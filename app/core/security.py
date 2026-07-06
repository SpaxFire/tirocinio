from datetime import datetime, timezone
from datetime import timedelta
from typing import Annotated
from fastapi import Cookie, Depends, HTTPException, Request, status
import jwt
from pwdlib import PasswordHash
from fastapi.security import OAuth2PasswordBearer

from app.schemas.user import UserInDB
from app.db import user as user_db

SECRET_KEY = "bc20806c2ed551192862145de892574666a63c9a9eac170f5445e635112de204"
ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------

def authenticate_user(username: str, password: str) -> UserInDB | None:
    user = user_db.get_user_by_username(username)

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserInDB:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    user = user_db.get_user_by_username(username)

    if user is None:
        raise credentials_exception

    return user

async def get_current_user_cookie(
    access_token: str | None = Cookie(default=None),
) -> UserInDB:
    if not access_token:
        raise HTTPException(status_code=401)

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401)

    user = user_db.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401)

    return user

async def get_current_active_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    access_token: str | None = Cookie(default=None),
) -> UserInDB:
    if access_token:
        current_user = await get_current_user_cookie(access_token)
    else:
        current_user = await get_current_user(token or "")

    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    return current_user

async def optional_current_user_cookie(
    access_token: str | None = Cookie(default=None),
) -> UserInDB | None:
    if not access_token:
        return None
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        return user_db.get_user_by_username(username)
    except Exception:
        return None

# utilizzato per le azione che richiedono autenticazione, ma non è necessario bloccare l'accesso se il token non è valido (es. like post, commentare)
async def require_user_cookie(
    user: UserInDB | None = Depends(optional_current_user_cookie),
):
    if not user:
        raise HTTPException(status_code=401)

    return user

# ---------------- Password ----------------

def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


def hash_password(password: str) -> str:
    return password_hash.hash(password)

# ---------------- JWT ----------------

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
