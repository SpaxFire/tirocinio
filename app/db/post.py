from uuid import uuid4
from app.db.neo4j import get_driver
from neo4j.time import DateTime as Neo4jDateTime

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


def update_post(post_id: str, content: str, categories: list[str], media_urls: list[str]):
    driver = get_driver()
    with driver.session() as session:
        # aggiorna contenuto e media
        session.run(
            """
            MATCH (p:Post {id: $post_id})
            SET p.content = $content,
                p.updated_at = datetime(),
                p.media_urls = $media_urls
            """,
            post_id=post_id,
            content=content,
            media_urls=media_urls
        )

        # rimuove vecchi archi IN_CATEGORY
        session.run(
            """
            MATCH (p:Post {id: $post_id})-[r:IN_CATEGORY]->()
            DELETE r
            """,
            post_id=post_id
        )

        # aggiunge nuove categorie
        for cat in categories:
            session.run(
                """
                MERGE (c:Category {name: $cat})
                WITH c
                MATCH (p:Post {id: $post_id})
                MERGE (p)-[:IN_CATEGORY]->(c)
                """,
                post_id=post_id,
                cat=cat
            )

    return get_post_by_id(post_id, None)


def delete_post(post_id: str):
    driver = get_driver()
    driver.execute_query(
        """
        MATCH (p:Post {id: $id})

        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)

        OPTIONAL MATCH (p)<-[l:LIKES]-()

        DETACH DELETE p, c
        """,
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

        // ---- LIKE COUNT ----
        OPTIONAL MATCH (p)<-[:LIKES]-(liker:User)
        WITH u, p, count(DISTINCT liker) AS like_count

        // ---- COMMENT COUNT ----
        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
        WITH u, p, like_count, count(DISTINCT c) AS comment_count

        // ---- CATEGORIES ----
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)
        WITH u, p, like_count, comment_count,
             collect(DISTINCT cat.name) AS categories

        // ---- CURRENT USER ----
        OPTIONAL MATCH (me:User {id: $user_id})
        OPTIONAL MATCH (me)-[ml:LIKES]->(p)
        OPTIONAL MATCH (me)-[:WROTE]->(myComment:Comment)-[:ON_POST]->(p)

        WITH u, p, like_count, comment_count, categories,
             ml, count(DISTINCT myComment) AS my_comments

        ORDER BY p.created_at DESC
        SKIP $skip
        LIMIT $limit

        RETURN
            p.id        AS id,
            p.content   AS content,
            p.created_at AS created_at,
            p.media_urls AS media_urls,
            u.username  AS author,
            u.profile_image AS profile_image,
            like_count,
            comment_count,
            categories,
            CASE WHEN ml IS NULL THEN false ELSE true END AS liked_by_me,
            CASE WHEN my_comments > 0 THEN true ELSE false END AS commented_by_me
        """,
        skip=skip,
        limit=limit,
        user_id=user_id,
        database_="neo4j",
    )

    formatted = []

    for record in records:
        post = dict(record)
        created_at = post["created_at"]

        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        post["created_at"] = created_at.strftime("%d %b %Y • %H:%M")

        # sicurezza: se non ha categorie → []
        post["categories"] = post.get("categories") or []

        formatted.append(post)

    return formatted

def get_post_by_id(post_id: str, user_id: str | None) -> dict | None:
    query = """
    MATCH (p:Post {id: $post_id})
    OPTIONAL MATCH (p)<-[:CREATED]-(u:User)
    OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)
    OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
    OPTIONAL MATCH (p)<-[:LIKES]-(l:User)

    WITH p, u,
        collect(DISTINCT cat.name) AS categories,
        count(DISTINCT c) AS comment_count,
        count(DISTINCT l) AS like_count

    OPTIONAL MATCH (me:User {id: $user_id})
    OPTIONAL MATCH (me)-[ml:LIKES]->(p)
    OPTIONAL MATCH (me)-[:WROTE]->(myComment:Comment)-[:ON_POST]->(p)

    WITH p, u, categories, comment_count, like_count, ml,
        count(DISTINCT myComment) AS my_comments

    RETURN
        p,
        u.username AS author,
        u.profile_image AS profile_image,
        categories,
        comment_count,
        like_count,
        CASE WHEN ml IS NULL THEN false ELSE true END AS liked_by_me,
        CASE WHEN my_comments > 0 THEN true ELSE false END AS commented_by_me,
        p.created_at AS created_at
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
        created_at = record["created_at"]

        # Converto Neo4jDateTime in datetime Python e formatto come stringa
        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        created_at_str = created_at.strftime("%d %b %Y • %H:%M")

        return {
        "id": p["id"],
        "content": p["content"],
        "media_urls": p.get("media_urls", []),
        "categories": record["categories"],
        "author": record["author"],
        "profile_image": record["profile_image"],
        "comment_count": record["comment_count"],
        "like_count": record["like_count"],
        "liked_by_me": record["liked_by_me"],
        "commented_by_me": record["commented_by_me"],
        "created_at": created_at_str,
    }

