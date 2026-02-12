from fastapi import APIRouter
from app.api.routes import categories, pages, posts, auth

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(pages.router)
api_router.include_router(posts.router)
api_router.include_router(categories.router)