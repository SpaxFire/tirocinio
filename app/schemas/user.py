from datetime import datetime
from pydantic import BaseModel

class UserBase(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str = "USER"
    bio: str | None = None
    profile_image: str | None = None
    created_at: datetime | None = None
    is_active: bool = True

class UserPublic(UserBase):
    post_count: int = 0
    comment_count: int = 0
    follower_count: int = 0
    following_count: int = 0
    total_likes_received: int = 0
    following_by_me: bool = False

class UserInDB(UserBase):
    password_hash: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str