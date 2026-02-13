from uuid import uuid4
from app.db.neo4j import get_driver

def create_post(username: str, content: str, categories: list[str], media_urls: list[str]):
    driver = get_driver()
    post_id = str(uuid4())

    query = """
    MATCH (u:User {username: $username})

    CREATE (p:Post {
        id: $post_id,
        content: $content,
        created_at: datetime(),
        updated_at: datetime(),
        visibility: "public",
        media_urls: $media_urls
    })

    MERGE (u)-[:CREATED]->(p)

    WITH p
    FOREACH (cat_name IN $categories |
        MERGE (c:Category {name: cat_name})
        MERGE (p)-[:IN_CATEGORY]->(c)
    )
    RETURN
        p.id AS id,
        p.content AS content,
        p.created_at AS created_at,
        p.media_urls AS media_urls,
        $username AS author
    """

    records, _, _ = driver.execute_query(
        query,
        username=username,
        post_id=post_id,
        content=content,
        categories=categories,
        media_urls=media_urls,
        database_="neo4j",
    )

    return records[0]


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

def toggle_like(post_id: str, username: str):
    driver = get_driver()

    query = """
    MATCH (u:User {username:$username})
    MATCH (p:Post {id:$post_id})

    OPTIONAL MATCH (u)-[r:LIKES]->(p)

    WITH u, p, r,
         CASE WHEN r IS NULL THEN true ELSE false END AS should_create

    FOREACH (_ IN CASE WHEN should_create THEN [1] ELSE [] END |
        MERGE (u)-[new_r:LIKES]->(p)
        ON CREATE SET new_r.created_at = datetime()
    )

    FOREACH (_ IN CASE WHEN should_create THEN [] ELSE [1] END |
        DELETE r
    )

    WITH p, should_create AS liked
    OPTIONAL MATCH (p)<-[:LIKES]-(l:User)

    RETURN liked, count(l) AS like_count
    """

    records, _, _ = driver.execute_query(
        query,
        username=username,
        post_id=post_id,
        database_="neo4j",
    )

    rec = records[0]
    return rec["liked"], rec["like_count"]

async def get_posts_paginated(skip: int, limit: int, user_id: str | None):
    driver = get_driver()
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User)-[:CREATED]->(p:Post)

        OPTIONAL MATCH (p)<-[:LIKES]-(liker:User)
        WITH u, p, count(liker) AS like_count

        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
        WITH u, p, like_count, count(c) AS comment_count

        OPTIONAL MATCH (me:User {id: $user_id})-[ml:LIKES]->(p)

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
            comment_count,
            CASE WHEN ml IS NULL THEN false ELSE true END AS liked_by_me
        """,
        skip=skip,
        limit=limit,
        user_id=user_id,
        database_="neo4j",
    )
    return records

def get_post_by_id(post_id: str, user_id: str | None) -> dict | None:
    query = """
    MATCH (p:Post {id: $post_id})
    OPTIONAL MATCH (p)<-[:CREATED]-(u:User)
    OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
    OPTIONAL MATCH (p)<-[:LIKES]-(l:User)

    WITH p, u, count(DISTINCT c) AS comment_count,
         count(DISTINCT l) AS like_count

    // gestiamo user_id null in modo sicuro
    OPTIONAL MATCH (me:User)-[ml:LIKES]->(p)
        WHERE me.id = $user_id

    RETURN
        p,
        u.username AS author,
        comment_count,
        like_count,
        CASE WHEN ml IS NULL THEN false ELSE true END AS liked_by_me
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            post_id=post_id,
            user_id=user_id
        ).single()

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
            "liked_by_me": record["liked_by_me"],
        }


