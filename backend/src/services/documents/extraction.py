from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Protocol

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
    raw_payload: Dict[str, Any] = field(default_factory=dict)


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


class FallbackExtractionProvider:
    """Combines local extraction with optional cloud vision fallback.

    Adheres strictly to the principle: local extraction first.
    Cloud fallback is only triggered if:
    1. settings.DOCUMENT_CLOUD_FALLBACK_ENABLED is True;
    2. Cloud credentials are configured;
    3. Local extraction fails or produces confidence below threshold.
    """
    def __init__(
        self,
        primary_provider: ExtractionProvider,
        fallback_threshold: float = 0.70,
    ):
        self.primary = primary_provider
        self.fallback_threshold = Decimal(str(fallback_threshold))

    async def extract(self, path: Path, mime_type: str) -> ExtractionResult:
        primary_result: ExtractionResult | None = None
        primary_error: Exception | None = None

        try:
            primary_result = await self.primary.extract(path, mime_type)
        except Exception as exc:
            primary_error = exc

        # Check if fallback is warranted and possible
        needs_fallback = False
        if primary_error is not None:
            needs_fallback = True
        elif primary_result is not None:
            overall_conf = primary_result.confidence.ocr_confidence
            if overall_conf < self.fallback_threshold:
                needs_fallback = True

        can_fallback = (
            settings.DOCUMENT_CLOUD_FALLBACK_ENABLED
            and bool(settings.DOCUMENT_EXTRACTION_API_KEY)
        )

        if needs_fallback and can_fallback:
            try:
                from src.services.documents.cloud_vision_provider import CloudVisionExtractionProvider
                cloud = CloudVisionExtractionProvider()
                cloud_result = await cloud.extract(path, mime_type)
                # Annotate that fallback succeeded
                cloud_result.raw_payload["cloud_fallback_triggered"] = True
                cloud_result.raw_payload["primary_provider"] = "local"
                return cloud_result
            except Exception:
                # If cloud fails, fall back to returning primary result or raising primary error
                pass

        if primary_error is not None:
            raise primary_error
        return primary_result


def get_extraction_provider(name: str | None = None) -> ExtractionProvider:
    """Create the configured provider at the processing boundary."""
    provider_name = (name or settings.DOCUMENT_EXTRACTION_PROVIDER).strip().lower()
    if provider_name == "local":
        # Keep the default local implementation lazily imported so provider
        # contracts remain independent of OCR/LLM implementation details.
        from src.services.documents.local_provider import LocalExtractionProvider

        local = LocalExtractionProvider()
        if settings.DOCUMENT_CLOUD_FALLBACK_ENABLED:
            return FallbackExtractionProvider(
                primary_provider=local,
                fallback_threshold=settings.DOCUMENT_CLOUD_FALLBACK_THRESHOLD,
            )
        return local
    if provider_name in {"openai_vision", "gemini_vision", "cloud_vision"}:
        from src.services.documents.cloud_vision_provider import CloudVisionExtractionProvider

        return CloudVisionExtractionProvider(provider_type=provider_name)
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
