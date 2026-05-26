from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid

class DomainRuleSchema(BaseModel):
    creativity: Optional[str] = Field(None, description="e.g., 'low', 'high', 'very_low'")
    preserve_placeholders: Optional[bool] = Field(None, description="Whether to strictly preserve placeholders")
    strict_glossary: Optional[bool] = Field(None, description="Whether to strictly enforce glossary terms")
    brevity_required: Optional[bool] = Field(None, description="Whether translation should be as concise as possible")
    cache_priority: Optional[str] = Field(None, description="e.g., 'high', 'low'")
    tone: Optional[str] = Field(None, description="e.g., 'neutral', 'promotional'")

    class Config:
        extra = "allow"

class DomainBase(BaseModel):
    name: str = Field(..., description="Unique name of the domain (e.g., 'ui', 'marketing')")
    description: Optional[str] = Field(None, description="Description of the domain")
    content_types: Optional[List[str]] = Field(None, description="List of typical content types")
    rules: DomainRuleSchema = Field(..., description="Rules applied to this domain")

class DomainCreate(DomainBase):
    pass

class DomainUpdate(BaseModel):
    description: Optional[str] = None
    content_types: Optional[List[str]] = None
    rules: Optional[DomainRuleSchema] = None

class DomainResponse(DomainBase):
    uuid: uuid.UUID

    model_config = {
        "from_attributes": True
    }
