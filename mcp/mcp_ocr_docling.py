# mcp_ocr_docling.py (fixed & hardened)
# MCP-friendly /ocr endpoint using Docling VLM (granite_docling) via CLI.
# Contract: multipart/form-data (image=<file>, lang=<code>)
# Returns: {"engine":"docling_granite","blocks":[{"text","confidence","bbox"}], "meta": {...}}

import io
import os
import json
import tempfile
import subprocess
import shlex
import imghdr
import traceback
from typing import List, Dict, Any, Tuple
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import uvicorn

# ---- Settings (override with env if needed) ----
DOCLING_BIN       = os.getenv("DOCLING_BIN", "docling")             # docling CLI on PATH
VLM_MODEL         = os.getenv("DOCLING_VLM_MODEL", "granite_docling")
PIPELINE          = os.getenv("DOCLING_PIPELINE", "vlm")            # docling pipeline id
MAX_JSON_MB       = float(os.getenv("DOCLING_MAX_JSON_MB", "64"))   # safety cap for capture
DOCLING_TIMEOUT_S = int(os.getenv("DOCLING_TIMEOUT_S", "600"))      # allow larger PDFs

# Global lazy init for Docling health to avoid repeated slow checks
_docling_healthy: bool | None = None

app = FastAPI(title="MCP OCR - Docling", version="1.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ------------------------- Utilities -------------------------
def _get_docling_health() -> bool:
    """Lazy check Docling CLI health once, cache result."""
    global _docling_healthy
    if _docling_healthy is not None:
        return _docling_healthy
    try:
        # Use --version for a potentially faster check than --help
        subprocess.run([DOCLING_BIN, "--version"], capture_output=True, check=True, timeout=30)
        _docling_healthy = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _docling_healthy = False
    except subprocess.CalledProcessError:
        # Non-zero exit, but exists
        _docling_healthy = True
    except Exception:
        _docling_healthy = False
    return _docling_healthy


def _ensure_docling() -> None:
    """Fail early if docling CLI is unhealthy."""
    if not _get_docling_health():
        raise RuntimeError(
            f"Docling CLI '{DOCLING_BIN}' unhealthy. Install with: pip install docling. "
            f"Check env (e.g., PYTORCH_ENABLE_MPS_FALLBACK=1 for Mac M1). "
            f"If slow, set TRANSFORMERS_NO_TORCH=1 etc."
        )


def _img_to_pdf_bytes(pil: Image.Image) -> bytes:
    """Wrap 1 image page into a minimal PDF using Pillow only (no img2pdf/pikepdf)."""
    buf = io.BytesIO()
    pil.convert("RGB").save(buf, format="PDF", resolution=300.0)
    return buf.getvalue()


def _maybe_coerce_json(stdout: str) -> Dict[str, Any]:
    """Docling sometimes prints logs before JSON. Try best-effort recovery."""
    if not stdout:
        raise RuntimeError("Docling produced empty output")
    # quick size guard
    if len(stdout) > MAX_JSON_MB * 1024 * 1024:
        raise RuntimeError(f"Docling JSON exceeded {MAX_JSON_MB} MB")
    # try normal parse
    try:
        return json.loads(stdout)
    except Exception:
        pass
    # strip leading/trailing non-JSON
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stdout[start:end+1]
        try:
            return json.loads(candidate)
        except Exception as e:
            raise RuntimeError(f"Docling produced non-JSON output (after trimming): {e}\nHead:\n{stdout[:1000]}")
    raise RuntimeError(f"Docling produced non-JSON output. Head:\n{stdout[:1000]}")


def _run_docling_vlm(pdf_path: str) -> Dict[str, Any]:
    """
    Execute docling CLI:
      docling --to json --pipeline <PIPELINE> --vlm-model <VLM_MODEL> <pdf>
    Prefer stdout; if empty, load any JSON Docling wrote to cwd.
    """
    cmd = [DOCLING_BIN, "--to", "json", "--pipeline", PIPELINE, "--vlm-model", VLM_MODEL, pdf_path]
    cmd_str = shlex.join(cmd)
    print(f"[DOCLING] Running: {cmd_str}")

    # Run in a temp working dir to capture any file artifacts Docling creates
    with tempfile.TemporaryDirectory() as workdir:
        proc = None
        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=DOCLING_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            stderr = getattr(proc, 'stderr', '') or ''
            raise RuntimeError(f"Docling timed out after {DOCLING_TIMEOUT_S}s. cmd={cmd_str}\nSTDERR:\n{stderr[:4000]}")

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"Docling failed (rc={proc.returncode}) cmd={cmd_str}\nSTDERR:\n{stderr[:4000]}")

        # 1) Try stdout first
        stdout = proc.stdout or ""
        if stdout.strip():
            return _maybe_coerce_json(stdout)

        # 2) Try to find a JSON file Docling may have emitted in workdir
        try:
            json_candidates = [
                os.path.join(workdir, f)
                for f in os.listdir(workdir)
                if f.lower().endswith(".json")
            ]
            if json_candidates:
                # pick the newest/ largest as a heuristic
                json_path = max(json_candidates, key=lambda p: (os.path.getmtime(p), os.path.getsize(p)))
                with open(json_path, "r", encoding="utf-8") as jf:
                    return json.load(jf)
        except Exception as e:
            # ignore and fall through to stderr parsing
            pass

        # 3) As a last resort, try to trim JSON out of STDERR
        stderr = proc.stderr or ""
        if stderr.strip():
            try:
                return _maybe_coerce_json(stderr)
            except Exception:
                pass

        # 4) Nothing usable
        raise RuntimeError("Docling produced empty output and no JSON file in working directory.\n" +
                           ("STDERR (trimmed):\n" + (stderr[:4000] if stderr else "<none>")))


