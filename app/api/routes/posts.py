from typing import Annotated, Union
from fastapi import APIRouter, HTTPException, Request, Form, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import UploadFile, File
from app.services.media import save_post_media

from app.api.routes.auth import require_user_cookie, optional_current_user_cookie
from app.schemas.post import Post, PostCreate, PostUpdate
from app.db import post as post_crud
from app.db import comment as comment_crud
from app.core.config import templates
from app.schemas.user import UserInDB

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("/create-box")
async def create_post_box(request: Request):
    return templates.TemplateResponse(
        "posts/partials/create_post_box.html",
        {
            "request": request,
        },
    )

@router.post("/create")
async def create_post(
    request: Request,
    content: str = Form(""),
    categories: str | None = Form(None),
    media: list[UploadFile] | None = File(None),
    user: UserInDB = Depends(require_user_cookie),
):
    try:
        if not content.strip():
            return HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                    hx-get="/empty"
                    hx-trigger="load delay:4s"
                    hx-swap="delete">
                    Il contenuto del post è obbligatorio
                </div>
            </div>
            """)

        category_list = []
        if categories:
            category_list = [c.strip() for c in categories.split(",") if c.strip()]

        media_urls = await save_post_media(media)

        post_crud.create_post(
            username=user.username,
            content=content,
            categories=category_list,
            media_urls=media_urls,
        )

        return HTMLResponse("""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-success"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                Post pubblicato con successo
            </div>
        </div>
                                    
        <div id="feed"
            hx-get="/posts/feed"
            hx-trigger="load"
            hx-swap="innerHTML"
            hx-swap-oob="true">
        </div>
        """)



    except Exception as e:
        return HTMLResponse(f"""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-danger"
                hx-get="/empty"
                hx-trigger="load delay:4s"
                hx-swap="delete">
                {str(e)}
            </div>
        </div>
        """)

@router.get("/feed", response_class=HTMLResponse)
async def post_feed(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    skip = page * page_size
    posts = await post_crud.get_posts_paginated(skip, page_size, user.id if user else None)

    return templates.TemplateResponse(
        "posts/feed.html",
        {
            "request": request,
            "posts": posts,
            "next_page": page + 1,
            "has_more": len(posts) == page_size
        }
    )

@router.get("/{post_id}", response_class=HTMLResponse)
async def post_detail(
    request: Request,
    post_id: str,
    user: UserInDB | None = Depends(optional_current_user_cookie),
    hx_request: Annotated[Union[str, None], Header()] = None,
):
    post = post_crud.get_post_by_id(post_id, user.id if user else None)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    template = "posts/partials/detail_content.html" if hx_request else "posts/detail.html"

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "post": post,
            "user": user,
            "is_authenticated": user is not None,
        },
    )

@router.post("/{post_id}/likes")
async def like_post(
    request: Request,
    post_id: str,
    user: UserInDB = Depends(require_user_cookie),
):
    liked, like_count = post_crud.toggle_like(post_id, user.username)

    return templates.TemplateResponse(
        "posts/partials/like_button.html",
        {
            "request": request,
            "post_id": post_id,
            "liked": liked,
            "like_count": like_count,
        },
    )

@router.get("/{post_id}/comment-form")
async def comment_form(
    request: Request,
    post_id: str,
    user: UserInDB | None = Depends(require_user_cookie),
):

    return templates.TemplateResponse(
        "comments/comment_form_modal.html",
        {"request": request, "post_id": post_id},
    )



@router.get("/{post_id}/comments", response_class=HTMLResponse)
async def get_comments(request: Request, post_id: str):
    comments = await comment_crud.get_comments_of_post(post_id)

    return templates.TemplateResponse(
        "posts/comments.html",
        {
            "request": request,
            "comments": comments
        }
    )
