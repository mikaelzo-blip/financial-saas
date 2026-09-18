"""Benchmark executor: Runs Current OCR vs Baidu Unlimited-OCR on 12 test documents."""
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

# Add backend to sys.path to allow imports without modifying python environment
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_SRC = REPO_ROOT / "backend"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

# Import benchmark modules
sys.path.insert(0, str(Path(__file__).parent))
from ground_truth import GROUND_TRUTH
from harness import CurrentPipelineRunner, UnlimitedOCRRunner

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = Path(__file__).parent / "documents"


def evaluate_document(gt: dict, pred: dict) -> dict:
    """Evaluates prediction against ground truth."""
    # Financial checks
    gt_total = str(gt["total_amount"]) if gt.get("total_amount") is not None else None
    pred_total = pred.get("total_amount")
    total_match = (gt_total == pred_total) if gt_total is not None else (pred_total is None)

    gt_subtotal = str(gt["subtotal"]) if gt.get("subtotal") is not None else None
    pred_subtotal = pred.get("subtotal")
    subtotal_match = (gt_subtotal == pred_subtotal) if gt_subtotal is not None else (pred_subtotal is None)

    gt_vat = str(gt["vat_amount"]) if gt.get("vat_amount") is not None else None
    pred_vat = pred.get("vat_amount")
    vat_match = (gt_vat == pred_vat) if gt_vat is not None else (pred_vat is None)

    # Document number check
    gt_doc_no = gt.get("document_number")
    pred_doc_no = pred.get("document_number")
    doc_no_match = (gt_doc_no in (pred_doc_no or "")) if gt_doc_no else True

    # Line item checks
    gt_items = gt.get("line_items", [])
    pred_items = pred.get("line_items", [])
    row_count_match = len(gt_items) == len(pred_items)

    matched_items = 0
    multiline_preserved = 0
    for g_item in gt_items:
        g_desc = g_item["description"].lower()
        g_amt = str(g_item["amount"])
        for p_item in pred_items:
            p_desc = (p_item.get("description") or "").lower()
            p_amt = str(p_item.get("amount") or "")
            if g_amt == p_amt:
                matched_items += 1
                # Check multiline
                if "\n" in g_item["description"] and "\n" in (p_item.get("description") or ""):
                    multiline_preserved += 1
                break

    item_accuracy = (matched_items / len(gt_items)) if gt_items else 1.0

    return {
        "total_match": total_match,
        "subtotal_match": subtotal_match,
        "vat_match": vat_match,
        "doc_no_match": doc_no_match,
        "row_count_match": row_count_match,
        "expected_rows": len(gt_items),
        "actual_rows": len(pred_items),
        "matched_items": matched_items,
        "multiline_preserved": multiline_preserved,
        "item_accuracy": item_accuracy,
    }


async def main():
    print("=" * 70)
    print("PHASE A — SESSION 3: OCR BENCHMARK (CURRENT OCR vs BAIDU UNLIMITED-OCR)")
    print("=" * 70)

    current_runner = CurrentPipelineRunner()
    unlimited_runner = UnlimitedOCRRunner(mode="base")

    full_results = []

    for doc_key, gt in GROUND_TRUTH.items():
        doc_path = DOCS_DIR / gt["file_name"]
        mime = gt["mime_type"]
        print(f"\nEvaluating: {doc_key} ({gt['title']})...")

        # 1. Run Current Pipeline
        current_res = {}
        try:
            print("  -> Running Current Pipeline (RapidOCR / pypdf)...")
            current_res = await current_runner.run(doc_path, mime)
            current_eval = evaluate_document(gt, current_res)
            print(f"     [Current] {current_res['latency_ms']}ms | Rows: {len(current_res['line_items'])}/{gt['line_items_count']} | Total: {current_res['total_amount']} (Match: {current_eval['total_match']})")
        except Exception as e:
            print(f"     [Current ERROR]: {e}")
            current_res = {"error": str(e), "latency_ms": -1, "line_items": []}
            current_eval = {"error": True}

        # 2. Run Unlimited-OCR Pipeline
        unlimited_res = {}
        try:
            print("  -> Running Baidu Unlimited-OCR (Official ZeroGPU)...")
            unlimited_res = await unlimited_runner.run(doc_path, mime)
            unlimited_eval = evaluate_document(gt, unlimited_res)
            print(f"     [Unlimited-OCR] {unlimited_res['latency_ms']}ms | Rows: {len(unlimited_res['line_items'])}/{gt['line_items_count']} | Total: {unlimited_res['total_amount']} (Match: {unlimited_eval['total_match']})")
        except Exception as e:
            print(f"     [Unlimited-OCR ERROR]: {e}")
            unlimited_res = {"error": str(e), "latency_ms": -1, "line_items": []}
            unlimited_eval = {"error": True}

        full_results.append({
            "doc_key": doc_key,
            "title": gt["title"],
            "ground_truth": {
                k: (str(v) if isinstance(v, Decimal) else v) for k, v in gt.items()
            },
            "current_pipeline": {
                "prediction": current_res,
                "evaluation": current_eval,
            },
            "unlimited_ocr": {
                "prediction": unlimited_res,
                "evaluation": unlimited_eval,
            },
        })

    # Save raw JSON results
    out_json = RESULTS_DIR / "benchmark_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)
    print(f"\nSaved benchmark results to {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
