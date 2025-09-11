from typing import Annotated, Union

from fastapi import FastAPI, Form, Request, Header
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from neo4j import GraphDatabase, RoutingControl

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"),name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request : Request):
    return templates.TemplateResponse(request=request, name="index.html")

class Post:
    def __init__(self, user : str, text: str, verified = False):
        self.id = uuid4()
        self.user = user
        self.text = text
        self.verified = verified

posts = [Post("pippo", "messaggio di test"), Post("pluto", "messaggio di test 2", True)]

@app.get("/posts", response_class=HTMLResponse)
async def list_posts(request: Request, hx_request: Annotated[Union[str, None], Header()] = None):
    if hx_request:
        return templates.TemplateResponse(
            request=request, name="posts.html", context={"posts": posts}
        )
    return JSONResponse(content=jsonable_encoder(posts))

@app.post("/posts", response_class=HTMLResponse)
async def create_post(request: Request, user : Annotated[str, Form()], text : Annotated[str, Form()], verified : Annotated[bool, Form()]):
    posts.append(Post(user, text, verified))
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )

@app.put("/posts/{post_id}", response_class=HTMLResponse)
async def update_post(request: Request, post_id: str, text : Annotated[str, Form()]):
    for index, post in enumerate(posts):
        if str(post.id) == post_id:
            post.text = text
            break
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )

@app.post("/posts/{post_id}/toggle", response_class=HTMLResponse)
async def toggle_post(request: Request, post_id: str):
    for index, post in enumerate(posts):
        if str(post.id) == post_id:
            posts[index].verified = not posts[index].verified
            break
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )


@app.post("/posts/{post_id}/delete", response_class=HTMLResponse)
async def delete_post(request: Request, post_id: str):
    for index, post in enumerate(posts):
        if str(post.id) == post_id:
            del posts[index]
            break
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )