import uuid
from neo4j.time import DateTime as Neo4jDateTime

from app.db.neo4j import get_driver
from app.schemas.user import UserInDB, UserPublic

def get_user_by_username(username: str) -> UserInDB | None:

    query = """
    MATCH (u:User {username: $username})
    RETURN u
    """

    with get_driver().session() as session:

        record = session.run(query, username=username).single()

        if not record:
            return None

        u = record["u"]

        return UserInDB(
            id=u["id"],
            username=u["username"],
            email=u.get("email"),
            password_hash=u["password_hash"],
            role=u.get("role", "USER"),
            is_active=u.get("is_active", True),
        )
    
def get_user_profile_by_username(username: str) -> UserPublic | None:
    query = """
    MATCH (u:User {username: $username})
    RETURN u
    """

    with get_driver().session() as session:
        record = session.run(query, username=username).single()

        if not record:
            return None

        u = record["u"]

        created_at = u.get("created_at")
        
        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        return UserPublic(
            id=u["id"],
            username=u["username"],
            email=u.get("email"),
            role=u.get("role", "USER"),
            bio=u.get("bio"),
            profile_image=u.get("profile_image"),
            created_at=created_at,
            is_active=u.get("is_active", True),
        )

    
def create_user(username: str, email: str, password_hash: str):

    with get_driver().session() as session:

        # check username/email
        check = session.run("""
            MATCH (u:User)
            WHERE u.username = $username OR u.email = $email
            RETURN u LIMIT 1
        """, username=username, email=email).single()

        if check:
            return None

        user_id = str(uuid.uuid4())

        result = session.run("""
            CREATE (u:User {
                id: $id,
                username: $username,
                email: $email,
                password_hash: $password_hash,
                role: "USER",
                bio: "",
                profile_image: "/static/images/default_avatar.png",
                created_at: datetime(),
                is_active: true
            })
            RETURN u
        """,
        id=user_id,
        username=username,
        email=email,
        password_hash=password_hash)

        return result.single()["u"]
