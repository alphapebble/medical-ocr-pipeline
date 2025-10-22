#!/usr/bin/env python3
"""
Quick QA Check - Run after each notebook stage
==============================================

A lightweight version of the QA evaluator for quick checks after each processing stage.
This script provides immediate feedback on content drops and quality changes.

Usage:
    python quick_qa_check.py --stage 01_blocks --run-dir outputs/run_001
    python quick_qa_check.py --stage 02_cleaned --run-dir outputs/run_001 --compare-with 01_blocks
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
from collections import defaultdict

def extract_page_number(filename: str) -> Optional[int]:
    """Extract page number from filename"""
    match = re.search(r'page_(\d+)', filename)
    return int(match.group(1)) if match else None

def load_stage_data(stage_dir: Path) -> Dict[int, Dict]:
    """Load all JSON files from a stage directory"""
    data = {}
    
    if not stage_dir.exists():
        return data
    
    for json_file in stage_dir.glob("*.json"):
        page_num = extract_page_number(json_file.name)
        if page_num:
            try:
                with open(json_file) as f:
                    blocks = json.load(f)
                    data[page_num] = {
                        'blocks': blocks,
                        'file': json_file.name
                    }
            except Exception as e:
                print(f"Warning: Could not load {json_file}: {e}")
    
    return data

def analyze_blocks(blocks: List[Dict]) -> Dict:
    """Analyze a list of blocks for content metrics"""
    if not blocks:
        return {
            'total_chars': 0,
            'total_words': 0,
            'total_blocks': 0,
            'empty_blocks': 0,
            'mean_confidence': 0.0,
            'low_confidence_blocks': 0,
            'total_area': 0.0
        }
    
    all_text = ""
    confidences = []
    empty_count = 0
    total_area = 0.0
    
    for block in blocks:
        text = block.get("text", "").strip()
        all_text += text + " "
        
        if not text:
            empty_count += 1
        
        if "confidence" in block:
            confidences.append(block["confidence"])
        
        # Calculate bbox area if available
        if "bbox" in block and len(block["bbox"]) == 4:
            x0, y0, x1, y1 = block["bbox"]
            area = max(0, (x1 - x0) * (y1 - y0))
            total_area += area
    
    words = all_text.split()
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    low_conf = sum(1 for c in confidences if c < 0.7) if confidences else 0
    
    return {
        'total_chars': len(all_text.strip()),
        'total_words': len(words),
        'total_blocks': len(blocks),
        'empty_blocks': empty_count,
        'mean_confidence': mean_conf,
        'low_confidence_blocks': low_conf,
        'total_area': total_area
    }

def compare_stages(before_data: Dict, after_data: Dict) -> Dict:
    """Compare metrics between two stages"""
    
    def get_stage_totals(data):
        totals = defaultdict(int)
        totals['mean_confidence'] = []
        totals['total_area'] = 0.0
        
        for page_data in data.values():
            metrics = analyze_blocks(page_data['blocks'])
            totals['total_chars'] += metrics['total_chars']
            totals['total_words'] += metrics['total_words'] 
            totals['total_blocks'] += metrics['total_blocks']
            totals['empty_blocks'] += metrics['empty_blocks']
            totals['low_confidence_blocks'] += metrics['low_confidence_blocks']
            totals['total_area'] += metrics['total_area']
            
            if metrics['mean_confidence'] > 0:
                totals['mean_confidence'].append(metrics['mean_confidence'])
        
        # Average confidence across pages
        if totals['mean_confidence']:
            totals['mean_confidence'] = sum(totals['mean_confidence']) / len(totals['mean_confidence'])
        else:
            totals['mean_confidence'] = 0.0
            
        return dict(totals)
    
    before_totals = get_stage_totals(before_data)
    after_totals = get_stage_totals(after_data)
    
    # Calculate changes
    changes = {}
    for key in before_totals:
        if key == 'mean_confidence':
            changes[f'{key}_change'] = after_totals[key] - before_totals[key]
        else:
            before_val = before_totals[key]
            after_val = after_totals[key]
            changes[f'{key}_change'] = after_val - before_val
            changes[f'{key}_change_pct'] = ((after_val - before_val) / max(before_val, 1)) * 100
    
    return {
        'before': before_totals,
        'after': after_totals,
        'changes': changes
    }

def print_stage_summary(stage_name: str, data: Dict):
    """Print summary for a single stage"""
    print(f"\n📊 Stage: {stage_name}")
    print("=" * 40)
    
    if not data:
        print("❌ No data found")
        return
    
    total_metrics = defaultdict(int)
    confidence_values = []
    
    print(f"📑 Pages found: {len(data)}")
    
    for page_num, page_data in sorted(data.items()):
        metrics = analyze_blocks(page_data['blocks'])
        
        total_metrics['total_chars'] += metrics['total_chars']
        total_metrics['total_words'] += metrics['total_words']
        total_metrics['total_blocks'] += metrics['total_blocks']
        total_metrics['empty_blocks'] += metrics['empty_blocks']
        total_metrics['low_confidence_blocks'] += metrics['low_confidence_blocks']
        
        if metrics['mean_confidence'] > 0:
            confidence_values.append(metrics['mean_confidence'])
    
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0
    
    print(f"📝 Total characters: {total_metrics['total_chars']:,}")
    print(f"📄 Total words: {total_metrics['total_words']:,}")
    print(f"🧱 Total blocks: {total_metrics['total_blocks']:,}")
    print(f"📊 Average confidence: {avg_confidence:.3f}")
    print(f"⚠️  Low confidence blocks: {total_metrics['low_confidence_blocks']}")
    print(f"❌ Empty blocks: {total_metrics['empty_blocks']}")

def print_comparison(before_stage: str, after_stage: str, comparison: Dict):
    """Print comparison between two stages"""
    print(f"\n🔄 Comparison: {before_stage} → {after_stage}")
    print("=" * 50)
    
    changes = comparison['changes']
    
    # Character changes
    char_change = changes['total_chars_change']
    char_change_pct = changes['total_chars_change_pct']
    
    if char_change >= 0:
        char_icon = "📈"
        char_direction = "increased"
    else:
        char_icon = "📉"
        char_direction = "decreased"
    
    print(f"{char_icon} Characters {char_direction}: {char_change:+,} ({char_change_pct:+.1f}%)")
    
    # Word changes
    word_change = changes['total_words_change']
    word_change_pct = changes['total_words_change_pct']
    
    if word_change >= 0:
        word_icon = "📈"
        word_direction = "increased"
    else:
        word_icon = "📉"
        word_direction = "decreased"
    
    print(f"{word_icon} Words {word_direction}: {word_change:+,} ({word_change_pct:+.1f}%)")
    
    # Block changes
    block_change = changes['total_blocks_change']
    block_change_pct = changes['total_blocks_change_pct']
    
    print(f"🧱 Blocks changed: {block_change:+,} ({block_change_pct:+.1f}%)")
    
    # Confidence changes
    conf_change = changes['mean_confidence_change']
    if abs(conf_change) > 0.001:  # Only show if meaningful change
        conf_icon = "📈" if conf_change > 0 else "📉"
        print(f"{conf_icon} Confidence changed: {conf_change:+.3f}")
    
    # Quality assessment
    print("\n🎯 Quality Assessment:")
    
    # Content loss assessment
    if abs(char_change_pct) < 5:
        print("   ✅ Content change: Minimal (<5%)")
    elif abs(char_change_pct) < 15:
        print("   🟡 Content change: Moderate (5-15%)")
    else:
        print("   🔴 Content change: Significant (>15%)")
    
    # Block efficiency
    if block_change < 0 and char_change >= 0:
        print("   ✅ Block efficiency: Improved (fewer blocks, same/more content)")
    elif block_change > 0 and char_change <= 0:
        print("   ⚠️  Block efficiency: Decreased (more blocks, same/less content)")
    
    # Empty blocks
    empty_change = changes['empty_blocks_change']
    if empty_change < 0:
        print("   ✅ Empty blocks: Reduced")
    elif empty_change > 5:
        print("   ⚠️  Empty blocks: Increased significantly")

def quick_qa_check(run_dir: str, stage: str, compare_with: Optional[str] = None):
    """Run quick QA check for a stage"""
    
    run_path = Path(run_dir)
    if not run_path.exists():
        print(f"❌ Run directory not found: {run_dir}")
        return
    
    stage_path = run_path / stage
    if not stage_path.exists():
        print(f"❌ Stage directory not found: {stage_path}")
        available_stages = [d.name for d in run_path.iterdir() if d.is_dir() and d.name.startswith(('01', '02', '03', '04', '05'))]
        print(f"Available stages: {available_stages}")
        return
    
    print(f"🔍 Quick QA Check - {run_path.name}")
    print(f"📁 Stage: {stage}")
    
    # Load current stage data
    current_data = load_stage_data(stage_path)
    print_stage_summary(stage, current_data)
    
    # Comparison with previous stage if requested
    if compare_with:
        compare_path = run_path / compare_with
        if compare_path.exists():
            previous_data = load_stage_data(compare_path)
            comparison = compare_stages(previous_data, current_data)
            print_comparison(compare_with, stage, comparison)
        else:
            print(f"⚠️  Comparison stage not found: {compare_with}")
    
    # Quick recommendations
    if current_data:
        print("\n💡 Quick Recommendations:")
        
        # Calculate overall metrics for recommendations
        total_chars = sum(analyze_blocks(pd['blocks'])['total_chars'] for pd in current_data.values())
        total_blocks = sum(analyze_blocks(pd['blocks'])['total_blocks'] for pd in current_data.values())
        empty_blocks = sum(analyze_blocks(pd['blocks'])['empty_blocks'] for pd in current_data.values())
        low_conf_blocks = sum(analyze_blocks(pd['blocks'])['low_confidence_blocks'] for pd in current_data.values())
        
        if total_chars < 1000:
            print("   ⚠️  Very low character count - check OCR parameters")
        
        if empty_blocks > total_blocks * 0.2:
            print("   🔴 High empty block ratio (>20%) - review block filtering")
        
        if low_conf_blocks > total_blocks * 0.3:
            print("   🔴 High low-confidence ratio (>30%) - tune confidence thresholds")
        
        if compare_with and 'changes' in locals():
            char_loss = comparison['changes']['total_chars_change_pct']
            if char_loss < -20:
                print("   🚨 Significant content loss (>20%) - review processing logic")
            elif char_loss < -10:
                print("   ⚠️  Moderate content loss (>10%) - monitor closely")
    
    print(f"\n✅ Quick QA check completed for {stage}")
    print(f"💡 For detailed analysis, run: python qa_pipeline_evaluator.py --run-dir {run_dir}")

def main():
    parser = argparse.ArgumentParser(description="Quick QA check after each pipeline stage")
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory")
    parser.add_argument("--stage", required=True, help="Stage directory to check (e.g., 01_blocks, 02_cleaned)")
    parser.add_argument("--compare-with", help="Previous stage to compare with (e.g., 01_blocks)")
    
    args = parser.parse_args()
    
    quick_qa_check(args.run_dir, args.stage, args.compare_with)

if __name__ == "__main__":
    main()