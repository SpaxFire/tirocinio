from fastapi import APIRouter
from app.api.routes import pages, posts

api_router = APIRouter()
api_router.include_router(pages.router)
api_router.include_router(posts.router)