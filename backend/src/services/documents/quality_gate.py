"""Text quality gate to evaluate whether native extracted text from a PDF page
is sufficiently rich and readable, or if rasterization and OCR fallback is required.
"""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class TextQualityResult:
    is_sufficient: bool
    char_count: int
    meaningful_token_count: int
    printable_ratio: float
    whitespace_ratio: float
    abnormal_control_chars: int
    reason: str


def evaluate_page_text_quality(
    text: str | None,
    min_chars: int = 35,
    min_tokens: int = 5,
    min_printable_ratio: float = 0.85,
    max_whitespace_ratio: float = 0.70,
    max_control_chars: int = 5,
) -> TextQualityResult:
    """Evaluates whether native page text is sufficient or if OCR fallback should be invoked.

    Deterministic heuristic check considering character volume, whitespace distribution,
    printable glyph density, and absence of excessive control characters or font encoding corruption.
    """
    if not text or not text.strip():
        return TextQualityResult(
            is_sufficient=False,
            char_count=0,
            meaningful_token_count=0,
            printable_ratio=0.0,
            whitespace_ratio=1.0,
            abnormal_control_chars=0,
            reason="Empty or whitespace-only text",
        )

    clean = text.strip()
    char_count = len(clean)

    # Count control characters (excluding standard \n, \r, \t)
    control_chars = sum(
        1 for c in clean
        if unicodedata.category(c).startswith("C") and c not in ("\n", "\r", "\t")
    )

    # Printable ratio
    printable_count = sum(1 for c in clean if c.isprintable() or c in ("\n", "\r", "\t"))
    printable_ratio = printable_count / max(char_count, 1)

    # Whitespace ratio
    whitespace_count = sum(1 for c in clean if c.isspace())
    whitespace_ratio = whitespace_count / max(char_count, 1)

    # Meaningful tokens: alphanumeric words with at least 2 characters
    meaningful_tokens = re.findall(r"\b[a-zA-Z0-9]{2,}\b", clean)
    token_count = len(meaningful_tokens)

    # Evaluation gates
    if control_chars > max_control_chars:
        return TextQualityResult(
            is_sufficient=False,
            char_count=char_count,
            meaningful_token_count=token_count,
            printable_ratio=printable_ratio,
            whitespace_ratio=whitespace_ratio,
            abnormal_control_chars=control_chars,
            reason=f"Excessive control characters ({control_chars} > {max_control_chars})",
        )

    if printable_ratio < min_printable_ratio:
        return TextQualityResult(
            is_sufficient=False,
            char_count=char_count,
            meaningful_token_count=token_count,
            printable_ratio=printable_ratio,
            whitespace_ratio=whitespace_ratio,
            abnormal_control_chars=control_chars,
            reason=f"Low printable character ratio ({printable_ratio:.2f} < {min_printable_ratio:.2f})",
        )

    if char_count < min_chars:
        return TextQualityResult(
            is_sufficient=False,
            char_count=char_count,
            meaningful_token_count=token_count,
            printable_ratio=printable_ratio,
            whitespace_ratio=whitespace_ratio,
            abnormal_control_chars=control_chars,
            reason=f"Character count too low ({char_count} < {min_chars})",
        )

    if token_count < min_tokens:
        return TextQualityResult(
            is_sufficient=False,
            char_count=char_count,
            meaningful_token_count=token_count,
            printable_ratio=printable_ratio,
            whitespace_ratio=whitespace_ratio,
            abnormal_control_chars=control_chars,
            reason=f"Meaningful token count too low ({token_count} < {min_tokens})",
        )

    if whitespace_ratio > max_whitespace_ratio:
        return TextQualityResult(
            is_sufficient=False,
            char_count=char_count,
            meaningful_token_count=token_count,
            printable_ratio=printable_ratio,
            whitespace_ratio=whitespace_ratio,
            abnormal_control_chars=control_chars,
            reason=f"Excessive whitespace ratio ({whitespace_ratio:.2f} > {max_whitespace_ratio:.2f})",
        )

    return TextQualityResult(
        is_sufficient=True,
        char_count=char_count,
        meaningful_token_count=token_count,
        printable_ratio=printable_ratio,
        whitespace_ratio=whitespace_ratio,
        abnormal_control_chars=control_chars,
        reason="Native text quality sufficient",
    )
