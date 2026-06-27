from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.core.exceptions.custom_exceptions import (
    ResourceNotFoundException,
    ResourceAlreadyExistsException,
    BusinessRuleViolationException,
    ExternalServiceException
)

def register_exception_handlers(app: FastAPI) -> None:
    """
    Binds global application exception handlers directly to the FastAPI instance.
    This safely translates internal domain errors into clean, structured frontend JSON.
    """

    @app.exception_handler(ResourceNotFoundException)
    async def not_found_handler(request: Request, exc: ResourceNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message, "error_code": "RESOURCE_NOT_FOUND"}
        )

    @app.exception_handler(ResourceAlreadyExistsException)
    async def already_exists_handler(request: Request, exc: ResourceAlreadyExistsException):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message, "error_code": "RESOURCE_ALREADY_EXISTS"}
        )

    @app.exception_handler(BusinessRuleViolationException)
    async def business_rule_handler(request: Request, exc: BusinessRuleViolationException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message, "error_code": "BUSINESS_RULE_VIOLATION"}
        )

    @app.exception_handler(ExternalServiceException)
    async def external_service_handler(request: Request, exc: ExternalServiceException):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message, "error_code": "AI_ENGINE_FAILURE"}
        )