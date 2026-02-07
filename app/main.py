from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db.init_db import init_db

init_db()

from app.api.router import api_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router)