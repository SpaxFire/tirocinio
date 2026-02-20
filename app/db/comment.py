from uuid import uuid4
from app.db.neo4j import driver
from neo4j.time import DateTime as Neo4jDateTime

from app.schemas.comment import CommentPublic


async def get_comments_of_post(
    post_id: str,
    limit: int | None = None
) -> list[CommentPublic]:

    query = """
    MATCH (p:Post {id: $post_id})
    MATCH (c:Comment)-[:ON_POST]->(p)
    WITH c
    ORDER BY c.created_at DESC
    """

    params = {"post_id": post_id}

    if limit is not None:
        query += "\nLIMIT $limit"
        params["limit"] = limit

    query += """
    MATCH (u:User)-[:CREATED]->(c)
    RETURN
        c.id AS id,
        c.content AS text,
        u.username AS author,
        u.profile_image AS profile_image,
        c.created_at AS created_at
    """

    with driver.session() as session:
        result = session.run(query, **params)

        comments = []
        for record in result:
            created_at = record["created_at"]

            if isinstance(created_at, Neo4jDateTime):
                created_at = created_at.to_native()

            comments.append(
                CommentPublic(
                    id=record["id"],
                    author=record["author"],
                    profile_image=record["profile_image"],
                    text=record["text"],
                    created_at=created_at.strftime("%d %b %Y • %H:%M"),
                )
            )

        return comments

async def count_comments_of_post(post_id: str) -> int:
    query = """
    MATCH (p:Post {id: $post_id})<-[:ON_POST]-(c:Comment)
    RETURN count(c) AS total
    """

    with driver.session() as session:
        result = session.run(query, post_id=post_id)
        record = result.single()
        return record["total"] if record else 0

async def has_user_commented(post_id: str, username: str) -> bool:
    query = """
    MATCH (u:User {username: $username})
    MATCH (p:Post {id: $post_id})
    RETURN EXISTS {
        MATCH (u)-[:CREATED]->(:Comment)-[:ON_POST]->(p)
    } AS commented_by_me
    """

    with driver.session() as session:
        result = session.run(query, username=username, post_id=post_id)
        record = result.single()
        return record["commented_by_me"] if record else False


def create_comment(post_id: str, username: str, content: str):
    query = """
    MATCH (u:User {username: $username})
    MATCH (p:Post {id: $post_id})

    CREATE (c:Comment {
        id: $comment_id,
        content: $content,
        created_at: datetime(),
        updated_at: datetime()
    })

    MERGE (u)-[:CREATED]->(c)
    MERGE (c)-[:ON_POST]->(p)
    """

    with driver.session() as session:
        session.run(query, {
            "username": username,
            "post_id": post_id,
            "comment_id": str(uuid4()),
            "content": content
        })

def get_comment_by_id(comment_id: str) -> CommentPublic | None:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Comment {id: $comment_id})<-[:CREATED]-(u:User)
            OPTIONAL MATCH (c)-[:ON_POST]->(p:Post)
            RETURN c.id AS id,
                   c.content AS text,
                   u.username AS author,
                   u.profile_image AS profile_image,
                   c.created_at AS created_at,
                   c.updated_at AS updated_at,
                   p.id AS post_id
            """,
            comment_id=comment_id
        )
        record = result.single()
        if not record:
            return None

        created_at = record["created_at"]
        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        return CommentPublic(
            id=record["id"],
            author=record["author"],
            profile_image=record["profile_image"],
            text=record["text"],
            created_at=created_at.strftime("%d %b %Y • %H:%M"),
            post_id=record["post_id"],
        )


def update_comment(comment_id: str, content: str):
    with driver.session() as session:
        session.run(
            """
            MATCH (c:Comment {id: $comment_id})
            SET c.content = $content,
                c.updated_at = datetime()
            """,
            comment_id=comment_id,
            content=content
        )
    return get_comment_by_id(comment_id)


def delete_comment(comment_id: str):
    driver.execute_query(
        "MATCH (c:Comment {id: $id}) DETACH DELETE c",
        id=comment_id,
        database_="neo4j",
    )

def search_comments(query: str, categories: list[str], skip: int, limit: int):
    records, _, _ = driver.execute_query(
        """
        MATCH (author:User)-[:CREATED]->(c:Comment)-[:ON_POST]->(p:Post)
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)

        WITH 
            c, p, author,
            [x IN collect(cat.name) | trim(toLower(x))] AS postCategories,
            [y IN $categories | trim(toLower(y))] AS filterCategories

        WHERE 
            ($query = "" OR toLower(c.content) CONTAINS toLower($query))
        AND
            (SIZE(filterCategories) = 0 
                OR ANY(catName IN postCategories WHERE catName IN filterCategories))

        MATCH (post_author:User)-[:CREATED]->(p)

        WITH DISTINCT c, p, author, post_author
        ORDER BY c.created_at DESC
        SKIP $skip
        LIMIT $limit

        RETURN
            c.id AS comment_id,
            author.username AS comment_author,
            c.content AS comment_content,
            c.created_at AS comment_created_at,
            p.id AS post_id,
            p.content AS post_content,
            p.created_at AS post_created_at,
            post_author.username AS post_author
        """,
        query=query,
        skip=skip,
        limit=limit,
        categories=categories,
        database_="neo4j"
    )

    formatted = []

    for record in records:
        item = dict(record)

        for field in ["comment_created_at", "post_created_at"]:
            dt = item[field]
            if isinstance(dt, Neo4jDateTime):
                dt = dt.to_native()
            item[field] = dt.strftime("%d %b %Y • %H:%M")

        formatted.append(item)

    return formatted

def get_all_comments_paginated(skip: int, limit: int):
    records, _, _ = driver.execute_query(
        """
        MATCH (author:User)-[:CREATED]->(c:Comment)-[:ON_POST]->(p:Post)
        MATCH (post_author:User)-[:CREATED]->(p)

        WITH c, p, author, post_author
        ORDER BY c.created_at DESC
        SKIP $skip
        LIMIT $limit

        RETURN
            c.id AS comment_id,
            author.username AS comment_author,
            c.content AS comment_content,
            c.created_at AS comment_created_at,
            p.id AS post_id,
            p.content AS post_content,
            p.created_at AS post_created_at,
            post_author.username AS post_author
        """,
        skip=skip,
        limit=limit,
        database_="neo4j"
    )

    formatted = []

    for record in records:
        item = dict(record)

        for field in ["comment_created_at", "post_created_at"]:
            dt = item[field]
            if isinstance(dt, Neo4jDateTime):
                dt = dt.to_native()
            item[field] = dt.strftime("%d %b %Y • %H:%M")

        formatted.append(item)

    return formatted