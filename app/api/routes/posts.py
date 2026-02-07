from typing import Annotated, Union
from fastapi import APIRouter, Request, Form, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder

from app.schemas.post import Post, PostCreate, PostUpdate
from app.crud import post as post_crud
from app.crud import comment as comment_crud
from app.core.config import templates

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
            "/posts/posts.html", {"request": request, "posts": posts}
        )

    return JSONResponse(content=jsonable_encoder(posts))

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

@router.get("/posts/{post_id}/comments", response_class=HTMLResponse)
async def get_comments(request: Request, post_id: str):
    comments = await comment_crud.get_all_comments(post_id)

    return templates.TemplateResponse(
        "posts/comments.html",
        {
            "request": request,
            "comments": comments
        }
    )
