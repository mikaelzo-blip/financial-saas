"""Domain exceptions for document extraction and OCR pipeline."""

class DocumentExtractionError(ValueError):
    """Base exception for document extraction failures (inherits from ValueError for API compatibility)."""
    def __init__(self, message: str, failure_code: str = "EXTRACTION_FAILED"):
        super().__init__(message)
        self.failure_code = failure_code
        self.message = message


class InvalidFileError(DocumentExtractionError):
    """Document is corrupt, password-protected, or unreadable."""
    def __init__(self, message: str = "Invalid or unreadable document file"):
        super().__init__(message, failure_code="INVALID_FILE")


class UnsupportedFileError(DocumentExtractionError):
    """Document format or MIME type is unsupported."""
    def __init__(self, message: str = "Unsupported document file type"):
        super().__init__(message, failure_code="UNSUPPORTED_FILE")


class PdfRenderError(DocumentExtractionError):
    """Failed to rasterize or render PDF page."""
    def __init__(self, message: str = "Failed to render PDF page"):
        super().__init__(message, failure_code="PDF_RENDER_FAILED")


class OcrProcessingError(DocumentExtractionError):
    """OCR engine execution failed."""
    def __init__(self, message: str = "OCR processing failed"):
        super().__init__(message, failure_code="OCR_FAILED")


class ExtractionFailedError(DocumentExtractionError):
    """Structured extraction or parsing failed completely."""
    def __init__(self, message: str = "Document extraction failed"):
        super().__init__(message, failure_code="EXTRACTION_FAILED")


class LowConfidenceError(DocumentExtractionError):
    """Extraction produced results below the acceptable confidence threshold."""
    def __init__(self, message: str = "Extraction confidence below required threshold"):
        super().__init__(message, failure_code="LOW_CONFIDENCE")
