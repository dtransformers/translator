"""
Standardized error response schemas for Swagger/OpenAPI documentation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response wrapper returned by all endpoints on failure."""

    success: bool = Field(False, description="Always false for error responses")
    data: None = Field(None, description="Always null for error responses")
    error: str = Field(..., description="Human-readable error message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "data": None,
                    "error": "Validation error - body.text: field required",
                }
            ]
        }
    }


# --------------------------------------------------------------------- #
#  Reusable response dicts for endpoint `responses` parameter
# --------------------------------------------------------------------- #

ERROR_400: dict = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — invalid input or unsupported language pair",
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "data": None,
                    "error": "Language pair en->jp is not supported",
                }
            }
        },
    }
}

ERROR_404: dict = {
    404: {
        "model": ErrorResponse,
        "description": "Not Found — the requested resource does not exist",
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "data": None,
                    "error": "Brand not found",
                }
            }
        },
    }
}

ERROR_422: dict = {
    422: {
        "model": ErrorResponse,
        "description": "Validation Error — request body failed schema validation",
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "data": None,
                    "error": "Validation error - body.source_lang: field required",
                }
            }
        },
    }
}

ERROR_500: dict = {
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — an unexpected error occurred",
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "data": None,
                    "error": "Internal server error: connection refused",
                }
            }
        },
    }
}

# Combined set for convenience
COMMON_ERRORS = {**ERROR_400, **ERROR_422, **ERROR_500}
CRUD_ERRORS = {**ERROR_404, **ERROR_422, **ERROR_500}
