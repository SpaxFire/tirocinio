from fastapi import Cookie
import jwt

from app.core.security import SECRET_KEY, ALGORITHM
from app.db import user as user_crud
from app.schemas.user import UserInDB

# utilizzato per le pagine che possono essere viste sia da autenticati che da guest
async def optional_current_user_cookie(
    access_token: str | None = Cookie(default=None),
) -> UserInDB | None:
    if not access_token:
        return None
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        return user_crud.get_user_by_username(username)
    except Exception:
        return None