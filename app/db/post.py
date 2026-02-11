from uuid import uuid4
from app.db.neo4j import get_driver

def get_all_posts():
    driver = get_driver()
    records, _, _ = driver.execute_query(
        """
        MATCH (p:Post)
        RETURN p.id as id, p.user as user, p.text as text, p.verified as verified
        """,
        database_="neo4j",
    )
    return records

def create_post(user: str, text: str, verified: bool):
    driver = get_driver()
    post_id = str(uuid4())
    driver.execute_query(
        """
        CREATE (p:Post {id: $id, user: $user, text: $text, verified: $verified})
        """,
        id=post_id, user=user, text=text, verified=verified,
        database_="neo4j",
    )
    return post_id

def update_post(post_id: str, text: str):
    driver = get_driver()
    driver.execute_query(
        "MATCH (p:Post {id: $id}) SET p.text = $text",
        id=post_id, text=text,
        database_="neo4j",
    )

def delete_post(post_id: str):
    driver = get_driver()
    driver.execute_query(
        "MATCH (p:Post {id: $id}) DELETE p",
        id=post_id,
        database_="neo4j",
    )

def like_post(post_id: str, username: str):
    pass

async def get_posts_paginated(skip: int, limit: int):
    driver = get_driver()
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User)-[:CREATED]->(p:Post)
        OPTIONAL MATCH (p)<-[:LIKES]-(liker:User)
        WITH u, p, count(liker) AS like_count
        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
        WITH u, p, like_count, count(c) AS comment_count
        ORDER BY p.created_at DESC
        SKIP $skip
        LIMIT $limit
        RETURN
        p.id        AS id,
        p.content   AS content,
        p.created_at AS created_at,
        p.media_urls AS media_urls,
        u.username  AS author,
        like_count,
        comment_count
        """,
        skip=skip, limit=limit,
        database_="neo4j",
    )
    return records

def get_post_by_id(post_id: str) -> dict | None:
    query = """
    MATCH (p:Post {id: $post_id})
    OPTIONAL MATCH (p)<-[:CREATED]-(u:User)
    OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
    OPTIONAL MATCH (p)<-[:LIKES]-(l:User)
    RETURN
        p,
        u.username AS author,
        count(DISTINCT c) AS comment_count,
        count(DISTINCT l) AS like_count
    """

    with get_driver().session() as session:
        record = session.run(query, post_id=post_id).single()
        if not record:
            return None

        p = record["p"]
        return {
            "id": p["id"],
            "content": p["content"],
            "media_urls": p.get("media_urls", []),
            "author": record["author"],
            "comment_count": record["comment_count"],
            "like_count": record["like_count"],
        }
