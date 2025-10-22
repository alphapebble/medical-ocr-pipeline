#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_ocr_verifier.py
------------------
Visual + quantitative verification for OCR completeness and layout coverage.

Inputs:
  - PDF file path
  - Directory containing JSON blocks per page (e.g., page_001_native.json, page_001_ocr_easy.json, page_001_ocr_tess.json)

Outputs (in --out-dir):
  - overlays/: page-wise overlay PNGs (native/easy/tess/combined)
  - heatmaps/: page-wise coverage heatmaps (PNG)
  - metrics.csv: per-page metrics (chars, recall vs PDF text layer, coverage score)
  - missing_words.json: words seen in PDF text layer but missing in OCR (top-K per page)
  - report.html: simple dashboard linking everything

Dependencies: fitz (PyMuPDF), Pillow, matplotlib, numpy, pandas
"""

import argparse, json, difflib, math, re
from pathlib import Path
from typing import Dict, List, Any, Tuple
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# --------------------------- Utils ---------------------------

def page_to_image(doc, page_index: int, dpi: int = 200) -> Image.Image:
    page = doc[page_index]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

def draw_blocks(img: Image.Image, blocks: List[Dict[str, Any]], color: str, label: str = None) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for b in blocks:
        if not isinstance(b, dict):
            continue
        bbox = b.get("bbox") or []
        if len(bbox) != 4:
            continue
        x0, y0, x1, y1 = bbox
        try:
            draw.rectangle([x0, y0, x1, y1], outline=color, width=2)
        except Exception:
            # Fallback: ignore invalid boxes
            continue
    if label:
        try:
            draw.text((10, 10), label, fill=color)
        except Exception:
            pass
    return img

def load_blocks(blocks_dir: Path, page_num: int) -> Dict[str, List[Dict[str, Any]]]:
    parts = {}
    # Expected filenames (adjust if your naming differs)
    mapping = {
        "native": blocks_dir / f"page_{page_num:03d}_native.json",
        "ocr_easy": blocks_dir / f"page_{page_num:03d}_ocr_easy.json",
        "ocr_tess": blocks_dir / f"page_{page_num:03d}_ocr_tess.json",
        "ocr_paddle": blocks_dir / f"page_{page_num:03d}_ocr_paddle.json",
        "ocr_surya": blocks_dir / f"page_{page_num:03d}_ocr_surya.json",
    }
    for k, p in mapping.items():
        if p.exists():
            try:
                parts[k] = json.loads(p.read_text())
            except Exception:
                parts[k] = []
        else:
            parts[k] = []
    return parts

def concat_text(blocks: List[Dict[str, Any]]) -> str:
    return " ".join((b.get("text") or "").strip() for b in blocks if isinstance(b, dict))

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def word_set(s: str) -> List[str]:
    # Split on non-alphanumerics; lowercase
    return [w for w in re.split(r"[^A-Za-z0-9]+", s.lower()) if w]

def coverage_mask(blocks: List[Dict[str, Any]], width: int, height: int, bin_size: int = 10) -> np.ndarray:
    """Return a HxW grid coverage mask with counts of how many boxes cover each bin."""
    H = max(1, height // bin_size)
    W = max(1, width // bin_size)
    mask = np.zeros((H, W), dtype=np.float32)
    for b in blocks:
        bbox = b.get("bbox", [])
        if len(bbox) != 4: 
            continue
        x0, y0, x1, y1 = bbox
        x0b, x1b = int(x0 // bin_size), int(x1 // bin_size)
        y0b, y1b = int(y0 // bin_size), int(y1 // bin_size)
        x0b, y0b = max(0, x0b), max(0, y0b)
        x1b, y1b = min(W-1, x1b), min(H-1, y1b)
        mask[y0b:y1b+1, x0b:x1b+1] += 1.0
    return mask

def save_heatmap(mask: np.ndarray, out_png: Path, title: str = "") -> None:
    plt.figure(figsize=(6, 6))
    plt.imshow(mask, interpolation="nearest")  # use default colormap
    plt.title(title)
    plt.axis("off")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, bbox_inches="tight", dpi=150)
    plt.close()

# --------------------------- Main ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to input PDF")
    ap.add_argument("--blocks-dir", required=True, help="Directory with page_XXX_*.json files")
    ap.add_argument("--out-dir", required=True, help="Output directory for visuals & report")
    ap.add_argument("--pages", type=int, default=5, help="Max pages to process")
    ap.add_argument("--dpi", type=int, default=200, help="Rasterization DPI")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    blocks_dir = Path(args.blocks_dir)
    out_dir = Path(args.out_dir)
    overlays_dir = out_dir / "overlays"
    heatmaps_dir = out_dir / "heatmaps"
    out_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)
    heatmaps_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    n_pages = min(len(doc), args.pages)

    records = []
    missing_words_all = {}

    for idx in range(n_pages):
        page_num = idx + 1
        page = doc[idx]
        print(f"[+] Page {page_num}")
        img = page_to_image(doc, idx, dpi=args.dpi)
        width, height = img.size

        parts = load_blocks(blocks_dir, page_num)
        native = parts.get("native", [])
        easy = parts.get("ocr_easy", [])
        tess = parts.get("ocr_tess", [])
        paddle = parts.get("ocr_paddle", [])
        surya = parts.get("ocr_surya", [])

        # --- Overlays ---
        paths = {}
        for name, blocks, color in [
            ("native", native, "cyan"),
            ("easy",   easy,   "orange"),
            ("tess",   tess,   "magenta"),
            ("paddle", paddle, "green"),
            ("surya",  surya,  "red"),
        ]:
            if not blocks:
                continue
            canvas = img.copy()
            draw_blocks(canvas, blocks, color, f"{name}")
            out_png = overlays_dir / f"page_{page_num:03d}_{name}.png"
            canvas.save(out_png)
            paths[name] = out_png.name

        # Combined overlay
        combined = img.copy()
        if native: draw_blocks(combined, native, "cyan", None)
        if easy:   draw_blocks(combined, easy, "orange", None)
        if tess:   draw_blocks(combined, tess, "magenta", None)
        if paddle: draw_blocks(combined, paddle, "green", None)
        if surya:  draw_blocks(combined, surya, "red", None)
        combined_path = overlays_dir / f"page_{page_num:03d}_combined.png"
        combined.save(combined_path)

        # --- Text completeness vs PDF text layer ---
        ref_text = page.get_text("text") or ""  # may be empty for scanned PDFs
        ocr_text = " ".join([
            concat_text(native),
            concat_text(easy),
            concat_text(tess),
            concat_text(paddle),
            concat_text(surya),
        ]).strip()

        ref_norm = normalize_ws(ref_text)
        ocr_norm = normalize_ws(ocr_text)

        if ref_norm and ocr_norm:
            char_recall = difflib.SequenceMatcher(None, ref_norm, ocr_norm).ratio()
        else:
            # If no reference text layer, we can't compute a true recall
            char_recall = float("nan")

        # --- Density metrics ---
        def char_count(blocks):
            return sum(len((b.get("text") or "")) for b in blocks)

        density_native = char_count(native)
        density_easy   = char_count(easy)
        density_tess   = char_count(tess)
        density_paddle = char_count(paddle)
        density_surya  = char_count(surya)
        density_total  = sum([density_native, density_easy, density_tess, density_paddle, density_surya])

        # --- Coverage heatmap over combined blocks ---
        all_blocks = []
        for lst in [native, easy, tess, paddle, surya]:
            all_blocks.extend(lst)
        mask = coverage_mask(all_blocks, width, height, bin_size=10)
        heat_png = heatmaps_dir / f"page_{page_num:03d}_heatmap.png"
        save_heatmap(mask, heat_png, title=f"Coverage (page {page_num})")

        # --- Missing words (from ref layer not in OCR) ---
        missing_words = []
        if ref_norm:
            ref_words = word_set(ref_norm)
            ocr_words = word_set(ocr_norm)
            ref_counts = {}
            for w in ref_words:
                ref_counts[w] = ref_counts.get(w, 0) + 1
            ocr_counts = {}
            for w in ocr_words:
                ocr_counts[w] = ocr_counts.get(w, 0) + 1
            # words with higher ref count than ocr count
            for w, c in ref_counts.items():
                if c > ocr_counts.get(w, 0):
                    missing_words.append((w, c - ocr_counts.get(w, 0)))
            # sort by deficit descending
            missing_words.sort(key=lambda x: x[1], reverse=True)
            missing_words_all[str(page_num)] = missing_words[:50]  # top 50
        else:
            missing_words_all[str(page_num)] = []

        records.append({
            "page": page_num,
            "width": width,
            "height": height,
            "char_recall_vs_pdf_text": char_recall,
            "chars_native": density_native,
            "chars_easy": density_easy,
            "chars_tess": density_tess,
            "chars_paddle": density_paddle,
            "chars_surya": density_surya,
            "chars_total": density_total,
            "overlay_combined": combined_path.name,
            "heatmap": heat_png.name,
            **{f"overlay_{k}": v for k,v in paths.items()}
        })

    # --- Save metrics & missing words ---
    df = pd.DataFrame.from_records(records).sort_values("page")
    df.to_csv(out_dir / "metrics.csv", index=False)
    with open(out_dir / "missing_words.json", "w") as f:
        json.dump(missing_words_all, f, indent=2)

    # --- Build simple HTML report ---
    template_path = Path(__file__).with_name("ocr_report_template.html")
    if template_path.exists():
        html = template_path.read_text()
    else:
        html = "<html><body><h1>OCR Report</h1></body></html>"

    # Build rows
    rows = []
    for r in records:
        imgs_html = []
        # Combined & heatmap first
        imgs_html.append(f'<div style="margin:6px 0;"><div>Combined</div><img src="overlays/{r["overlay_combined"]}" style="max-width:100%;"></div>')
        imgs_html.append(f'<div style="margin:6px 0;"><div>Heatmap</div><img src="heatmaps/{r["heatmap"]}" style="max-width:100%;"></div>')
        # Individual overlays if present
        for key in ["overlay_native","overlay_easy","overlay_tess","overlay_paddle","overlay_surya"]:
            if key in r:
                imgs_html.append(f'<div style="margin:6px 0;"><div>{key.replace("overlay_","").upper()}</div><img src="overlays/{r[key]}" style="max-width:100%;"></div>')
        row = f"""
        <tr>
          <td style="vertical-align:top;">{r["page"]}</td>
          <td>{r.get("char_recall_vs_pdf_text",""):.3f}</td>
          <td>{r["chars_native"]}</td>
          <td>{r["chars_easy"]}</td>
          <td>{r["chars_tess"]}</td>
          <td>{r["chars_paddle"]}</td>
          <td>{r["chars_surya"]}</td>
          <td>{r["chars_total"]}</td>
          <td>{"".join(imgs_html)}</td>
        </tr>
        """
        rows.append(row)

    table_html = "\n".join(rows)
    html = html.replace("{{TABLE_ROWS}}", table_html)
    html = html.replace("{{CSV_PATH}}", "metrics.csv")
    html = html.replace("{{MISSING_JSON_PATH}}", "missing_words.json")
    (out_dir / "report.html").write_text(html, encoding="utf-8")

    print(f"[✓] Done. Outputs in: {out_dir}")
    print(f"    - metrics.csv")
    print(f"    - missing_words.json")
    print(f"    - overlays/, heatmaps/")
    print(f"    - report.html")

if __name__ == "__main__":
    main()
