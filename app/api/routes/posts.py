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

@router.get("", response_class=HTMLResponse)
async def list_posts(
    request: Request,
    hx_request: Annotated[Union[str, None], Header()] = None
):
    records = post_crud.get_all_posts()
    posts = [Post(**r) for r in records]

    if hx_request:
        return templates.TemplateResponse(
            "posts/posts.html", {"request": request, "posts": posts}
        )

    return JSONResponse(content=jsonable_encoder(posts))

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
            <div id="post-success" hx-swap-oob="true"></div>

            <div id="post-errors" hx-swap-oob="true"
                class="text-red-500 text-sm mb-2">
                Il contenuto del post è obbligatorio
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
        <div id="post-errors" hx-swap-oob="true"></div>

        <div id="post-success"
            hx-swap-oob="true"
            hx-get="/posts/empty"
            hx-trigger="load delay:3s"
            hx-swap="outerHTML"
            class="bg-green-100 text-green-700 p-2 rounded mb-2">
            Post pubblicato con successo
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
        <div id="post-success" hx-swap-oob="true"></div>

        <div id="post-errors" hx-swap-oob="true"
             class="text-red-500 text-sm mb-2">
             {str(e)}
        </div>
        """)

@router.get("/empty")
async def empty():
    return HTMLResponse("""<div id="post-success"></div>""")

@router.get("/feed", response_class=HTMLResponse)
async def post_feed(
    request: Request,
    page: int = 0,
    page_size: int = 10
):
    skip = page * page_size
    posts = await post_crud.get_posts_paginated(skip, page_size)

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
    post = post_crud.get_post_by_id(post_id)

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

@router.post("/{post_id}/like")
async def like_post(
    request: Request,
    post_id: str,
    user: UserInDB | None = Depends(require_user_cookie),
):
    post_crud.like_post(post_id, user.username)

    return HTMLResponse("")   # nessun modale


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
