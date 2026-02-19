from pydantic import BaseModel


class CommentPublic(BaseModel):
    id: str
    author: str
    profile_image: str | None
    text: str
    created_at: str
    post_id : str | None = None
