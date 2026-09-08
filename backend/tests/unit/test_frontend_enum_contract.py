import re
from pathlib import Path

from src.models.enums import CostCategory, DocumentType, TransactionType


def _typescript_array_values(source: str, constant_name: str) -> list[str]:
    match = re.search(
        rf"export const {constant_name} = \[(.*?)\] as const;",
        source,
        re.DOTALL,
    )
    assert match, f"Missing TypeScript runtime contract: {constant_name}"
    return re.findall(r"'([^']+)'", match.group(1))


def test_frontend_runtime_enums_match_backend_contract() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    frontend_types = (repository_root / "frontend" / "src" / "types" / "api.ts").read_text(
        encoding="utf-8"
    )

    assert _typescript_array_values(frontend_types, "TRANSACTION_TYPES") == [
        member.value for member in TransactionType
    ]
    assert _typescript_array_values(frontend_types, "DOCUMENT_TYPES") == [
        member.value for member in DocumentType
    ]
    assert _typescript_array_values(frontend_types, "COST_CATEGORIES") == [
        member.value for member in CostCategory
    ]
