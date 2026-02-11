from app.db.neo4j import get_driver
from app.schemas.comment import CommentPublic
from datetime import datetime


async def get_comments_of_post(post_id: str) -> list[CommentPublic]:
    query = """
    MATCH (p:Post {id: $post_id})
    MATCH (u:User)-[:CREATED]->(c:Comment)-[:ON_POST]->(p)
    RETURN
        c.content AS text,
        u.username AS author,
        c.created_at AS created_at
    ORDER BY c.created_at ASC
    """

    with get_driver().session() as session:
        result = session.run(query, post_id=post_id)

        return [
                CommentPublic(
                    author=record["author"],
                    text=record["text"],
                    created_at=record["created_at"].to_native(),
                )
                for record in result
                ]
