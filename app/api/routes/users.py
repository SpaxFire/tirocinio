from typing import Annotated, Union
from fastapi import APIRouter, HTTPException, Request, Form, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import UploadFile, File
from app.services.media import save_post_media

from app.api.routes.auth import require_user_cookie, optional_current_user_cookie
from app.db import user as user_crud
from app.core.config import templates
from app.core.security import verify_password, hash_password
from app.schemas.user import UserInDB

router = APIRouter(prefix="/u", tags=["users"])


@router.get("/{username}", response_class=HTMLResponse)
def user_profile_page(username: str, request: Request, current_user: UserInDB | None = Depends(optional_current_user_cookie)):

    user = user_crud.get_user_profile_by_username(username, current_user.id if current_user else None)
    print(user)

    if not user:
        return HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                     hx-get="/empty"
                     hx-trigger="load delay:4s"
                     hx-swap="delete">
                    Utente non trovato
                </div>
            </div>
        """)

    template = (
        "users/partials/profile_content.html"
        if request.headers.get("HX-Request")
        else "users/profile.html"
    )

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "user": user,
        }
    )

@router.post("/{username}/follow")
async def toggle_follow_user(
    request: Request,
    username: str,
    user: UserInDB = Depends(require_user_cookie),
):
    following, follower_count = user_crud.toggle_follow(
        user.id,
        username
    )

    return templates.TemplateResponse(
        "users/partials/follow_button.html",
        {
            "request": request,
            "username": username,
            "following": following,
            "follower_count": follower_count,
        },
    )

@router.get("/{username}/posts", response_class=HTMLResponse)
async def user_posts(
    request: Request,
    username: str,
    page: int = 0,
    page_size: int = 10,
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    skip = page * page_size
    posts = await user_crud.get_user_posts_paginated(username, skip, page_size, user.id if user else None)

    return templates.TemplateResponse(
        "partials/feed.html",
        {
            "request": request,
            "posts": posts,
            "next_page": page + 1,
            "has_more": len(posts) == page_size,
            "pagination_url": f"/u/{username}/posts"
        }
    )

@router.get("/{username}/comments", response_class=HTMLResponse)
async def user_comments(
    request: Request,
    username: str,
    page: int = 0,
    page_size: int = 10,
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    skip = page * page_size

    comments = await user_crud.get_user_comments_paginated(
        username,
        skip,
        page_size,
        user.id if user else None
    )

    return templates.TemplateResponse(
        "users/partials/profile_comments.html",
        {
            "request": request,
            "comments": comments,
            "next_page": page + 1,
            "has_more": len(comments) == page_size,
            "pagination_url": f"/u/{username}/comments"
        }
    )

@router.get("/{username}/likes", response_class=HTMLResponse)
async def user_likes(
    request: Request,
    username: str,
    page: int = 0,
    page_size: int = 10,
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    skip = page * page_size
    likes_posts = await user_crud.get_user_likes_paginated(username, skip, page_size, user.id if user else None)

    return templates.TemplateResponse(
        "partials/feed.html",
        {
            "request": request,
            "posts": likes_posts,
            "next_page": page + 1,
            "has_more": len(likes_posts) == page_size,
            "pagination_url": f"/u/{username}/likes"
        }
    )

@router.get("/{username}/followers", response_class=HTMLResponse)
async def user_followers(
    request: Request,
    username: str,
    page: int = 0,
    page_size: int = 10,
    current_user: UserInDB | None = Depends(optional_current_user_cookie),
):
    skip = page * page_size

    # recupero utente profilo
    profile_user = user_crud.get_user_with_counts(
        username=username,
        my_id=current_user.id if current_user else None
    )

    if not profile_user:
        raise HTTPException(status_code=404)

    # lista followers paginata
    users = user_crud.get_followers_paginated(
        username=username,
        skip=skip,
        limit=page_size,
        my_id=current_user.id if current_user else None
    )

    context = {
        "request": request,
        "user": profile_user,
        "users": users,
        "next_page": page + 1,
        "has_more": len(users) == page_size,
        "active_tab": "followers",
        "list_type": "followers",
        "pagination_url": f"/u/{username}/followers",
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/user_list.html",
            context
        )

    return templates.TemplateResponse(
        "users/profile.html",
        context
    )

@router.get("/{username}/following", response_class=HTMLResponse)
async def user_following(
    request: Request,
    username: str,
    page: int = 0,
    page_size: int = 10,
    current_user: UserInDB | None = Depends(optional_current_user_cookie),
):
    skip = page * page_size

    profile_user = user_crud.get_user_with_counts(
        username=username,
        my_id=current_user.id if current_user else None
    )

    if not profile_user:
        raise HTTPException(status_code=404)

    users = user_crud.get_following_paginated(
        username=username,
        skip=skip,
        limit=page_size,
        my_id=current_user.id if current_user else None
    )

    context = {
        "request": request,
        "user": profile_user,
        "users": users,
        "next_page": page + 1,
        "has_more": len(users) == page_size,
        "active_tab": "following",
        "list_type": "following",
        "pagination_url": f"/u/{username}/following",
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/user_list.html",
            context
        )

    return templates.TemplateResponse(
        "users/profile.html",
        context
    )

@router.get("/{username}/edit-modal", response_class=HTMLResponse)
async def edit_user_modal(
    username: str,
    request: Request,
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    if not user or (user.role != "ADMIN" and user.username != username):
        raise HTTPException(status_code=403)
    
    user = user_crud.get_user_by_username(username)

    return templates.TemplateResponse(
        "users/edit_modal.html",
        {
            "request": request,
            "user": user
        }
    )

@router.post("/{username}/update", response_class=HTMLResponse)
async def update_user(
    username: str,
    request: Request,
    section: str = Form(...),

    # profile
    username_new: str | None = Form(None, alias="username"),
    bio: str | None = Form(None),
    profile_image: UploadFile | None = File(None),

    # email
    email: str | None = Form(None),

    # password
    current_password: str | None = Form(None),
    new_password: str | None = Form(None),
    new_password_confirm: str | None = Form(None),

    current_user: UserInDB | None = Depends(optional_current_user_cookie)
):
    if not current_user or (current_user.role != "ADMIN" and current_user.username != username):
        raise HTTPException(status_code=403)
    
    target_user = user_crud.get_user_by_username(username)

    msg_success = ""
    msg_error = ""

    # ======================
    # SEZIONE PROFILE
    # ======================
    if section == "profile":

        # salva avatar se presente
        if profile_image:
            avatar_url = await save_post_media([profile_image])
            avatar_url = avatar_url[0]
        else:
            avatar_url = target_user.profile_image

        if not username_new or not username_new.strip():
            msg_error = "Username obbligatorio"
        else:
            result = user_crud.update_profile(
                target_user.id,
                username_new.strip(),
                bio.strip() if bio else "",
                avatar_url
            )
            if result:
                msg_success = "Profilo aggiornato"
            else:
                msg_error = "Username già in uso"

    # ======================
    # SEZIONE EMAIL
    # ======================
    elif section == "email":
        if not email:
            msg_error = "Email obbligatoria"
        else:
            result = user_crud.update_email(target_user.id, email)
            if result:
                msg_success = "Email aggiornata"
            else:
                msg_error = "Email già in uso"

    # ======================
    # SEZIONE PASSWORD
    # ======================
    elif section == "password":
        if not new_password:
            msg_error = "Nuova password obbligatoria"

        elif new_password != new_password_confirm:
            msg_error = "Le password non coincidono"
        else:
            # 👤 USER normale → serve password attuale
            if current_user.role != "ADMIN":
                if not current_password:
                    msg_error = "Password attuale obbligatoria"

                elif not verify_password(current_password, target_user.password_hash):
                    msg_error = "Password attuale errata"

            if not msg_error:
                hashed = hash_password(new_password)
                result = user_crud.update_password(target_user.id, hashed)

                if result:
                    msg_success = "Password aggiornata"
                else:
                    msg_error = "Errore durante l'aggiornamento"

    # recupero utente aggiornato
    updated_user = user_crud.get_user_profile_by_username(
        username_new if section == "profile" else username,
        current_user.id
    )

    html = templates.get_template("users/partials/profile_content.html").render(
        {
            "request": request,
            "user": updated_user
        }
    )

    swap = ""
    if msg_success:
        swap = f"""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-success"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                {msg_success}
            </div>
        </div>

        <div id="modal-container" hx-swap-oob="true"></div>

        <div id="profile-wrapper" hx-swap-oob="true">
            {html}
        </div>
        """
    elif msg_error:
        swap = f"""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-danger"
                hx-get="/empty"
                hx-trigger="load delay:4s"
                hx-swap="delete">
                {msg_error}
            </div>
        </div>
        """
    return swap

@router.get("/{username}/delete-modal", response_class=HTMLResponse)
async def delete_confirm_modal(
    username: str,
    request: Request,
    user: UserInDB = Depends(require_user_cookie)
):
    if not user or user.username != username:
        raise HTTPException(status_code=403)

    return templates.TemplateResponse(
        "users/delete_modal.html",
        {
            "request": request,
            "user": user
        }
    )

@router.post("/{username}/delete")
async def delete_user(
    username: str,
    password: str = Form(None),
    user: UserInDB = Depends(require_user_cookie)
):
    if not user or user.username != username:
        raise HTTPException(status_code=403)
    
    if not password:
        return HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                    hx-on::load="setTimeout(() => this.remove(), 4000)">
                    Password obbligatoria
                </div>
            </div>
        """)

    # verifica password
    if not verify_password(password, user.password_hash):
        return HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                    hx-on::load="setTimeout(() => this.remove(), 4000)">
                    Password errata
                </div>
            </div>
        """)

    # soft delete
    user_crud.deactivate_user(user.id)

    # reset completo UI come logout
    response = HTMLResponse("""
        <div id="modal-container" hx-swap-oob="true"></div>
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-success"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                Account eliminato
            </div>
        </div>
        <div id="user-widget" hx-get="/auth/user-widget" hx-trigger="load" hx-swap-oob="true"></div>
    """)

    response.delete_cookie("access_token")

    return response


@router.post("/{username}/validate-password")
async def validate_password(
    new_password: str = Form(...),
    new_password_confirm: str = Form(...)
):
    if new_password != new_password_confirm:
        return HTMLResponse(
            '<p class="text-red-500 text-sm">Le password non coincidono</p>'
        )

    return HTMLResponse(
        '<p class="text-green-500 text-sm">Password OK</p>'
    )
