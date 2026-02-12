from fastapi import APIRouter, Request
from app.db import category as category_crud
from app.core.config import templates

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/search")
async def search_categories(request: Request, category_search: str = ""):
    results = category_crud.search_categories(category_search)

    return templates.TemplateResponse(
        "partials/category_results.html",
        {
            "request": request,
            "categories": results,
        },
    )

