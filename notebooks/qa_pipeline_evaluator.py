#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QA Pipeline Evaluator
=====================
Comprehensive evaluation system for the medical OCR pipeline to track content drops,
quality metrics, and layout accuracy after each processing stage.

Inspired by tools like:
- Dinglehopper (OCR evaluation with GT comparison)
- DavarOCR (layout + recognition evaluation)
- MultimodalOCR (benchmarking across datasets)
- Scribe OCR (visual proofreading)

Features:
- Stage-wise quality tracking (01_blocks → 02_cleanup → 03_llm → 04_extraction → 05_merged)
- Content drop analysis (character/word/block count changes)
- Layout preservation metrics (bbox coverage, reading order)
- Cross-engine OCR comparison and ensemble evaluation
- Visual diff generation and overlay reports
- Medical domain-specific metrics (terminology preservation)
- Ground truth comparison (when available)
- Confidence scoring and uncertainty detection
"""

import argparse
import json
import re
import math
import difflib
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import warnings

# Core dependencies
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image, ImageDraw, ImageFont

# OCR/PDF processing
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    warnings.warn("PyMuPDF not available - PDF processing disabled")

# Text processing
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    warnings.warn("spaCy not available - advanced text analysis disabled")

# Medical NLP
try:
    import scispacy  # noqa
    HAS_SCISPACY = True
except ImportError:
    HAS_SCISPACY = False

# Optional: QuickUMLS for medical entity recognition
try:
    from quickumls import QuickUMLS
    HAS_QUICKUMLS = True
except ImportError:
    HAS_QUICKUMLS = False

# ========================= DATA STRUCTURES =========================

@dataclass
class StageMetrics:
    """Metrics for a single processing stage"""
    stage_name: str
    input_files: List[str] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)
    
    # Content metrics
    total_chars: int = 0
    total_words: int = 0
    total_blocks: int = 0
    unique_words: int = 0
    
    # Layout metrics
    total_bbox_area: float = 0.0
    coverage_percentage: float = 0.0
    reading_order_score: float = 0.0
    
    # Quality metrics
    mean_confidence: float = 0.0
    low_confidence_blocks: int = 0
    empty_blocks: int = 0
    
    # Medical domain metrics
    medical_terms_count: int = 0
    medical_terms_preserved: float = 0.0
    
    # Change tracking
    chars_added: int = 0
    chars_removed: int = 0
    words_added: int = 0
    words_removed: int = 0
    blocks_added: int = 0
    blocks_removed: int = 0

@dataclass
class PageEvaluation:
    """Complete evaluation for a single page across all stages"""
    page_number: int
    pdf_path: str
    stages: Dict[str, StageMetrics] = field(default_factory=dict)
    
    # Ground truth comparison (if available)
    ground_truth_file: Optional[str] = None
    word_error_rate: float = float('nan')
    character_error_rate: float = float('nan')
    layout_accuracy: float = float('nan')
    
    # Cross-engine comparison
    ocr_engine_agreement: Dict[str, float] = field(default_factory=dict)
    best_ocr_engine: str = ""
    
    # Visual artifacts
    overlay_images: Dict[str, str] = field(default_factory=dict)
    diff_images: Dict[str, str] = field(default_factory=dict)

@dataclass
class PipelineEvaluation:
    """Complete pipeline evaluation across all pages and stages"""
    run_id: str
    pdf_path: str
    pages: Dict[int, PageEvaluation] = field(default_factory=dict)
    
    # Aggregate metrics
    total_content_drop: float = 0.0  # Percentage of content lost
    quality_trend: List[float] = field(default_factory=list)  # Quality by stage
    problematic_pages: List[int] = field(default_factory=list)
    
    # Recommendations
    recommended_actions: List[str] = field(default_factory=list)
    quality_score: float = 0.0

# ========================= CORE EVALUATOR =========================

class QAPipelineEvaluator:
    """Main evaluator class for OCR pipeline quality assessment"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.medical_terms = self._load_medical_terms()
        self.nlp = self._init_nlp()
        self.quickumls = self._init_quickumls()
        
        # Stage definitions
        self.stage_mapping = {
            "01_blocks": "Block Extraction",
            "01a_normalized": "Layout Normalization", 
            "02_cleaned": "Domain Cleanup",
            "02a_segmented": "Segmentation",
            "03_llmcleaned": "LLM Cleanup",
            "04_jsonextracted": "JSON Extraction",
            "05_merged_validated": "Final Merge & Validation"
        }
        
        # Output directories
        self.output_base = Path("qa_evaluation")
        self.overlays_dir = self.output_base / "overlays"
        self.metrics_dir = self.output_base / "metrics"
        self.reports_dir = self.output_base / "reports"
        
        # Create directories
        for d in [self.overlays_dir, self.metrics_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load evaluation configuration"""
        default_config = {
            "confidence_threshold": 0.7,
            "medical_terms_weight": 0.3,
            "layout_weight": 0.4,
            "content_weight": 0.3,
            "max_content_drop": 0.15,  # 15% max acceptable content loss
            "visualization_dpi": 200,
            "medical_terms_file": "config/medical_terms.yml"
        }
        
        if config_path and Path(config_path).exists():
            import yaml
            with open(config_path) as f:
                user_config = yaml.safe_load(f)
            default_config.update(user_config)
        
        return default_config
    
    def _load_medical_terms(self) -> Set[str]:
        """Load medical terminology for domain-specific evaluation"""
        terms = set()
        
        # Try to load from config
        medical_file = Path(self.config["medical_terms_file"])
        if medical_file.exists():
            try:
                import yaml
                with open(medical_file) as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        for category, term_list in data.items():
                            if isinstance(term_list, list):
                                terms.update(term.lower() for term in term_list)
                    elif isinstance(data, list):
                        terms.update(term.lower() for term in data)
            except Exception as e:
                print(f"Warning: Could not load medical terms: {e}")
        
        # Add some common medical terms as fallback
        fallback_terms = {
            "prescription", "medication", "dosage", "tablet", "capsule", "mg", "ml",
            "patient", "diagnosis", "symptoms", "treatment", "therapy", "doctor",
            "hospital", "clinic", "medical", "health", "blood", "pressure", "heart",
            "diabetes", "hypertension", "cholesterol", "infection", "antibiotics"
        }
        terms.update(fallback_terms)
        
        return terms
    
    def _init_nlp(self):
        """Initialize NLP pipeline for text analysis"""
        if not HAS_SPACY:
            return None
            
        # Try to load medical NLP models
        for model_name in ["en_core_sci_lg", "en_ner_bc5cdr_md", "en_core_web_sm"]:
            try:
                nlp = spacy.load(model_name)
                print(f"Loaded spaCy model: {model_name}")
                return nlp
            except OSError:
                continue
        
        print("Warning: No spaCy models available for advanced text analysis")
        return None
    
    def _init_quickumls(self):
        """Initialize QuickUMLS for medical entity recognition"""
        if not HAS_QUICKUMLS:
            return None
            
        # This would need QuickUMLS data files - skip if not available
        return None
    
    # ========================= CONTENT ANALYSIS =========================
    
    def analyze_content_changes(self, before_blocks: List[Dict], after_blocks: List[Dict]) -> Dict[str, Any]:
        """Analyze content changes between processing stages"""
        
        def extract_text_stats(blocks):
            texts = [block.get("text", "") for block in blocks if block.get("text")]
            combined_text = " ".join(texts)
            
            return {
                "total_chars": len(combined_text),
                "total_words": len(combined_text.split()),
                "unique_words": len(set(word.lower() for word in combined_text.split())),
                "block_count": len(blocks),
                "empty_blocks": len([b for b in blocks if not b.get("text", "").strip()]),
                "texts": texts
            }
        
        before_stats = extract_text_stats(before_blocks)
        after_stats = extract_text_stats(after_blocks)
        
        # Calculate changes
        changes = {
            "chars_delta": after_stats["total_chars"] - before_stats["total_chars"],
            "words_delta": after_stats["total_words"] - before_stats["total_words"],
            "blocks_delta": after_stats["block_count"] - before_stats["block_count"],
            "unique_words_delta": after_stats["unique_words"] - before_stats["unique_words"],
            "empty_blocks_delta": after_stats["empty_blocks"] - before_stats["empty_blocks"],
            
            "content_retention": (after_stats["total_chars"] / max(before_stats["total_chars"], 1)),
            "block_retention": (after_stats["block_count"] / max(before_stats["block_count"], 1)),
        }
        
        # Analyze text quality changes
        if self.nlp:
            before_text = " ".join(before_stats["texts"])
            after_text = " ".join(after_stats["texts"])
            
            changes["text_similarity"] = self._calculate_text_similarity(before_text, after_text)
            changes["medical_terms_preserved"] = self._calculate_medical_preservation(before_text, after_text)
        
        return changes
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        if not self.nlp or not text1.strip() or not text2.strip():
            return difflib.SequenceMatcher(None, text1, text2).ratio()
        
        try:
            doc1 = self.nlp(text1)
            doc2 = self.nlp(text2)
            return doc1.similarity(doc2)
        except Exception:
            return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    def _calculate_medical_preservation(self, before_text: str, after_text: str) -> float:
        """Calculate how well medical terminology is preserved"""
        before_terms = self._extract_medical_terms(before_text)
        after_terms = self._extract_medical_terms(after_text)
        
        if not before_terms:
            return 1.0  # No medical terms to preserve
        
        preserved = len(before_terms.intersection(after_terms))
        return preserved / len(before_terms)
    
    def _extract_medical_terms(self, text: str) -> Set[str]:
        """Extract medical terms from text"""
        words = set(re.findall(r'\b\w+\b', text.lower()))
        return words.intersection(self.medical_terms)
    
    # ========================= LAYOUT ANALYSIS =========================
    
    def analyze_layout_changes(self, before_blocks: List[Dict], after_blocks: List[Dict], 
                             page_width: int, page_height: int) -> Dict[str, Any]:
        """Analyze layout and spatial changes between stages"""
        
        def get_layout_stats(blocks):
            valid_blocks = [b for b in blocks if b.get("bbox") and len(b["bbox"]) == 4]
            
            if not valid_blocks:
                return {
                    "total_area": 0,
                    "coverage": 0,
                    "bbox_count": 0,
                    "reading_order_score": 0
                }
            
            total_area = 0
            bboxes = []
            
            for block in valid_blocks:
                x0, y0, x1, y1 = block["bbox"]
                area = max(0, (x1 - x0) * (y1 - y0))
                total_area += area
                bboxes.append((x0, y0, x1, y1))
            
            page_area = page_width * page_height
            coverage = min(1.0, total_area / page_area) if page_area > 0 else 0
            
            # Calculate reading order score (top-to-bottom, left-to-right)
            reading_order_score = self._calculate_reading_order_score(bboxes)
            
            return {
                "total_area": total_area,
                "coverage": coverage,
                "bbox_count": len(valid_blocks),
                "reading_order_score": reading_order_score,
                "bboxes": bboxes
            }
        
        before_layout = get_layout_stats(before_blocks)
        after_layout = get_layout_stats(after_blocks)
        
        return {
            "area_retention": (after_layout["total_area"] / max(before_layout["total_area"], 1)),
            "coverage_change": after_layout["coverage"] - before_layout["coverage"],
            "bbox_count_change": after_layout["bbox_count"] - before_layout["bbox_count"],
            "reading_order_change": after_layout["reading_order_score"] - before_layout["reading_order_score"],
            "layout_preservation": self._calculate_layout_preservation(before_layout["bboxes"], after_layout["bboxes"])
        }
    
    def _calculate_reading_order_score(self, bboxes: List[Tuple[float, float, float, float]]) -> float:
        """Calculate how well bboxes follow natural reading order"""
        if len(bboxes) < 2:
            return 1.0
        
        # Sort by reading order (top-to-bottom, left-to-right)
        sorted_bboxes = sorted(bboxes, key=lambda b: (b[1], b[0]))  # y, then x
        
        # Calculate how much the current order deviates from ideal
        order_violations = 0
        for i in range(len(bboxes) - 1):
            current = bboxes[i]
            next_box = bboxes[i + 1]
            
            # Check if reading order is violated
            if current[1] > next_box[1] + 10:  # Current is significantly below next
                order_violations += 1
            elif abs(current[1] - next_box[1]) < 10 and current[0] > next_box[0]:  # Same line, wrong horizontal order
                order_violations += 1
        
        return max(0, 1 - (order_violations / len(bboxes)))
    
    def _calculate_layout_preservation(self, before_bboxes: List, after_bboxes: List) -> float:
        """Calculate how well the layout structure is preserved"""
        if not before_bboxes or not after_bboxes:
            return 0.0
        
        # Calculate IoU-based preservation score
        total_iou = 0
        matches = 0
        
        for before_bbox in before_bboxes:
            best_iou = 0
            for after_bbox in after_bboxes:
                iou = self._calculate_bbox_iou(before_bbox, after_bbox)
                best_iou = max(best_iou, iou)
            
            if best_iou > 0.3:  # Threshold for considering a match
                total_iou += best_iou
                matches += 1
        
        return total_iou / len(before_bboxes) if before_bboxes else 0
    
    def _calculate_bbox_iou(self, bbox1: Tuple, bbox2: Tuple) -> float:
        """Calculate Intersection over Union for two bounding boxes"""
        x1, y1, x2, y2 = bbox1
        x3, y3, x4, y4 = bbox2
        
        # Calculate intersection
        xi1, yi1 = max(x1, x3), max(y1, y3)
        xi2, yi2 = min(x2, x4), min(y2, y4)
        
        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0
        
        intersection = (xi2 - xi1) * (yi2 - yi1)
        
        # Calculate union
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (x4 - x3) * (y4 - y3)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    # ========================= GROUND TRUTH EVALUATION =========================
    
    def evaluate_against_ground_truth(self, ocr_blocks: List[Dict], gt_file: str) -> Dict[str, float]:
        """Evaluate OCR output against ground truth (ALTO/PAGE/text format)"""
        if not Path(gt_file).exists():
            return {"error": "Ground truth file not found"}
        
        try:
            # Load ground truth based on file extension
            gt_text = self._load_ground_truth(gt_file)
            ocr_text = " ".join(block.get("text", "") for block in ocr_blocks)
            
            # Calculate standard OCR metrics
            metrics = {
                "character_error_rate": self._calculate_cer(gt_text, ocr_text),
                "word_error_rate": self._calculate_wer(gt_text, ocr_text),
                "bleu_score": self._calculate_bleu(gt_text, ocr_text),
                "edit_distance": difflib.SequenceMatcher(None, gt_text, ocr_text).ratio()
            }
            
            return metrics
            
        except Exception as e:
            return {"error": f"Ground truth evaluation failed: {str(e)}"}
    
    def _load_ground_truth(self, gt_file: str) -> str:
        """Load ground truth text from various formats"""
        gt_path = Path(gt_file)
        
        if gt_path.suffix.lower() == '.txt':
            return gt_path.read_text(encoding='utf-8')
        elif gt_path.suffix.lower() in ['.xml', '.alto', '.page']:
            # For ALTO/PAGE XML, would need proper parsing
            # For now, treat as text
            return gt_path.read_text(encoding='utf-8')
        else:
            # Try as JSON
            try:
                data = json.loads(gt_path.read_text())
                if isinstance(data, list):
                    return " ".join(item.get("text", "") for item in data if isinstance(item, dict))
                elif isinstance(data, dict):
                    return data.get("text", "")
                else:
                    return str(data)
            except Exception:
                return gt_path.read_text(encoding='utf-8')
    
    def _calculate_cer(self, reference: str, hypothesis: str) -> float:
        """Calculate Character Error Rate"""
        return 1 - difflib.SequenceMatcher(None, reference, hypothesis).ratio()
    
    def _calculate_wer(self, reference: str, hypothesis: str) -> float:
        """Calculate Word Error Rate"""
        ref_words = reference.split()
        hyp_words = hypothesis.split()
        return 1 - difflib.SequenceMatcher(None, ref_words, hyp_words).ratio()
    
    def _calculate_bleu(self, reference: str, hypothesis: str) -> float:
        """Simple BLEU-like score calculation"""
        ref_words = set(reference.lower().split())
        hyp_words = set(hypothesis.lower().split())
        
        if not ref_words:
            return 1.0 if not hyp_words else 0.0
        
        intersection = len(ref_words.intersection(hyp_words))
        return intersection / len(ref_words)
    
    # ========================= VISUALIZATION =========================
    
    def create_stage_comparison_overlay(self, page_data: Dict, output_dir: Path, page_num: int):
        """Create visual overlays comparing different stages"""
        if not HAS_FITZ:
            print("Warning: PyMuPDF not available - skipping overlay generation")
            return
        
        # This would integrate with the existing overlay generation code
        # from the OCR verifier but extend it for stage-wise comparison
        pass
    
    def create_quality_trends_plot(self, evaluation: PipelineEvaluation, output_path: Path):
        """Create plots showing quality trends across stages"""
        
        # Aggregate metrics across all pages for each stage
        stage_metrics = defaultdict(list)
        
        for page_eval in evaluation.pages.values():
            for stage_name, metrics in page_eval.stages.items():
                stage_metrics[stage_name].append({
                    'content_retention': metrics.total_chars,
                    'layout_score': metrics.reading_order_score,
                    'confidence': metrics.mean_confidence,
                    'medical_preservation': metrics.medical_terms_preserved
                })
        
        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Pipeline Quality Trends - {evaluation.run_id}', fontsize=16)
        
        stages = list(stage_metrics.keys())
        
        # Content retention plot
        content_means = [np.mean([m['content_retention'] for m in stage_metrics[s]]) for s in stages]
        axes[0, 0].plot(stages, content_means, marker='o')
        axes[0, 0].set_title('Content Retention')
        axes[0, 0].set_ylabel('Characters')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # Layout quality plot
        layout_means = [np.mean([m['layout_score'] for m in stage_metrics[s]]) for s in stages]
        axes[0, 1].plot(stages, layout_means, marker='s', color='orange')
        axes[0, 1].set_title('Layout Quality Score')
        axes[0, 1].set_ylabel('Score (0-1)')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # Confidence plot
        conf_means = [np.mean([m['confidence'] for m in stage_metrics[s]]) for s in stages]
        axes[1, 0].plot(stages, conf_means, marker='^', color='green')
        axes[1, 0].set_title('Mean Confidence')
        axes[1, 0].set_ylabel('Confidence (0-1)')
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # Medical preservation plot
        med_means = [np.mean([m['medical_preservation'] for m in stage_metrics[s]]) for s in stages]
        axes[1, 1].plot(stages, med_means, marker='d', color='red')
        axes[1, 1].set_title('Medical Terms Preservation')
        axes[1, 1].set_ylabel('Preservation Rate (0-1)')
        axes[1, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    # ========================= MAIN EVALUATION PIPELINE =========================
    
    def evaluate_pipeline_run(self, run_dir: str, pdf_path: str = None, 
                            ground_truth_dir: str = None) -> PipelineEvaluation:
        """Evaluate a complete pipeline run"""
        
        run_path = Path(run_dir)
        if not run_path.exists():
            raise ValueError(f"Run directory not found: {run_dir}")
        
        # Initialize evaluation
        evaluation = PipelineEvaluation(
            run_id=run_path.name,
            pdf_path=pdf_path or ""
        )
        
        # Find all stage directories
        stage_dirs = {stage: run_path / stage for stage in self.stage_mapping.keys() 
                     if (run_path / stage).exists()}
        
        if not stage_dirs:
            raise ValueError(f"No recognized stage directories found in {run_dir}")
        
        print(f"Evaluating pipeline run: {evaluation.run_id}")
        print(f"Found stages: {list(stage_dirs.keys())}")
        
        # Determine page range
        first_stage = list(stage_dirs.values())[0]
        page_files = list(first_stage.glob("page_*.json"))
        page_numbers = []
        
        for pf in page_files:
            # Extract page number from filename
            match = re.search(r'page_(\d+)', pf.name)
            if match:
                page_numbers.append(int(match.group(1)))
        
        page_numbers = sorted(set(page_numbers))
        print(f"Processing {len(page_numbers)} pages: {page_numbers}")
        
        # Process each page
        for page_num in page_numbers:
            page_eval = PageEvaluation(page_number=page_num, pdf_path=pdf_path or "")
            
            # Load ground truth if available
            if ground_truth_dir:
                gt_file = Path(ground_truth_dir) / f"page_{page_num:03d}.txt"
                if gt_file.exists():
                    page_eval.ground_truth_file = str(gt_file)
            
            prev_blocks = None
            
            # Process each stage for this page
            for stage_key, stage_dir in stage_dirs.items():
                stage_metrics = self._evaluate_page_stage(
                    stage_dir, page_num, stage_key, prev_blocks
                )
                
                if stage_metrics:
                    page_eval.stages[stage_key] = stage_metrics
                    
                    # Load blocks for next iteration
                    stage_files = list(stage_dir.glob(f"page_{page_num:03d}*.json"))
                    if stage_files:
                        with open(stage_files[0]) as f:
                            prev_blocks = json.load(f)
            
            # Ground truth evaluation for final stage
            if page_eval.ground_truth_file and prev_blocks:
                gt_metrics = self.evaluate_against_ground_truth(prev_blocks, page_eval.ground_truth_file)
                page_eval.word_error_rate = gt_metrics.get("word_error_rate", float('nan'))
                page_eval.character_error_rate = gt_metrics.get("character_error_rate", float('nan'))
            
            evaluation.pages[page_num] = page_eval
        
        # Calculate aggregate metrics
        self._calculate_aggregate_metrics(evaluation)
        
        # Generate reports
        self._generate_evaluation_report(evaluation)
        
        return evaluation
    
    def _evaluate_page_stage(self, stage_dir: Path, page_num: int, stage_key: str, 
                           prev_blocks: List[Dict] = None) -> Optional[StageMetrics]:
        """Evaluate a single page at a single stage"""
        
        # Find files for this page
        stage_files = list(stage_dir.glob(f"page_{page_num:03d}*.json"))
        if not stage_files:
            return None
        
        # Load current stage blocks
        try:
            with open(stage_files[0]) as f:
                current_blocks = json.load(f)
        except Exception as e:
            print(f"Error loading {stage_files[0]}: {e}")
            return None
        
        # Initialize metrics
        metrics = StageMetrics(stage_name=self.stage_mapping[stage_key])
        metrics.input_files = [str(f) for f in stage_files]
        
        # Basic content metrics
        all_text = " ".join(block.get("text", "") for block in current_blocks if block.get("text"))
        metrics.total_chars = len(all_text)
        metrics.total_words = len(all_text.split())
        metrics.total_blocks = len(current_blocks)
        metrics.unique_words = len(set(word.lower() for word in all_text.split()))
        
        # Quality metrics
        confidences = [block.get("confidence", 0) for block in current_blocks if "confidence" in block]
        metrics.mean_confidence = np.mean(confidences) if confidences else 0.0
        metrics.low_confidence_blocks = sum(1 for c in confidences if c < self.config["confidence_threshold"])
        metrics.empty_blocks = sum(1 for block in current_blocks if not block.get("text", "").strip())
        
        # Medical domain metrics
        metrics.medical_terms_count = len(self._extract_medical_terms(all_text))
        
        # Layout metrics
        valid_bboxes = [block["bbox"] for block in current_blocks 
                       if block.get("bbox") and len(block["bbox"]) == 4]
        if valid_bboxes:
            total_area = sum((x1-x0)*(y1-y0) for x0, y0, x1, y1 in valid_bboxes)
            metrics.total_bbox_area = max(0, total_area)
            metrics.reading_order_score = self._calculate_reading_order_score(valid_bboxes)
        
        # Compare with previous stage if available
        if prev_blocks is not None:
            content_changes = self.analyze_content_changes(prev_blocks, current_blocks)
            metrics.chars_added = max(0, content_changes["chars_delta"])
            metrics.chars_removed = max(0, -content_changes["chars_delta"])
            metrics.words_added = max(0, content_changes["words_delta"])
            metrics.words_removed = max(0, -content_changes["words_delta"])
            metrics.blocks_added = max(0, content_changes["blocks_delta"])
            metrics.blocks_removed = max(0, -content_changes["blocks_delta"])
            metrics.medical_terms_preserved = content_changes.get("medical_terms_preserved", 1.0)
        
        return metrics
    
    def _calculate_aggregate_metrics(self, evaluation: PipelineEvaluation):
        """Calculate pipeline-wide aggregate metrics"""
        
        if not evaluation.pages:
            return
        
        # Calculate total content drop across pipeline
        initial_chars = 0
        final_chars = 0
        
        for page_eval in evaluation.pages.values():
            stages = list(page_eval.stages.keys())
            if stages:
                first_stage = min(stages, key=lambda x: list(self.stage_mapping.keys()).index(x))
                last_stage = max(stages, key=lambda x: list(self.stage_mapping.keys()).index(x))
                
                initial_chars += page_eval.stages[first_stage].total_chars
                final_chars += page_eval.stages[last_stage].total_chars
        
        evaluation.total_content_drop = 1 - (final_chars / max(initial_chars, 1))
        
        # Calculate quality trend
        stage_order = list(self.stage_mapping.keys())
        evaluation.quality_trend = []
        
        for stage in stage_order:
            stage_scores = []
            for page_eval in evaluation.pages.values():
                if stage in page_eval.stages:
                    metrics = page_eval.stages[stage]
                    # Composite quality score
                    score = (
                        metrics.mean_confidence * 0.4 +
                        metrics.reading_order_score * 0.3 +
                        metrics.medical_terms_preserved * 0.3
                    )
                    stage_scores.append(score)
            
            if stage_scores:
                evaluation.quality_trend.append(np.mean(stage_scores))
        
        # Identify problematic pages
        for page_num, page_eval in evaluation.pages.items():
            # Check for significant content drops
            stages = list(page_eval.stages.keys())
            if len(stages) >= 2:
                first_chars = page_eval.stages[stages[0]].total_chars
                last_chars = page_eval.stages[stages[-1]].total_chars
                content_drop = 1 - (last_chars / max(first_chars, 1))
                
                if content_drop > self.config["max_content_drop"]:
                    evaluation.problematic_pages.append(page_num)
        
        # Generate recommendations
        self._generate_recommendations(evaluation)
        
        # Calculate overall quality score
        if evaluation.quality_trend:
            evaluation.quality_score = np.mean(evaluation.quality_trend)
    
    def _generate_recommendations(self, evaluation: PipelineEvaluation):
        """Generate actionable recommendations based on evaluation"""
        
        recommendations = []
        
        # Content drop recommendations
        if evaluation.total_content_drop > self.config["max_content_drop"]:
            recommendations.append(
                f"HIGH: Significant content loss detected ({evaluation.total_content_drop:.1%}). "
                f"Review preprocessing parameters and OCR engine settings."
            )
        
        # Problematic pages
        if evaluation.problematic_pages:
            recommendations.append(
                f"MEDIUM: Pages {evaluation.problematic_pages} show quality issues. "
                f"Consider manual review or ground truth annotation."
            )
        
        # Quality trend analysis
        if len(evaluation.quality_trend) >= 2:
            trend_slope = (evaluation.quality_trend[-1] - evaluation.quality_trend[0]) / len(evaluation.quality_trend)
            if trend_slope < -0.1:
                recommendations.append(
                    "MEDIUM: Quality decreases through pipeline stages. "
                    "Review stage-specific processing logic."
                )
        
        # Low confidence blocks
        total_low_conf = sum(
            sum(stage.low_confidence_blocks for stage in page.stages.values())
            for page in evaluation.pages.values()
        )
        
        if total_low_conf > 0:
            recommendations.append(
                f"LOW: {total_low_conf} low-confidence blocks detected. "
                f"Consider OCR parameter tuning or manual review."
            )
        
        evaluation.recommended_actions = recommendations
    
    def _generate_evaluation_report(self, evaluation: PipelineEvaluation):
        """Generate comprehensive HTML evaluation report"""
        
        # Save metrics to CSV
        metrics_data = []
        for page_num, page_eval in evaluation.pages.items():
            for stage_key, metrics in page_eval.stages.items():
                metrics_data.append({
                    'page': page_num,
                    'stage': stage_key,
                    'stage_name': metrics.stage_name,
                    'total_chars': metrics.total_chars,
                    'total_words': metrics.total_words,
                    'total_blocks': metrics.total_blocks,
                    'mean_confidence': metrics.mean_confidence,
                    'low_confidence_blocks': metrics.low_confidence_blocks,
                    'medical_terms_count': metrics.medical_terms_count,
                    'medical_terms_preserved': metrics.medical_terms_preserved,
                    'reading_order_score': metrics.reading_order_score,
                    'chars_added': metrics.chars_added,
                    'chars_removed': metrics.chars_removed
                })
        
        df = pd.DataFrame(metrics_data)
        csv_path = self.metrics_dir / f"{evaluation.run_id}_detailed_metrics.csv"
        df.to_csv(csv_path, index=False)
        
        # Generate quality trends plot
        plot_path = self.reports_dir / f"{evaluation.run_id}_quality_trends.png"
        self.create_quality_trends_plot(evaluation, plot_path)
        
        # Generate HTML report
        html_content = self._create_html_report(evaluation, csv_path, plot_path)
        report_path = self.reports_dir / f"{evaluation.run_id}_evaluation_report.html"
        report_path.write_text(html_content, encoding='utf-8')
        
        print(f"\n✓ Evaluation complete for {evaluation.run_id}")
        print(f"  [STATS] Detailed metrics: {csv_path}")
        print(f"  📈 Quality trends: {plot_path}")
        print(f"  [STATUS] Full report: {report_path}")
        print(f"  [TARGET] Overall quality score: {evaluation.quality_score:.3f}")
        print(f"  📉 Total content drop: {evaluation.total_content_drop:.1%}")
        
        if evaluation.recommended_actions:
            print("  ⚠️  Recommendations:")
            for action in evaluation.recommended_actions:
                print(f"     • {action}")
    
    def _create_html_report(self, evaluation: PipelineEvaluation, csv_path: Path, plot_path: Path) -> str:
        """Create HTML evaluation report"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>OCR Pipeline Evaluation Report - {evaluation.run_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .metric-box {{ background: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #3498db; }}
        .warning {{ border-left-color: #e74c3c; background: #fdf2f2; }}
        .success {{ border-left-color: #27ae60; background: #eafaf1; }}
        .recommendation {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 5px 0; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .problematic {{ background-color: #ffe6e6; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OCR Pipeline Evaluation Report</h1>
        
        <div class="metric-box">
            <h3>Run Information</h3>
            <p><strong>Run ID:</strong> {evaluation.run_id}</p>
            <p><strong>PDF Path:</strong> {evaluation.pdf_path}</p>
            <p><strong>Pages Processed:</strong> {len(evaluation.pages)}</p>
            <p><strong>Generated:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="metric-box {'warning' if evaluation.total_content_drop > 0.15 else 'success'}">
            <h3>Overall Quality Metrics</h3>
            <p><strong>Quality Score:</strong> {evaluation.quality_score:.3f} / 1.0</p>
            <p><strong>Total Content Drop:</strong> {evaluation.total_content_drop:.1%}</p>
            <p><strong>Problematic Pages:</strong> {len(evaluation.problematic_pages)} 
               {f"(Pages: {', '.join(map(str, evaluation.problematic_pages))})" if evaluation.problematic_pages else ""}</p>
        </div>
        
        """
        
        # Recommendations section
        if evaluation.recommended_actions:
            html += "<h2>Recommendations</h2>\n"
            for action in evaluation.recommended_actions:
                priority = action.split(':')[0]
                html += f'<div class="recommendation"><strong>{priority}:</strong> {action[len(priority)+1:].strip()}</div>\n'
        
        # Quality trends plot
        html += f"""
        <h2>Quality Trends</h2>
        <img src="{plot_path.name}" alt="Quality Trends Plot">
        """
        
        # Per-page summary
        html += """
        <h2>Per-Page Summary</h2>
        <table>
            <tr>
                <th>Page</th>
                <th>Final Chars</th>
                <th>Final Blocks</th>
                <th>Avg Confidence</th>
                <th>Medical Terms</th>
                <th>Quality Issues</th>
            </tr>
        """
        
        for page_num in sorted(evaluation.pages.keys()):
            page_eval = evaluation.pages[page_num]
            stages = list(page_eval.stages.keys())
            
            if stages:
                final_stage = max(stages, key=lambda x: list(self.stage_mapping.keys()).index(x))
                final_metrics = page_eval.stages[final_stage]
                
                issues = []
                if page_num in evaluation.problematic_pages:
                    issues.append("Content Loss")
                if final_metrics.low_confidence_blocks > 0:
                    issues.append(f"{final_metrics.low_confidence_blocks} Low Conf")
                if final_metrics.empty_blocks > 5:
                    issues.append(f"{final_metrics.empty_blocks} Empty Blocks")
                
                row_class = "problematic" if page_num in evaluation.problematic_pages else ""
                
                html += f"""
                <tr class="{row_class}">
                    <td>{page_num}</td>
                    <td>{final_metrics.total_chars:,}</td>
                    <td>{final_metrics.total_blocks}</td>
                    <td>{final_metrics.mean_confidence:.3f}</td>
                    <td>{final_metrics.medical_terms_count}</td>
                    <td>{', '.join(issues) if issues else 'None'}</td>
                </tr>
                """
        
        html += f"""
        </table>
        
        <h2>Detailed Metrics</h2>
        <p>Complete stage-by-stage metrics are available in: <a href="{csv_path.name}">{csv_path.name}</a></p>
        
        <h2>Usage Instructions</h2>
        <div class="metric-box">
            <h4>Interpreting Results:</h4>
            <ul>
                <li><strong>Quality Score:</strong> Composite score (0-1) based on confidence, layout, and medical term preservation</li>
                <li><strong>Content Drop:</strong> Percentage of characters lost through the pipeline (target: &lt;15%)</li>
                <li><strong>Problematic Pages:</strong> Pages with significant quality issues requiring attention</li>
            </ul>
            
            <h4>Next Steps:</h4>
            <ul>
                <li>Review recommended actions above</li>
                <li>For problematic pages, consider manual annotation for ground truth creation</li>
                <li>Use detailed metrics CSV for stage-specific optimization</li>
                <li>Compare different OCR engine configurations using this evaluation framework</li>
            </ul>
        </div>
        
    </div>
</body>
</html>
        """
        
        return html

# ========================= CLI INTERFACE =========================

def main():
    parser = argparse.ArgumentParser(description="OCR Pipeline Quality Assessment")
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory to evaluate")
    parser.add_argument("--pdf-path", help="Original PDF file path")
    parser.add_argument("--ground-truth-dir", help="Directory containing ground truth files")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--output-dir", default="qa_evaluation", help="Output directory for evaluation results")
    
    args = parser.parse_args()
    
    # Initialize evaluator
    evaluator = QAPipelineEvaluator(config_path=args.config)
    evaluator.output_base = Path(args.output_dir)
    
    try:
        # Run evaluation
        evaluation = evaluator.evaluate_pipeline_run(
            run_dir=args.run_dir,
            pdf_path=args.pdf_path,
            ground_truth_dir=args.ground_truth_dir
        )
        
        print(f"\n[COMPLETE] Evaluation completed successfully!")
        print(f"📁 Results saved to: {evaluator.output_base}")
        
    except Exception as e:
        print(f"[ERROR] Evaluation failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()