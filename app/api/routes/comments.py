from fastapi import APIRouter, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse

from app.core.security import require_user_cookie, optional_current_user_cookie
from app.db import post as post_db
from app.db import comment as comment_db
from app.core.config import templates
from app.schemas.user import UserInDB

router = APIRouter(tags=["comments"])

@router.get("/posts/{post_id}/comments", response_class=HTMLResponse)
async def get_comments(
    request: Request,
    post_id: str,
    source: str = "feed"
):
    limit = 3 if source == "feed" else None

    comments = await comment_db.get_comments_of_post(
        post_id,
        limit=limit
    )

    total_count = await comment_db.count_comments_of_post(post_id)

    show_all_button = source == "feed" and total_count > 5

    return templates.TemplateResponse(
        "posts/comments.html",
        {
            "request": request,
            "comments": comments,
            "post_id": post_id,
            "source": source,
            "show_all_button": show_all_button,
            "remain_count": total_count - (limit if limit else 0),
        }
    )



@router.get("/posts/{post_id}/comment-modal", response_class=HTMLResponse)
async def comment_modal(
    post_id: str,
    request: Request,
    source: str = "feed",
    user: UserInDB = Depends(require_user_cookie),
):
    post = post_db.get_post_by_id(post_id, user.id)

    if not post:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "comments/comment_modal.html",
        {
            "request": request,
            "post": post,
            "source": source
        }
    )


@router.post("/posts/{post_id}/comments", response_class=HTMLResponse)
async def create_comment(
    post_id: str,
    request: Request,
    content: str = Form(""),
    source: str = Form("feed"),
    user: UserInDB = Depends(require_user_cookie),
):
    if not content.strip():
        return HTMLResponse("""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-danger"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                Il commento non può essere vuoto
            </div>
        </div>
        """)

    comment_db.create_comment(
        post_id=post_id,
        username=user.username,
        content=content
    )
    # recupero dati aggiornati del post per renderizzare correttamente i commenti
    comments = await comment_db.get_comments_of_post(post_id)
    comments_html = templates.get_template(
        "posts/comments.html"
    ).render({
        "request": request,
        "comments": comments
    })

    commented_by_me = await comment_db.has_user_commented(post_id=post_id, username=user.username)
    button_html = templates.get_template(
        "posts/partials/comment_button.html"
    ).render({
        "request": request,
        "post_id": post_id,
        "commented_by_me": commented_by_me,
        "comment_count": len(comments),
        "source": source
    })


    # render corretto in base alla provenienza
    if source == "detail":
        return HTMLResponse(
            f"""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-success"
                    hx-get="/empty"
                    hx-trigger="load delay:3s"
                    hx-swap="delete">
                    Commento pubblicato con successo
                </div>
            </div>

            <div id="modal-container" hx-swap-oob="true"></div>
            <div id="comments" hx-swap-oob="true">
                {comments_html}
            </div>

            <div id="comment-btn-{ post_id }" hx-swap-oob="outerHTML">
                { button_html }
            </div>
            """
        )

    else:  # feed
        return HTMLResponse(
            f"""
            <div id="flash-container" hx-swap-oob="innerHTML">
                <div class="msg-success"
                    hx-get="/empty"
                    hx-trigger="load delay:3s"
                    hx-swap="delete">
                    Commento pubblicato con successo
                </div>
            </div>

            <div id="modal-container" hx-swap-oob="true"></div>
            <div id="comments-{post_id}" hx-swap-oob="true" class="mt-4 text-sm space-y-2 relative z-30">
                {comments_html}
            </div>

            <div id="comment-btn-{ post_id }" hx-swap-oob="outerHTML">
                { button_html }
            </div>
            """
        )

@router.get("/comments/{comment_id}/edit-modal", response_class=HTMLResponse)
async def edit_comment_modal(
    comment_id: str,
    request: Request,
    source: str = "feed",
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    comment = comment_db.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Commento non trovato")

    # controllo che l'utente sia l'autore del commento o un admin
    if not user or (user.username != comment.author and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    return templates.TemplateResponse(
        "comments/edit_modal.html",
        {
            "request": request,
            "comment": comment,
            "source": source
        }
    )

@router.post("/comments/{comment_id}/update", response_class=HTMLResponse)
async def update_comment(
    comment_id: str,
    request: Request,
    content: str = Form(""),
    source: str = Form("feed"),
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    comment = comment_db.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Commento non trovato")
    
    # controllo che l'utente sia l'autore del commento o un admin
    if not user or (user.username != comment.author and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    if not content.strip():
        return HTMLResponse("""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-danger"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                Il commento non può essere vuoto
            </div>
        </div>
        """)

    comment_db.update_comment(comment_id, content)
    
    updated_comment = comment_db.get_comment_by_id(comment_id)

    html = templates.get_template("comments/partials/comment_item.html").render(
        {"request": request, "comment": updated_comment}
    )

    return HTMLResponse(f"""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-success"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                Commento modificato
            </div>
        </div>

        <div id="modal-container" hx-swap-oob="true"></div>
        <div id="comment-{comment_id}" hx-swap-oob="true">
            {html}
        </div>
    """)

@router.get("/comments/{comment_id}/delete-modal", response_class=HTMLResponse)
async def delete_comment_modal(
    comment_id: str,
    request: Request,
    source: str = "feed",
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    comment = comment_db.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Commento non trovato")

    # controllo che l'utente sia l'autore del commento o un admin
    if not user or (user.username != comment.author and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    return templates.TemplateResponse(
        "comments/delete_modal.html",
        {
            "request": request,
            "comment": comment,
            "source": source
        }
    )

@router.post("/comments/{comment_id}/delete", response_class=HTMLResponse)
async def delete_comment(
    comment_id: str,
    request: Request,
    source: str = Form("feed"),
    user: UserInDB | None = Depends(optional_current_user_cookie)
):
    comment = comment_db.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Commento non trovato")

    # controllo che l'utente sia l'autore del commento o un admin
    if not user or (user.username != comment.author and user.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="Permesso negato")

    post_id = comment.post_id

    comment_db.delete_comment(comment_id)

    comments = await comment_db.get_comments_of_post(post_id)

    commented_by_me = await comment_db.has_user_commented(post_id=post_id, username=user.username)
    button_html = templates.get_template(
        "posts/partials/comment_button.html"
    ).render({
        "request": request,
        "post_id": post_id,
        "commented_by_me": commented_by_me,
        "comment_count": len(comments),
        "source": source
    })

    return HTMLResponse(f"""
        <div id="flash-container" hx-swap-oob="innerHTML">
            <div class="msg-success"
                hx-get="/empty"
                hx-trigger="load delay:3s"
                hx-swap="delete">
                Commento eliminato
            </div>
        </div>

        <div id="modal-container" hx-swap-oob="true"></div>

        <div id="comment-{comment_id}" hx-swap-oob="delete"></div>

        <div id="comment-btn-{ post_id }" hx-swap-oob="outerHTML">
            { button_html }
        </div>
    """)

