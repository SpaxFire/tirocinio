from uuid import uuid4
from app.db.neo4j import driver
from neo4j.time import DateTime as Neo4jDateTime

from app.schemas.comment import CommentPublic


async def get_comments_of_post(post_id: str) -> list[CommentPublic]:
    query = """
    MATCH (p:Post {id: $post_id})
    MATCH (u:User)-[:CREATED]->(c:Comment)-[:ON_POST]->(p)
    RETURN
        c.id AS id,
        c.content AS text,
        u.username AS author,
        u.profile_image AS profile_image,
        c.created_at AS created_at
    ORDER BY c.created_at DESC
    """

    with driver.session() as session:
        result = session.run(query, post_id=post_id)

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