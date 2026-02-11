from datetime import datetime
from pydantic import BaseModel


class CommentPublic(BaseModel):
    author: str
    text: str
    created_at: datetime
