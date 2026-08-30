from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Protocol

from src.core.config import settings
from src.models.enums import DocumentType
from src.schemas.document import ConfidenceScores, StructuredExtraction


@dataclass(frozen=True)
class ExtractionResult:
    document_type: DocumentType
    data: StructuredExtraction
    confidence: ConfidenceScores
    provider_name: str
    provider_version: str


class ExtractionProvider(Protocol):
    async def extract(self, path: Path, mime_type: str) -> ExtractionResult: ...


ExtractionProviderFactory = Callable[[], ExtractionProvider]
_provider_factories: dict[str, ExtractionProviderFactory] = {}


def register_extraction_provider(name: str, factory: ExtractionProviderFactory) -> None:
    """Register a replaceable extraction provider without coupling callers to it."""
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("Extraction provider name is required")
    _provider_factories[normalized_name] = factory


def get_extraction_provider(name: str | None = None) -> ExtractionProvider:
    """Create the configured provider at the processing boundary."""
    provider_name = (name or settings.DOCUMENT_EXTRACTION_PROVIDER).strip().lower()
    if provider_name == "local":
        # Keep the default local implementation lazily imported so provider
        # contracts remain independent of OCR/LLM implementation details.
        from src.services.documents.local_provider import LocalExtractionProvider

        return LocalExtractionProvider()
    try:
        return _provider_factories[provider_name]()
    except KeyError as exc:
        raise ValueError(f"Unsupported document extraction provider: {provider_name}") from exc


def empty_confidence() -> ConfidenceScores:
    return ConfidenceScores(ocr_confidence=Decimal("0"), document_type_confidence=Decimal("0"),
        entity_confidence=Decimal("0"), project_confidence=Decimal("0"), amount_confidence=Decimal("0"))


class ScriptedExtractionProvider:
    """Deterministic provider for tests and controlled local fixtures."""
    def __init__(self, result: ExtractionResult): self.result = result
    async def extract(self, path: Path, mime_type: str) -> ExtractionResult: return self.result
