from datetime import datetime, timezone
from datetime import timedelta
import jwt
from pwdlib import PasswordHash

SECRET_KEY = "bc20806c2ed551192862145de892574666a63c9a9eac170f5445e635112de204"
ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()

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