def search_posts(query: str, categories: list[str], skip: int, limit: int, my_id: str | None):
    driver = get_driver()
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User)-[:CREATED]->(p:Post)
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)

        WITH u, p, 
            collect(DISTINCT cat.name) AS categories,
            [c IN collect(cat.name) | trim(toLower(c))] AS postCategories,
            [x IN $categories | trim(toLower(x))] AS filterCategories

        WHERE 
            ($query = "" OR toLower(p.content) CONTAINS toLower($query))
        AND
            (SIZE(filterCategories) = 0 
                OR ANY(c IN postCategories WHERE c IN filterCategories))

        WITH DISTINCT u, p, categories

        // ---- LIKE COUNT ----
        OPTIONAL MATCH (p)<-[:LIKES]-(liker:User)
        WITH u, p, categories, count(DISTINCT liker) AS like_count

        // ---- COMMENT COUNT ----
        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
        WITH u, p, categories, like_count, count(DISTINCT c) AS comment_count

        // ---- CURRENT USER STATE ----
        OPTIONAL MATCH (me:User {id: $my_id})
        OPTIONAL MATCH (me)-[ml:LIKES]->(p)
        OPTIONAL MATCH (me)-[:WROTE]->(myComment:Comment)-[:ON_POST]->(p)

        WITH u, p, categories, like_count, comment_count, ml,
            count(DISTINCT myComment) AS my_comments

        ORDER BY p.created_at DESC
        SKIP $skip
        LIMIT $limit

        RETURN
            p.id AS id,
            p.content AS content,
            p.created_at AS created_at,
            p.media_urls AS media_urls,
            u.username AS author,
            u.profile_image AS profile_image,
            like_count,
            comment_count,
            categories,
            CASE WHEN ml IS NULL THEN false ELSE true END AS liked_by_me,
            CASE WHEN my_comments > 0 THEN true ELSE false END AS commented_by_me
        """,
        query=query,
        skip=skip,
        limit=limit,
        my_id=my_id,
        categories=categories,
        database_="neo4j",
    )

    formatted = []

    for record in records:
        post = dict(record)
        created_at = post["created_at"]

        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        post["created_at"] = created_at.strftime("%d %b %Y • %H:%M")

        # sicurezza: sempre lista
        post["categories"] = post.get("categories") or []

        formatted.append(post)

    return formatted

def discover_posts_from_followed_likes(
    my_id: str,
    skip: int,
    limit: int
):
    driver = get_driver()

    records, _, _ = driver.execute_query(
        """
        MATCH (me:User {id: $my_id})-[:FOLLOWS]->(f:User)
        MATCH (f)-[:LIKES]->(p:Post)
        MATCH (author:User)-[:CREATED]->(p)

        // escludo miei post
        WHERE author.id <> $my_id

        // escludo post già likati da me
        AND NOT (me)-[:LIKES]->(p)

        // escludo post già commentati da me
        AND NOT (me)-[:WROTE]->(:Comment)-[:ON_POST]->(p)

        // conteggio quanti followed hanno messo like
        WITH p, author, count(DISTINCT f) AS score

        // ---- LIKE COUNT TOTALE ----
        OPTIONAL MATCH (p)<-[:LIKES]-(liker:User)
        WITH p, author, score, count(DISTINCT liker) AS like_count

        // ---- COMMENT COUNT ----
        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
        WITH p, author, score, like_count,
             count(DISTINCT c) AS comment_count

        // ---- CATEGORIES ----
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)
        WITH p, author, score, like_count, comment_count,
             collect(DISTINCT cat.name) AS categories

        ORDER BY score DESC, p.created_at DESC
        SKIP $skip
        LIMIT $limit

        RETURN
            p.id AS id,
            p.content AS content,
            p.created_at AS created_at,
            p.media_urls AS media_urls,
            author.username AS author,
            author.profile_image AS profile_image,
            like_count,
            comment_count,
            categories,
            score,
            false AS liked_by_me,
            false AS commented_by_me
        """,
        my_id=my_id,
        skip=skip,
        limit=limit,
        database_="neo4j",
    )

    formatted = []

    for record in records:
        post = dict(record)

        created_at = post["created_at"]
        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        post["created_at"] = created_at.strftime("%d %b %Y • %H:%M")
        post["categories"] = post.get("categories") or []

        formatted.append(post)

    return formatted