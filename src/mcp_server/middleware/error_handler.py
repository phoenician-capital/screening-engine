"""
Unified error handling middleware for MCP tool endpoints.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable

from src.shared.types import ToolError, ToolResponse

logger = logging.getLogger(__name__)

# Maps exception types to error codes
ERROR_MAP = {
    "RateLimitError": ("RATE_LIMIT", True),
    "NotFoundError": ("NOT_FOUND", False),
    "TimeoutError": ("TIMEOUT", True),
    "AuthenticationError": ("AUTH_ERROR", False),
    "JSONDecodeError": ("PARSE_FAILURE", False),
    "ValueError": ("PARSE_FAILURE", False),
}


def tool_endpoint(func: Callable) -> Callable:
    """Decorator that wraps tool functions with standardized error handling."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            result = await func(*args, **kwargs)
            return ToolResponse(success=True, data=result).model_dump()
        except Exception as e:
            exc_name = type(e).__name__
            code, retryable = ERROR_MAP.get(exc_name, ("INTERNAL_ERROR", False))

            logger.error(
                "Tool %s failed: [%s] %s", func.__name__, code, str(e),
                exc_info=True,
            )

            return ToolResponse(
                success=False,
                error=ToolError(
                    code=code,
                    message=str(e),
                    retryable=retryable,
                ),
            ).model_dump()

    return wrapper
