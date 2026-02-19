from fastapi import APIRouter
from app.api.routes import  users, categories, comments, pages, posts, auth

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(pages.router)
api_router.include_router(posts.router)
api_router.include_router(categories.router)
api_router.include_router(comments.router)
api_router.include_router(users.router)