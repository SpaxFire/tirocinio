from typing import Annotated
from fastapi import Depends, Request, Header, APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from app.core.config import templates
from app.core.security import optional_current_user_cookie
from app.schemas.user import UserInDB
from app.db import post as post_db
from app.db import user as user_db
from app.db import comment as comment_db
from app.services.audit_client import AuditServiceClient
from urllib.parse import urlencode

# Inizializza il router e il client verso il validatore audit
router = APIRouter(tags=["pages"])
audit_client = AuditServiceClient()

# Risponde alle richieste GET per la home page
@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    hx_request: Annotated[str | None, Header()] = None
):
    """
    Home page:
    - se richiesta HTMX → solo contenuto centrale
    - se richiesta normale → pagina completa
    """
    if hx_request:
        return templates.TemplateResponse(
            "partials/home_content.html",
            {"request": request}
        )

    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )

# Risponde alle richieste GET per la barra laterale destra
@router.get("/sidebar/right", response_class=HTMLResponse)
def right_sidebar(
    request: Request,
    current_user: UserInDB | None = Depends(optional_current_user_cookie),
):
    if not current_user:
        return templates.TemplateResponse(
            "components/sidebar_right_guest.html",
            {"request": request}
        )

    users = user_db.get_following_paginated(
        username=current_user.username,
        skip=0,
        limit=5,
        my_id=current_user.id
    )

    return templates.TemplateResponse(
        "components/sidebar_right_following.html",
        {
            "request": request,
            "users": users,
            "has_more": False
        }
    )

# Risponde alle richieste GET per la pagina di ricerca
@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = "",
    tab: str = "posts",
    page: int = 0,
    page_size: int = 10,
    categories: str = "",
    bio: str = "",
    current_user: UserInDB | None = Depends(optional_current_user_cookie),
):
    skip = page * page_size

    # parsing categorie
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    print("Categorie selezionate:", category_list)
    # QUERY
    if tab == "posts":
        results = post_db.search_posts(
            query=q,
            categories=category_list,
            skip=skip,
            limit=page_size,
            my_id=current_user.id if current_user else None
        )

    elif tab == "users":
        results = user_db.search_users(
            query=q,
            bio=bio,
            skip=skip,
            limit=page_size,
            my_id=current_user.id if current_user else None
        )

    elif tab == "comments":
        results = comment_db.search_comments(
            query=q,
            categories=category_list,
            skip=skip,
            limit=page_size
        )

    has_more = len(results) == page_size

    # pagination URL mantiene filtri
    params = {
        "q": q.strip(),
        "tab": tab,
        "categories": categories.strip(),
        "bio": bio.strip(),
    }

    # rimuove chiavi con valori vuoti
    clean_params = {k: v for k, v in params.items() if v}

    pagination_url = f"/search?{urlencode(clean_params)}"
    print("URL di paginazione:", pagination_url)

    context = {
        "request": request,
        "query": q,
        "active_tab": tab,
        "next_page": page + 1,
        "has_more": has_more,
        "pagination_url": pagination_url,
    }

    if tab == "posts":
        context["posts"] = results
    elif tab == "users":
        context["users"] = results
    elif tab == "comments":
        context["comments"] = results

    # HTMX logic
    if request.headers.get("HX-Request"):
        if page > 0:
            template_map = {
                "posts": "partials/feed.html",
                "users": "partials/user_list.html",
                "comments": "users/partials/profile_comments.html",
            }

            response = templates.TemplateResponse(template_map[tab], context)
            # no push durante paginazione
            return response

        # Primo caricamento o cambio tab
        response = templates.TemplateResponse(
            "search/partials/search_content.html",
            context
        )

        # push dell'URL pulito
        response.headers["HX-Push-Url"] = pagination_url

        return response


    # NON HX → render normale (già pulito se hai fatto redirect prima)
    return templates.TemplateResponse("search/search.html", context)

# Risponde alle richieste GET per la pagina Discover
@router.get("/discover", response_class=HTMLResponse)
async def discover_page(
    request: Request,
    tab: str = "posts",
    page: int = 0,
    page_size: int = 10,
    current_user: UserInDB | None = Depends(optional_current_user_cookie),
):

    skip = page * page_size

    if tab == "posts":
        results = post_db.discover_posts_from_followed_likes(
            my_id=current_user.id,
            skip=skip,
            limit=page_size,
        )
    else:
        results = user_db.discover_users_from_followed(
            my_id=current_user.id,
            skip=skip,
            limit=page_size,
        )

    has_more = len(results) == page_size
    pagination_url = f"/discover?tab={tab}"

    context = {
        "request": request,
        "active_tab": tab,
        "next_page": page + 1,
        "has_more": has_more,
        "pagination_url": pagination_url,
    }

    if tab == "posts":
        context["posts"] = results
    else:
        context["users"] = results

    # HTMX
    if request.headers.get("HX-Request"):
        print("Richiesta HTMX per Discover - Tab:", tab, "Pagina:", page)
        if page > 0:
            template_map = {
                "posts": "partials/feed.html",
                "users": "partials/user_list.html",
            }
            return templates.TemplateResponse(template_map[tab], context)

        response = templates.TemplateResponse(
            "discover/partials/discover_content.html",
            context
        )
        response.headers["HX-Push-Url"] = pagination_url
        return response

    return templates.TemplateResponse(
        "discover/discover.html",
        context
    )


# ADMIN PAGES, controlla la validità della blockchain di audit e mostra la catena
@router.get("/admin/audit", response_class=HTMLResponse)
async def admin_audit_page(
    request: Request,
    current_user: UserInDB | None = Depends(optional_current_user_cookie),
    user: str | None = None,
    event_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
):
    if not current_user or current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    chain: dict = {"chain": []}
    is_valid = False

    if audit_client.enabled:
        remote_view = await audit_client.get_chain_view(
            user=user,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
        )
        if remote_view:
            chain = remote_view.get("chain", {"chain": []})
            is_valid = bool(remote_view.get("is_valid", False))

    context = {
        "request": request,
        "chain": chain,
        "is_valid": is_valid,
        "active_filters": {
            "user": user,
            "event_type": event_type,
            "start_time": start_time,
            "end_time": end_time,
        },
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("admin/partials/audit_content.html", context)

    return templates.TemplateResponse("admin/audit.html", context)

# Risponde alle richieste GET per l'endpoint vuoto
@router.get("/empty", response_class=HTMLResponse)
async def empty():
    """
    Endpoint vuoto usato per svuotare i messaggi di errore nei modali tramite HTMX
    """
    return HTMLResponse("")
