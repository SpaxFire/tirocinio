import uuid
from app.db.neo4j import get_driver
from app.schemas.user import UserInDB


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
                profile_image: "",
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