def _to_bbox(box: Any, page_w: float, page_h: float) -> List[float]:
    """
    Accepts a variety of Docling-like shapes:
      - [x0,y0,x1,y1]
      - {"x0":...,"y0":...,"x1":...,"y1":...}
      - polygon: [[x,y], ...]
      Fallback: full page.
    """
    if not box:
        return [0.0, 0.0, float(page_w), float(page_h)]
    if isinstance(box, dict) and {"x0","y0","x1","y1"}.issubset(box.keys()):
        return [float(box["x0"]), float(box["y0"]), float(box["x1"]), float(box["y1"])]
    if isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
        x0,y0,x1,y1 = box
        return [float(x0), float(y0), float(x1), float(y1)]
    if isinstance(box, (list, tuple)) and box and isinstance(box[0], (list, tuple)) and len(box[0]) == 2:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
    return [0.0, 0.0, float(page_w), float(page_h)]


def _harvest_candidates(js: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float, float, Dict[str, Any]]:
    """Collect candidate items and infer page size & meta across Docling JSON variants."""
    candidates: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}
    page_w = float(js.get("page_width", js.get("width", 2480)))
    page_h = float(js.get("page_height", js.get("height", 3508)))

    # Some docling variants wrap under top-level keys like 'result', 'document', or 'documents'
    for wrap_key in ("result", "document", "data"):
        if isinstance(js.get(wrap_key), dict):
            js = js[wrap_key]
            break

    # If there are multiple pages
    pages = js.get("pages")
    if isinstance(pages, list) and pages:
        meta["pages"] = len(pages)
        # Pull items from all pages, not just first
        for pg in pages:
            page_w = float(pg.get("width", page_w))
            page_h = float(pg.get("height", page_h))
            for key in ("elements", "items", "blocks", "lines", "spans", "regions"):
                arr = pg.get(key)
                if isinstance(arr, list):
                    candidates.extend(arr)

    # Also scan common top-level arrays
    for key in ("items", "blocks", "regions", "elements", "lines", "spans"):
        arr = js.get(key)
        if isinstance(arr, list):
            candidates.extend(arr)

    return candidates, page_w, page_h, meta


