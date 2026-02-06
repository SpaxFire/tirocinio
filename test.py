from typing import Annotated, Union

from fastapi import FastAPI, Form, Request, Header
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from neo4j import GraphDatabase
import uvicorn

# connection to the neo4j db
URI = "neo4j+s://4148cbd8.databases.neo4j.io"
AUTH = ("neo4j", "Na-BH0ELGuexhejtnBBsUQqDl-KoJpA8soPaelB_gOI")

driver = GraphDatabase.driver(URI, auth=AUTH)
driver.verify_connectivity()

summary = driver.execute_query("""
    CREATE CONSTRAINT post_user IF NOT EXISTS FOR (p:Post) REQUIRE p.user IS UNIQUE
    """,
    database_="neo4j",
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
    def __init__(self, id: str, user : str, text: str, verified = False):
        self.id = id
        self.user = user
        self.text = text
        self.verified = verified

@app.get("/posts", response_class=HTMLResponse)
async def list_posts(request: Request, hx_request: Annotated[Union[str, None], Header()] = None):
    # Fetch posts from database
    records, summary, keys = driver.execute_query(
        "MATCH (p:Post) RETURN p.id as id, p.user as user, p.text as text, p.verified as verified",
        database_="neo4j",
    )
    posts = [Post(record["id"], record["user"], record["text"], record["verified"]) for record in records]
    
    if hx_request:
        return templates.TemplateResponse(
            request=request, name="posts.html", context={"posts": posts}
        )
    return JSONResponse(content=jsonable_encoder(posts))

@app.post("/posts", response_class=HTMLResponse)
async def create_post(request: Request, user : Annotated[str, Form()], verified : Annotated[bool, Form()], text : Annotated[str, Form()] = ""):
    post_id = str(uuid4())
    summary = driver.execute_query("""
        CREATE (p:Post {id: $id, user: $user, text: $text, verified: $verified})
        RETURN p
        """,
        id=post_id, user=user, text=text, verified=verified,
        database_="neo4j",
    ).summary
    print("Created {nodes_created} nodes in {time} ms.".format(
        nodes_created=summary.counters.nodes_created,
        time=summary.result_available_after
    ))
    
    # Fetch all posts from database
    records, summary, keys = driver.execute_query(
        "MATCH (p:Post) RETURN p.id as id, p.user as user, p.text as text, p.verified as verified",
        database_="neo4j",
    )
    posts = [Post(record["id"], record["user"], record["text"], record["verified"]) for record in records]
    
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )

@app.put("/posts/{post_id}", response_class=HTMLResponse)
async def update_post(request: Request, post_id: str, text : Annotated[str, Form()] = ""):
    # Update post in database
    driver.execute_query(
        "MATCH (p:Post {id: $id}) SET p.text = $text",
        id=post_id, text=text,
        database_="neo4j",
    )
    
    # Fetch all posts from database
    records, summary, keys = driver.execute_query(
        "MATCH (p:Post) RETURN p.id as id, p.user as user, p.text as text, p.verified as verified",
        database_="neo4j",
    )
    posts = [Post(record["id"], record["user"], record["text"], record["verified"]) for record in records]
    
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )

@app.post("/posts/{post_id}/toggle", response_class=HTMLResponse)
async def toggle_post(request: Request, post_id: str):
    # Fetch current verified status and toggle it
    records, _, _ = driver.execute_query(
        "MATCH (p:Post {id: $id}) RETURN p.verified as verified",
        id=post_id,
        database_="neo4j",
    )
    if records:
        current_verified = records[0]["verified"]
        driver.execute_query(
            "MATCH (p:Post {id: $id}) SET p.verified = $verified",
            id=post_id, verified=not current_verified,
            database_="neo4j",
        )
    
    # Fetch all posts from database
    records, summary, keys = driver.execute_query(
        "MATCH (p:Post) RETURN p.id as id, p.user as user, p.text as text, p.verified as verified",
        database_="neo4j",
    )
    posts = [Post(record["id"], record["user"], record["text"], record["verified"]) for record in records]
    
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )


@app.post("/posts/{post_id}/delete", response_class=HTMLResponse)
async def delete_post(request: Request, post_id: str):
    # Delete post from database
    driver.execute_query(
        "MATCH (p:Post {id: $id}) DELETE p",
        id=post_id,
        database_="neo4j",
    )
    
    # Fetch all posts from database
    records, summary, keys = driver.execute_query(
        "MATCH (p:Post) RETURN p.id as id, p.user as user, p.text as text, p.verified as verified",
        database_="neo4j",
    )
    posts = [Post(record["id"], record["user"], record["text"], record["verified"]) for record in records]
    
    return templates.TemplateResponse(
        request=request, name="posts.html", context={"posts": posts}
    )

# Source - https://stackoverflow.com/a/66240984
# Posted by alex_noname, modified by community. See post 'Timeline' for change history
# Retrieved 2026-02-06, License - CC BY-SA 4.0

if __name__ == "__main__":
    uvicorn.run("example:app", host="127.0.0.1", port=8000, reload=True)