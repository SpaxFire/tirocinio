from typing import Annotated
from fastapi import Depends, Request, Header, APIRouter
from fastapi.responses import HTMLResponse
from app.core.config import templates
from app.core.dependencies import optional_current_user_cookie
from app.schemas.user import UserInDB
from app.db import post as post_crud
from app.db import user as user_crud
from app.db import comment as comment_crud
from urllib.parse import urlencode

router = APIRouter(tags=["pages"])


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
        results = post_crud.search_posts(
            query=q,
            categories=category_list,
            skip=skip,
            limit=page_size,
            my_id=current_user.id if current_user else None
        )

    elif tab == "users":
        results = user_crud.search_users(
            query=q,
            bio=bio,
            skip=skip,
            limit=page_size,
            my_id=current_user.id if current_user else None
        )

    elif tab == "comments":
        results = comment_crud.search_comments(
            query=q,
            categories=category_list,
            skip=skip,
            limit=page_size
        )

    has_more = len(results) == page_size

    # pagination URL mantiene filtri
    params = {
        "q": q,
        "tab": tab,
        "categories": categories,
        "bio": bio,
    }

    pagination_url = f"/search?{urlencode(params)}"

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
            return templates.TemplateResponse(template_map[tab], context)

        return templates.TemplateResponse(
            "search/partials/search_content.html",
            context
        )

    return templates.TemplateResponse("search/search.html", context)

@router.get("/empty", response_class=HTMLResponse)
async def empty():
    """
    Endpoint vuoto usato per svuotare i messaggi di errore nei modali tramite HTMX
    """
    return HTMLResponse("")
