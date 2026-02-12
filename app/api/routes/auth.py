from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt

from app.core.dependencies import optional_current_user_cookie
from app.core.render import render
from app.schemas.user import UserInDB, UserPublic
from app.schemas.token import Token
from app.db import user as user_crud
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
)
from app.core.config import templates

# ------------------------------------------------------------------

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ------------------------------------------------------------------
# Auth logic
# ------------------------------------------------------------------

def authenticate_user(username: str, password: str) -> UserInDB | None:
    user = user_crud.get_user_by_username(username)

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user

# ------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------

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

    user = user_crud.get_user_by_username(username)

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

    user = user_crud.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401)

    return user

async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
) -> UserInDB:

    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    return current_user

# utilizzato per le azione che richiedono autenticazione, ma non è necessario bloccare l'accesso se il token non è valido (es. like post, commentare)
async def require_user_cookie(
    request: Request,
    user: UserInDB | None = Depends(optional_current_user_cookie),
):
    if not user:
        raise HTTPException(status_code=401)

    return user


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):

    user = authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(access_token=access_token, token_type="bearer")

@router.get("/login/modal", response_class=HTMLResponse)
async def login_modal(request: Request):
    return templates.TemplateResponse(
        "auth/login_modal.html",
        {"request": request},
    )

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "auth/login_page.html",
        {"request": request},
    )

@router.post("/login")
async def login_htmx(
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(username, password)

    # errore → solo messaggio
    if not user:
        return HTMLResponse(
            "<div class='text-red-500'>Credenziali errate</div>"
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    html = HTMLResponse("""
        <div id="modal-container" hx-swap-oob="true"></div>
                        
        <div id="user-widget" hx-get="/auth/user-widget" hx-trigger="load" hx-swap-oob="true"></div>
        <script>window.location.reload()</script>
    """)

    html.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
    )

    return html

@router.get("/register/modal", response_class=HTMLResponse)
async def register_modal(request: Request):
    return templates.TemplateResponse(
        "auth/register_modal.html",
        {"request": request},
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        "auth/register_page.html",
        {"request": request},
    )


@router.post("/register")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    password_hash = hash_password(password)

    user = user_crud.create_user(username, email, password_hash)

    if not user:
        return HTMLResponse(
            "<div class='text-red-500'>Username o email già registrati</div>"
        )

    # mostra direttamente il login modal con messaggio
    return templates.TemplateResponse(
        "auth/login_modal.html",
        {
            "request": request,
            "success_message": "Registrazione completata. Effettua il login."
        },
    )

@router.post("/logout")
async def logout():
    response = HTMLResponse("""
        <script>
            window.location='/';
        </script>
    """)
    response.delete_cookie("access_token")
    return response

@router.get("/auth/user-widget")
async def user_widget(request: Request):
    return await render(request, "components/user_widget.html")

@router.get("/users/me", response_model=UserPublic)
async def read_users_me(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    return current_user
