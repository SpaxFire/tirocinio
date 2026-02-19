from typing import Annotated, Union
from fastapi import APIRouter, HTTPException, Request, Form, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import UploadFile, File
from app.services.media import save_post_media

from app.api.routes.auth import require_user_cookie, optional_current_user_cookie
from app.db import user as user_crud
from app.core.config import templates
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
        "posts/feed.html",
        {
            "request": request,
            "posts": posts,
            "next_page": page + 1,
            "has_more": len(posts) == page_size
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
            "has_more": len(comments) == page_size
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
        "posts/feed.html",
        {
            "request": request,
            "posts": likes_posts,
            "next_page": page + 1,
            "has_more": len(likes_posts) == page_size
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
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "users/follow_list.html",
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
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "users/follow_list.html",
            context
        )

    return templates.TemplateResponse(
        "users/profile.html",
        context
    )
