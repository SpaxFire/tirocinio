from typing import Annotated, Union
from fastapi import APIRouter, HTTPException, Request, Form, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi import UploadFile, File
from app.services.media import save_post_media

from app.core.security import require_user_cookie, optional_current_user_cookie
from app.db import post as post_db
from app.core.config import templates
from app.schemas.user import UserInDB
from app.services.mqtt_client import mqtt_notification_client

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
            # l'eliminazione del messaggio di errore è gestita usando l'endpoint di empty
            # per dimostrare un approccio alternativo a quello usato nel modale di auth
            # (dove invece l'eliminazione è gestita tramite hx-on:load direttamente nel template)
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

        created_post = post_db.create_post(
            username=user.username,
            content=content,
            categories=category_list,
            media_urls=media_urls,
        )

        # Pubblicazione della notifica di creazione del post tramite MQTT
        mqtt_notification_client.publish(
            {
                "type": "post_created",
                "author": user.username,
                "content": content,
                "post_id": created_post.get("id"),
            }
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
    
@router.get("/{post_id}/edit-modal", response_class=HTMLResponse)
async def edit_post_modal(
    post_id: str,
    request: Request,
    source: str = "feed",
    user: UserInDB = Depends(require_user_cookie)
):
    post = post_db.get_post_by_id(post_id, user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post non trovato")

    # controllo che l'utente sia l'autore del post o un admin
    if not user or (user.username != post["author"] and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    return templates.TemplateResponse(
        "posts/edit_modal.html",
        {
            "request": request,
            "post": post,
            "source": source
        }
    )

@router.post("/{post_id}/update", response_class=HTMLResponse)
async def update_post(
    post_id: str,
    request: Request,
    content: str = Form(""),
    media: list[UploadFile] | None = File(None),
    existing_media: str = Form(""),
    categories: str = Form(""),
    source: str = Form("feed"),
    user: UserInDB = Depends(require_user_cookie)
):
    post = post_db.get_post_by_id(post_id, user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post non trovato")

    # controllo che l'utente sia l'autore del post o un admin
    if not user or (user.username != post["author"] and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")
    
    if not content.strip():
            # l'eliminazione del messaggio di errore è gestita usando l'endpoint di empty
            # per dimostrare un approccio alternativo a quello usato nel modale di auth
            # (dove invece l'eliminazione è gestita tramite hx-on:load direttamente nel template)
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

    categories_list = [c.strip() for c in categories.split(",") if c.strip()]

    existing_media_list = [
        m.strip() for m in existing_media.split(",") if m.strip()
    ]

    if media:
        try:
            new_media_urls = await save_post_media(media)
        except HTTPException as e:
            return HTMLResponse(f"""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-danger"
                    hx-get="/empty"
                    hx-trigger="load delay:4s"
                    hx-swap="delete">
                    {e.detail}
                </div>
            </div>
            """)
    else:
        new_media_urls = []

    media_urls = existing_media_list + new_media_urls

    post_db.update_post(post_id, content, categories_list, media_urls)

    updated_post = post_db.get_post_by_id(post_id, user.id)

    # render corretto in base alla provenienza
    if source == "detail":
        html = templates.get_template("posts/partials/detail_content.html").render(
            {"request": request, "post": updated_post, "user": user}
        )

        return HTMLResponse(
            f"""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-success"
                    hx-get="/empty"
                    hx-trigger="load delay:3s"
                    hx-swap="delete">
                    Post modificato con successo
                </div>
            </div>

            <div id="modal-container" hx-swap-oob="true"></div>
            <div id="post-detail" hx-swap-oob="true">
                {html}
            </div>
            """
        )

    else:  # feed
        html = templates.get_template("posts/partials/post_card.html").render(
            {"request": request, "post": updated_post}
        )

        return HTMLResponse(
            f"""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-success"
                    hx-get="/empty"
                    hx-trigger="load delay:3s"
                    hx-swap="delete">
                    Post modificato con successo
                </div>
            </div>

            <div id="modal-container" hx-swap-oob="true"></div>
            <div id="post-{post_id}" hx-swap-oob="true">
                {html}
            </div>
            """
        )


# MODALE DELETE
@router.get("/{post_id}/delete-modal", response_class=HTMLResponse)
async def delete_post_modal(
    post_id: str,
    request: Request,
    source: str = "feed",
    user: UserInDB = Depends(require_user_cookie)
):
    post = post_db.get_post_by_id(post_id, user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post non trovato")

    # controllo che l'utente sia l'autore del post o un admin
    if not user or (user.username != post["author"] and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    return templates.TemplateResponse(
        "posts/delete_modal.html",  # template del modale
        {
            "request": request,
            "post": post,
            "source": source
        }
    )

# DELETE POST
@router.post("/{post_id}/delete", response_class=HTMLResponse)
async def delete_post(
    post_id: str,
    request: Request,
    source: str = Form("feed"),
    user: UserInDB = Depends(require_user_cookie)
):
    post = post_db.get_post_by_id(post_id, user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post non trovato")

    # controllo che l'utente sia l'autore del post o un admin
    if not user or (user.username != post["author"] and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    post_db.delete_post(post_id)

    # risposta HTMX con flash e rimozione modal
    flash_html = """
    <div id="flash-container" hx-swap-oob="innerHTML">
        <div class="msg-success"
            hx-get="/empty"
            hx-trigger="load delay:3s"
            hx-swap="delete">
            Post eliminato con successo
        </div>
    </div>
    """

    if source == "detail":
        response = HTMLResponse("""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-success">
                    Post eliminato con successo
                </div>
            </div>
        """)
        response.headers["HX-Redirect"] = "/"
        return response
    else:  # feed
        return HTMLResponse(
            f"""
            {flash_html}
            <div id="modal-container" hx-swap-oob="true"></div>
            <div id="post-{post_id}" hx-swap-oob="true"></div>
            """
        )

@router.get("/feed", response_class=HTMLResponse)
async def post_feed(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    skip = page * page_size
    posts = await post_db.get_posts_paginated(skip, page_size, user.id if user else None)

    return templates.TemplateResponse(
        "partials/feed.html",
        {
            "request": request,
            "posts": posts,
            "next_page": page + 1,
            "has_more": len(posts) == page_size,
            "pagination_url": "/posts/feed"
        }
    )

@router.get("/{post_id}", response_class=HTMLResponse)
async def post_detail(
    request: Request,
    post_id: str,
    user: UserInDB | None = Depends(optional_current_user_cookie),
    hx_request: Annotated[Union[str, None], Header(alias="HX-Request")] = None,
):
    post = post_db.get_post_by_id(post_id, user.id if user else None)

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
    liked, like_count = post_db.toggle_like(post_id, user.username)
    post = post_db.get_post_by_id(post_id, user.id)

    if liked:
        # Pubblicazione della notifica di like tramite MQTT
        mqtt_notification_client.publish(
            {
                "type": "post_liked",
                "author": user.username,
                "content": post["author"],
                "post_id": post_id,
            }
        )

    return templates.TemplateResponse(
        "posts/partials/like_button.html",
        {
            "request": request,
            "post_id": post_id,
            "liked": liked,
            "like_count": like_count,
        },
    )
