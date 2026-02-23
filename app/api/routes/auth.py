from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.user import UserInDB, UserPublic
from app.schemas.token import Token
from app.db import user as user_db
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    get_current_active_user,
    hash_password,
    create_access_token,
    )
from app.core.config import templates


router = APIRouter(tags=["auth"])

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
    next: str = Form("/")
):
    user = authenticate_user(username, password)

    # errore → solo messaggio
    if not user:
        return HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                    hx-on::load="setTimeout(() => this.remove(), 4000)">
                    Credenziali errate
                </div>
            </div>
        """)
    
    if not user.is_active:
        return HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                    hx-on::load="setTimeout(() => this.remove(), 4000)">
                    Utente non attivo
                </div>
            </div>
        """)


    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    response = Response(status_code=204)
    response.headers["HX-Refresh"] = "true"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
    )

    return response

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

    user = user_db.create_user(username, email, password_hash)

    # l'eliminazione del messaggio di errore è gestita direttamente nel template del modal tramite hx-on:load,
    # senza usare l'endpoint di empty come per gli altri modali (a scopo dimostrativo di un approccio alternativo)
    if not user:
        return HTMLResponse("""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-danger"
                hx-on::load="setTimeout(() => this.remove(), 4000)">
                Username o email già registrati
            </div>
        </div>
        """)

    # mostra direttamente il login modal con messaggio
    html = templates.get_template("auth/login_modal.html").render(
        request=request,
        success_message="Registrazione completata. Effettua il login."
    )

    return HTMLResponse(f"""
    <div id="modal-container" hx-swap-oob="innerHTML">
    {html}
    </div>
    """)


@router.post("/logout")
async def logout():
    response = Response(status_code=204)
    response.headers["HX-Refresh"] = "true"
    response.delete_cookie("access_token")
    return response

@router.get("/auth/user-widget", response_class=HTMLResponse)
async def user_widget(request: Request):
    """
    Widget utente flottante in basso a sinistra:
    - se autenticato → mostra avatar e logout
    - se guest → mostra pulsante login
    """
    return templates.TemplateResponse(
        "components/user_widget.html",
        {"request": request}
    )


@router.get("/users/me", response_model=UserPublic)
async def read_users_me(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    return current_user
