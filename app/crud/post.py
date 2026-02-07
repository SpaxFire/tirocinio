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
        p.media_urls AS media,
        u.username  AS author,
        like_count,
        comment_count
        """,
        skip=skip, limit=limit,
        database_="neo4j",
    )
    return records