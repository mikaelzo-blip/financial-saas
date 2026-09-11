from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str = "BAD_REQUEST",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"entity": entity_name, "identifier": str(identifier)}
        )


class InvariantViolationException(AppException):
    """Raised when an accounting invariant or business rule fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
            error_code="INVARIANT_VIOLATION",
            details=details
        )


class DuplicateEntityException(AppException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_ENTITY",
            details=details
        )


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Authentication required."):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED"
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Insufficient permissions to perform this action.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            details=details
        )


class AuthorizationException(ForbiddenException):
    pass


class TransactionContentionError(AppException):
    """Raised when a database transaction encounters persistent concurrent conflict after bounded retries."""
    def __init__(
        self,
        message: str = "Transaction could not be completed due to persistent concurrent conflict.",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="TRANSACTION_CONTENTION",
            details=details or {},
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on FastAPI app."""
    from src.services.tenant_sequence_allocator import SequenceCollisionError

    @app.exception_handler(TransactionContentionError)
    async def transaction_contention_handler(request: Request, exc: TransactionContentionError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(SequenceCollisionError)
    async def sequence_collision_handler(request: Request, exc: SequenceCollisionError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "error": {
                    "code": "SEQUENCE_COLLISION",
                    "message": "Generated business identifier could not be allocated safely.",
                    "details": {},
                },
            },
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details
                }
            }
        )
