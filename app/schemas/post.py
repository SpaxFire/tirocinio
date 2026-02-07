from pydantic import BaseModel, Field

class Post(BaseModel):
    id: str
    user: str
    text: str
    verified: bool = False

class PostCreate(BaseModel):
    user: str = Field(..., min_length=1)
    text: str = Field(default="")
    verified: bool = False

class PostUpdate(BaseModel):
    text: str = Field(default="")