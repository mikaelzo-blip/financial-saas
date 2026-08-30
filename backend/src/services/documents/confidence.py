from decimal import Decimal
from src.schemas.document import ConfidenceScores


def below_threshold(scores: ConfidenceScores, required: tuple[str, ...], threshold: Decimal = Decimal("0.85")) -> bool:
    return any(getattr(scores, field) < threshold for field in required)
