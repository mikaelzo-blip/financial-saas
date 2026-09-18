"""Run deep evaluation of Current Pipeline (RapidOCR + pypdf + table_extractor) across all 12 benchmark docs."""
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_SRC = REPO_ROOT / "backend"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(Path(__file__).parent))

from ground_truth import GROUND_TRUTH
from harness import CurrentPipelineRunner

DOCS_DIR = Path(__file__).parent / "documents"


def decimal_serializer(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def parse_money(val) -> Decimal | None:
    if val is None:
        return None
    try:
        # Strip currency strings and whitespace
        s = str(val).replace("Rp", "").replace("IDR", "").replace(",", "").strip()
        return Decimal(s)
    except Exception:
        return None


async def evaluate_current():
    runner = CurrentPipelineRunner()
    results = {}

    for doc_key, gt in GROUND_TRUTH.items():
        doc_path = DOCS_DIR / gt["file_name"]
        mime = gt["mime_type"]
        res = await runner.run(doc_path, mime)

        # Evaluate financial matching
        gt_tot = gt.get("total_amount")
        pr_tot = parse_money(res.get("total_amount"))
        tot_ok = (gt_tot == pr_tot) if gt_tot is not None else (pr_tot is None)

        gt_sub = gt.get("subtotal")
        pr_sub = parse_money(res.get("subtotal"))
        sub_ok = (gt_sub == pr_sub) if gt_sub is not None else (pr_sub is None)

        gt_vat = gt.get("vat_amount")
        pr_vat = parse_money(res.get("vat_amount"))
        vat_ok = (gt_vat == pr_vat) if gt_vat is not None else (pr_vat is None)

        # Line items
        gt_items = gt.get("line_items", [])
        pr_items = res.get("line_items", [])
        row_count_ok = (len(gt_items) == len(pr_items))

        # Check item amount matches
        matched_items = 0
        multiline_preserved = 0
        for g in gt_items:
            g_amt = g["amount"]
            for p in pr_items:
                p_amt = parse_money(p.get("amount"))
                if g_amt == p_amt:
                    matched_items += 1
                    if "\n" in g["description"] and "\n" in (p.get("description") or ""):
                        multiline_preserved += 1
                    break

        results[doc_key] = {
            "title": gt["title"],
            "mime_type": mime,
            "latency_ms": res["latency_ms"],
            "document_type": res["document_type"],
            "expected_doc_type": gt["doc_type"],
            "doc_no": res["document_number"],
            "expected_doc_no": gt.get("document_number"),
            "date": res["transaction_date"],
            "expected_date": gt.get("date"),
            "total": str(pr_tot) if pr_tot is not None else None,
            "expected_total": str(gt_tot) if gt_tot is not None else None,
            "total_match": tot_ok,
            "subtotal": str(pr_sub) if pr_sub is not None else None,
            "expected_subtotal": str(gt_sub) if gt_sub is not None else None,
            "subtotal_match": sub_ok,
            "vat": str(pr_vat) if pr_vat is not None else None,
            "expected_vat": str(gt_vat) if gt_vat is not None else None,
            "vat_match": vat_ok,
            "expected_rows": len(gt_items),
            "actual_rows": len(pr_items),
            "row_count_match": row_count_ok,
            "matched_items": matched_items,
            "multiline_preserved": multiline_preserved,
            "raw_text": res["raw_text"],
            "line_items": pr_items,
        }

    return results


if __name__ == "__main__":
    res = asyncio.run(evaluate_current())
    out_file = Path(__file__).parent / "results" / "current_pipeline_detailed.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=decimal_serializer)
    print("Completed Current Pipeline evaluation. Summary:")
    for k, v in res.items():
        print(f"[{k}] {v['latency_ms']}ms | Type: {v['document_type']} | Tot: {v['total']} (Match: {v['total_match']}) | Rows: {v['actual_rows']}/{v['expected_rows']} (Matched: {v['matched_items']})")
