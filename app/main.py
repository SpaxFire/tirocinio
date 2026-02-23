from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import templates
from app.core.security import optional_current_user_cookie
from app.api.router import api_router

app = FastAPI()

# MIDDLEWARE PER current_user
class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        access_token = request.cookies.get("access_token")

        user = await optional_current_user_cookie(access_token)

        request.state.user = user  # disponibile ovunque

        response = await call_next(request)
        return response
    
class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        access_token = request.cookies.get("access_token")
        user = await optional_current_user_cookie(access_token)

        request.state.user = user

        response = await call_next(request)

        # elimina flash cookie dopo il primo render
        if request.cookies.get("flash_message"):
            response.delete_cookie("flash_message")

        return response


app.add_middleware(CurrentUserMiddleware)


# STATIC
app.mount("/static", StaticFiles(directory="static"), name="static")

# ROUTER
app.include_router(api_router)


# RENDIAMO current_user GLOBALE NEI TEMPLATE
templates.env.globals["current_user"] = lambda request: request.state.user


# Gestione errori 401 per HTMX
@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):

    if request.headers.get("HX-Request"):
        response = templates.TemplateResponse(
            "auth/login_modal.html",
            {"request": request},
            status_code=200,
        )
        response.headers["HX-Retarget"] = "#modal-container"
        response.headers["HX-Reswap"] = "innerHTML"
        return response

    return HTMLResponse("Unauthorized", status_code=401)