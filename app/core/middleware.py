import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.fastapi_config import templates

ACCEPT_JSON = "application/json"
ERROR_TEMPLATE = "error.html"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации"""
    logger.warning(f"Validation error: {exc.errors()}")

    if ACCEPT_JSON in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()}
        )

    return templates.TemplateResponse(
        ERROR_TEMPLATE,
        {
            "request": request,
            "error": "Ошибка валидации данных",
            "details": exc.errors()
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Обработчик ошибок базы данных"""
    logger.error(f"Database error: {str(exc)}")

    if ACCEPT_JSON in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Ошибка базы данных"}
        )

    return templates.TemplateResponse(
        ERROR_TEMPLATE,
        {
            "request": request,
            "error": "Ошибка базы данных",
            "details": "Попробуйте позже"
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def general_exception_handler(request: Request, exc: Exception):
    """Общий обработчик ошибок"""
    logger.exception(f"Unexpected error: {str(exc)}")

    if ACCEPT_JSON in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Внутренняя ошибка сервера"}
        )

    return templates.TemplateResponse(
        ERROR_TEMPLATE,
        {
            "request": request,
            "error": "Внутренняя ошибка сервера",
            "details": "Попробуйте позже"
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def setup_exception_handlers(app):
    """Настройка обработчиков ошибок для приложения"""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