def _extract_blocks_from_docling(js: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Docling JSON into our blocks. Best-effort across versions.
    """
    blocks: List[Dict[str, Any]] = []
    candidates, page_w, page_h, meta = _harvest_candidates(js)

    for it in candidates:
        if not isinstance(it, dict):
            continue
        txt = (it.get("text") or it.get("content") or "").strip()
        if not txt:
            continue
        box = it.get("bbox") or it.get("box") or it.get("polygon") or it.get("points")
        bbox = _to_bbox(box, page_w, page_h)
        conf = it.get("confidence", it.get("score", 0.99))
        try:
            conf = float(conf)
            if conf > 1.0:
                conf = conf / 100.0
        except Exception:
            conf = 0.99
        blocks.append({"text": txt, "confidence": conf, "bbox": bbox})

    # Fallback: doc-level text
    if not blocks:
        for key in ("text", "markdown", "md", "content"):
            if isinstance(js.get(key), str) and js[key].strip():
                txt = js[key].strip()
                blocks.append({"text": txt, "confidence": 0.99, "bbox": [0.0, 0.0, page_w, page_h]})
                break

    return {"blocks": blocks, "meta": meta, "page_size": {"w": page_w, "h": page_h}}


# -------------------------- API Routes --------------------------
@app.get("/warmup")
def warmup():
    """Trigger Docling model load/caching with a tiny synthetic PDF."""
    try:
        _ensure_docling()
        import time
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory() as td:
            img = Image.new("RGB", (400, 200), "white")
            d = ImageDraw.Draw(img)
            d.text((10, 90), "docling warmup", fill="black")
            pdf_path = os.path.join(td, "warmup.pdf")
            with open(pdf_path, "wb") as f:
                f.write(_img_to_pdf_bytes(img))
            t0 = time.time()
            js = _run_docling_vlm(pdf_path)
            dt = time.time() - t0
            out = _extract_blocks_from_docling(js)
        return {"ok": True, "seconds": round(dt, 2), "blocks": len(out["blocks"])}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/ocr")
async def ocr(image: UploadFile = File(...), lang: str = Form("en")):
    """
    Accept an image *or* a PDF, run Docling VLM (granite_docling), return blocks (text+bbox).
    - If the uploaded file is a PDF (content_type 'application/pdf' or magic), pass through.
    - Otherwise, treat as image and wrap into a 1-page PDF.
    """
    try:
        _ensure_docling()

        data = await image.read()
        content_type = image.content_type or ""

        with tempfile.TemporaryDirectory() as td:
            pdf_path = os.path.join(td, "page.pdf")

            is_pdf = content_type == "application/pdf" or (data[:4] == b"%PDF")
            if is_pdf:
                with open(pdf_path, "wb") as f:
                    f.write(data)
            else:
                # try open image first to validate
                try:
                    pil = Image.open(io.BytesIO(data)).convert("RGB")
                except Exception:
                    # final fallback: detect via imghdr
                    if imghdr.what(None, h=data) is None:
                        raise RuntimeError(f"Unsupported file type: {content_type or 'unknown'}")
                    pil = Image.open(io.BytesIO(data)).convert("RGB")
                with open(pdf_path, "wb") as f:
                    f.write(_img_to_pdf_bytes(pil))

            js = _run_docling_vlm(pdf_path)
            out = _extract_blocks_from_docling(js)

        return JSONResponse({
            "engine": "docling_granite",
            "blocks": out["blocks"],
            "meta": {"lang": lang, **out.get("meta", {})},
            "page_size": out.get("page_size", {}),
        })

    except Exception as e:
        # Omit traceback in production; include for debugging
        tb = os.getenv("DOCLING_INCLUDE_TRACEBACK", "0") == "1"
        resp = {
            "engine": "docling_granite",
            "blocks": [],
            "error": str(e),
        }
        if tb:
            resp["traceback"] = traceback.format_exc()
        return JSONResponse(resp, status_code=500)


@app.get("/health")
def health():
    healthy = _get_docling_health()
    if not healthy:
        return {"ok": False, "error": "Docling CLI unhealthy"}
    return {"ok": True, "engine": "docling_granite", "pipeline": PIPELINE, "model": VLM_MODEL}


# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (docling)")
except Exception as e:
    print(f"[WARN] MCP not enabled for docling: {e}")


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8093"))
    print(f"[INFO] Starting Docling OCR server on {host}:{port}")
    print(f"[INFO] Using model: {VLM_MODEL}, pipeline: {PIPELINE}")

    # Optional warmup on start (set DOCLING_WARMUP_ON_START=1)
    if os.getenv("DOCLING_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                try:
                    # wait a bit for server to come up then warm
                    import time; time.sleep(1)
                    print("[WARMUP] hitting /warmup ...")
                    requests.get(f"http://{host}:{port}/warmup", timeout=600)
                    print("[WARMUP] done")
                except Exception as e:
                    print(f"[WARMUP] failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")

    uvicorn.run(app, host=host, port=port)