from pydantic import BaseModel

class UserBase(BaseModel):
    id: str
    username: str
    email: str | None = None

class UserPublic(UserBase):
    bio: str | None = None
    profile_image: str | None = None

class UserInDB(UserBase):
    password_hash: str
    role: str
    is_active: bool

class UserCreate(BaseModel):
    username: str
    email: str
    password: str