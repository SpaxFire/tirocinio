from typing import Annotated, Union

from fastapi import FastAPI, Form, Request, Header
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from neo4j import GraphDatabase

# connection to the neo4j db
URI = "neo4j+s://59d9d16d.databases.neo4j.io"
AUTH = ("59d9d16d", "UEFY7bEn9JLKCKSdQ66kU0uJStz8hE1dBD7Oq4rx2Jg")

with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()

summary = driver.execute_query("""
    MATCH (n)
    DETACH DELETE n
    """,
    database="59d9d16d",
    database_="59d9d16d",
).summary
print("Deleted {nodes_created} nodes in {time} ms.".format(
    nodes_created=summary.counters.nodes_deleted,
    time=summary.result_available_after
))
summary = driver.execute_query("""
    CREATE CONSTRAINT post_user IF NOT EXISTS FOR (p:Post) REQUIRE p.user IS UNIQUE
    """,
    database_="59d9d16d",
).summary
print("Added {constraint_created} constaint in {time} ms.".format(
    constraint_created=summary.counters.constraints_added,
    time=summary.result_available_after
))

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
    summary = driver.execute_query("""
        CREATE (p:Post {id: 1, user: $user, text: $text, verified: $verified})
        RETURN p
        """,
        user=user,text=text, verified=verified,
        database_="59d9d16d",
    ).summary
    print("Created {nodes_created} nodes in {time} ms.".format(
        nodes_created=summary.counters.nodes_created,
        time=summary.result_available_after
    ))
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