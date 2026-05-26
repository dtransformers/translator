"""Pydantic schemas for the Brand entity."""

from pydantic import BaseModel, Field
from typing import List, Optional


class BrandBase(BaseModel):
    """Shared brand fields used by create and response schemas."""

    website: Optional[str] = Field(None, description="Brand's primary website URL")
    name: str = Field(..., description="Brand name (must be unique)", min_length=1, max_length=200)
    industry: Optional[str] = Field(None, description="Industry vertical (e.g., 'SaaS', 'E-commerce')")
    summary: Optional[str] = Field(None, description="Short description of the brand's products/services")
    keywords: List[str] = Field(default_factory=list, description="Domain-specific keywords for translation context")
    audience: Optional[str] = Field(None, description="Target audience description (e.g., 'B2B enterprise')")
    entities: List[str] = Field(default_factory=list, description="Named entities that should not be translated")
    tone: Optional[str] = Field(None, description="Desired translation tone (e.g., 'Formal', 'Friendly')")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Acme Corp",
                    "website": "https://acme.example.com",
                    "industry": "Restaurant SaaS",
                    "summary": "Cloud-based POS and ordering platform for restaurants",
                    "keywords": ["POS", "orders", "menu"],
                    "audience": "Restaurant owners and managers",
                    "entities": ["Acme", "OrderFlow"],
                    "tone": "Professional and friendly",
                }
            ]
        }
    }


class BrandCreate(BrandBase):
    """Schema for creating a new brand."""
    pass


class BrandUpdate(BaseModel):
    """Schema for updating an existing brand. All fields are optional."""

    website: Optional[str] = Field(None, description="Brand's primary website URL")
    name: Optional[str] = Field(None, description="Brand name", min_length=1, max_length=200)
    industry: Optional[str] = Field(None, description="Industry vertical")
    summary: Optional[str] = Field(None, description="Short description of the brand")
    keywords: Optional[List[str]] = Field(None, description="Domain-specific keywords")
    audience: Optional[str] = Field(None, description="Target audience description")
    entities: Optional[List[str]] = Field(None, description="Named entities not to translate")
    tone: Optional[str] = Field(None, description="Desired translation tone")


class BrandResponse(BrandBase):
    """Schema returned when reading a brand from the API."""

    id: int = Field(..., description="Internal database ID")
    uuid: str = Field(..., description="Public unique identifier for API references")

    model_config = {"from_attributes": True}
