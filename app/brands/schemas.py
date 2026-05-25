from pydantic import BaseModel, Field
from typing import List, Optional

class BrandBase(BaseModel):
    website: Optional[str] = None
    name: str
    industry: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    audience: Optional[str] = None
    entities: List[str] = Field(default_factory=list)
    tone: Optional[str] = None

class BrandCreate(BrandBase):
    pass

class BrandUpdate(BaseModel):
    website: Optional[str] = None
    name: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    audience: Optional[str] = None
    entities: Optional[List[str]] = None
    tone: Optional[str] = None

class BrandResponse(BrandBase):
    id: int
    uuid: str

    model_config = {"from_attributes": True}
