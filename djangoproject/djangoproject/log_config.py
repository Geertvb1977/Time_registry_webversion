import logging
import sys
from loguru import logger as loguru_logger


class InterceptHandler(logging.Handler):
    """Redirect standard logging records to loguru."""

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = loguru_logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        # Find caller frame to show the right source in loguru
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def init_logging(level: str | None = None):
    """Configure loguru and redirect the stdlib logging to it.

    Call early from Django settings to ensure all logs are captured.
    """
    # Remove default handlers and set a clean one
    loguru_logger.remove()
    log_level = level or ("DEBUG" if (sys.argv and "runserver" in " ".join(sys.argv)) else "INFO")
    # Try to add a rich sink with rotation/retention; fall back if the installed
    # Loguru version doesn't support these kwargs (some packaging variants differ).
    try:
        loguru_logger.add(
            sys.stderr,
            level=log_level,
            rotation="10 MB",
            retention="10 days",
            backtrace=True,
            diagnose=False,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )
    except TypeError:
        # Fallback for older/simpler implementations: only specify sink, level and format
        loguru_logger.add(
            sys.stderr,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}",
        )

    # Intercept the standard library logging
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.DEBUG)

    # Optional: quieter loggers
    for name in ("uvicorn.access", "asyncio", "gunicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)

