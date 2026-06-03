from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Indicates if the request was successful")
    data: Optional[T] = Field(None, description="The response data payload if successful")
    error: Optional[str] = Field(None, description="Error message if the request failed")
