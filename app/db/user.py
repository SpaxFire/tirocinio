import uuid
from neo4j.time import DateTime as Neo4jDateTime

from app.db.neo4j import driver
from app.schemas.user import UserInDB, UserPublic


def get_user_by_username(username: str) -> UserInDB | None:

    query = """
    MATCH (u:User {username: $username})
    RETURN u
    """

    with driver.session() as session:
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
            bio=u.get("bio"),
            profile_image=u.get("profile_image"),
            created_at=u.get("created_at").to_native() if u.get("created_at") else None,
            is_active=u.get("is_active", True),
        )
    
def get_user_profile_by_username(username: str, my_id: str | None) -> UserPublic | None:
    query = """
    MATCH (u:User {username: $username})

    OPTIONAL MATCH (u)-[:CREATED]->(p:Post)
    WITH u, count(DISTINCT p) AS post_count

    OPTIONAL MATCH (u)-[:CREATED]->(p2:Post)<-[:LIKES]-(liker:User)
    WITH u, post_count, count(liker) AS total_likes_received

    OPTIONAL MATCH (u)<-[:FOLLOWS]-(follower:User)
    WITH u, post_count, total_likes_received,
         count(DISTINCT follower) AS follower_count

    OPTIONAL MATCH (u)-[:FOLLOWS]->(following:User)
    WITH u, post_count, total_likes_received,
         follower_count,
         count(DISTINCT following) AS following_count

    OPTIONAL MATCH (me:User {id: $my_id})
    OPTIONAL MATCH (me)-[rel:FOLLOWS]->(u)

    RETURN
        u,
        post_count,
        total_likes_received,
        follower_count,
        following_count,
        CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me
    """

    with driver.session() as session:
        record = session.run(query, username=username, my_id=my_id).single()

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

            post_count=record["post_count"],
            follower_count=record["follower_count"],
            following_count=record["following_count"],
            total_likes_received=record["total_likes_received"],
            following_by_me=record["following_by_me"]
        )
    
def toggle_follow(my_id: str, username: str):
    query = """
    MATCH (me:User {id: $my_id})
    MATCH (target:User {username: $username})

    OPTIONAL MATCH (me)-[r:FOLLOWS]->(target)

    WITH me, target, r,
        CASE WHEN r IS NULL THEN true ELSE false END AS should_follow

    FOREACH (_ IN CASE WHEN should_follow THEN [1] ELSE [] END |
        MERGE (me)-[:FOLLOWS {created_at: datetime()}]->(target)
    )

    FOREACH (_ IN CASE WHEN should_follow THEN [] ELSE [1] END |
        DELETE r
    )

    WITH target, should_follow AS following
    OPTIONAL MATCH (target)<-[:FOLLOWS]-(f:User)

    RETURN following, count(f) AS follower_count
    """

    records, _, _ = driver.execute_query(
        query,
        my_id=my_id,
        username=username,
        database_="neo4j"
    )

    rec = records[0]
    return rec["following"], rec["follower_count"]

async def get_user_posts_paginated(username: str, skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User {username: $username})-[:CREATED]->(p:Post)

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
        OPTIONAL MATCH (me:User {id: $my_id})
        OPTIONAL MATCH (me)-[ml:LIKES]->(p)
        OPTIONAL MATCH (me)-[:CREATED]->(myComment:Comment)-[:ON_POST]->(p)

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
        username=username,
        my_id=my_id,
        database_="neo4j",
    )

    formatted = []

    for record in records:
        post = dict(record)
        created_at = post["created_at"]

        if isinstance(created_at, Neo4jDateTime):
            created_at = created_at.to_native()

        post["created_at"] = created_at.strftime("%d %b %Y • %H:%M")

        # sicurezza: se non ha categorie → lista vuota
        post["categories"] = post.get("categories") or []

        formatted.append(post)

    return formatted

async def get_user_comments_paginated(username: str, skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User {username: $username})-[:CREATED]->(c:Comment)
        MATCH (c)-[:ON_POST]->(p:Post)
        MATCH (postAuthor:User)-[:CREATED]->(p)

        // ---- CATEGORIES DEL POST ----
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)

        WITH u, c, p, postAuthor,
             collect(DISTINCT cat.name) AS categories

        ORDER BY c.created_at DESC
        SKIP $skip
        LIMIT $limit

        RETURN
            c.id AS comment_id,
            c.content AS comment_content,
            c.created_at AS comment_created_at,
            u.username AS comment_author,
            u.profile_image AS comment_author_image,

            p.id AS post_id,
            p.content AS post_content,
            p.created_at AS post_created_at,
            p.media_urls AS post_media_urls,

            postAuthor.username AS post_author,
            postAuthor.profile_image AS post_author_image,

            categories
        """,
        username=username,
        skip=skip,
        limit=limit,
        database_="neo4j",
    )

    formatted = []

    for record in records:
        comment = dict(record)

        # ---- Format date ----
        for field in ["comment_created_at", "post_created_at"]:
            dt = comment[field]
            if isinstance(dt, Neo4jDateTime):
                dt = dt.to_native()
            comment[field] = dt.strftime("%d %b %Y • %H:%M")

        # sicurezza: se nessuna categoria → []
        comment["categories"] = comment.get("categories") or []

        formatted.append(comment)

    return formatted

async def get_user_likes_paginated(username: str, skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User {username: $username})-[:LIKES]->(p:Post)

        OPTIONAL MATCH (p)<-[:CREATED]-(author:User)

        // ---- LIKE COUNT ----
        OPTIONAL MATCH (p)<-[:LIKES]-(liker:User)
        WITH u, p, author, count(DISTINCT liker) AS like_count

        // ---- COMMENT COUNT ----
        OPTIONAL MATCH (p)<-[:ON_POST]-(c:Comment)
        WITH u, p, author, like_count, count(DISTINCT c) AS comment_count

        // ---- CATEGORIES ----
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(cat:Category)
        WITH u, p, author, like_count, comment_count,
             collect(DISTINCT cat.name) AS categories

        // ---- CURRENT USER STATE ----
        OPTIONAL MATCH (me:User {id: $my_id})
        OPTIONAL MATCH (me)-[ml:LIKES]->(p)
        OPTIONAL MATCH (me)-[:CREATED]->(myComment:Comment)-[:ON_POST]->(p)

        WITH u, p, author, like_count, comment_count, categories,
             ml, count(DISTINCT myComment) AS my_comments

        ORDER BY p.created_at DESC
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
            CASE WHEN ml IS NULL THEN false ELSE true END AS liked_by_me,
            CASE WHEN my_comments > 0 THEN true ELSE false END AS commented_by_me
        """,
        skip=skip,
        limit=limit,
        username=username,
        my_id=my_id,
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

def get_user_with_counts(username: str, my_id: str | None):

    query = """
    MATCH (u:User {username: $username})

    /* ---------------- POST COUNT ---------------- */
    OPTIONAL MATCH (u)-[:CREATED]->(p:Post)
    WITH u, count(DISTINCT p) AS post_count

    /* ---------------- TOTAL LIKES RECEIVED ---------------- */
    OPTIONAL MATCH (u)-[:CREATED]->(p2:Post)<-[:LIKES]-(liker:User)
    WITH u, post_count, count(liker) AS total_likes_received

    /* ---------------- FOLLOWER COUNT ---------------- */
    OPTIONAL MATCH (u)<-[:FOLLOWS]-(f:User)
    WITH u, post_count, total_likes_received,
        count(DISTINCT f) AS follower_count

    /* ---------------- FOLLOWING COUNT ---------------- */
    OPTIONAL MATCH (u)-[:FOLLOWS]->(f2:User)
    WITH u, post_count, total_likes_received,
        follower_count,
        count(DISTINCT f2) AS following_count

    /* ---------------- FOLLOWING BY ME ---------------- */
    OPTIONAL MATCH (me:User {id: $my_id})
    OPTIONAL MATCH (me)-[rel:FOLLOWS]->(u)

    RETURN
        u,
        post_count,
        total_likes_received,
        follower_count,
        following_count,
        CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me
    """

    records, _, _ = driver.execute_query(
        query,
        username=username,
        my_id=my_id,
        database_="neo4j"
    )

    if not records:
        return None

    record = records[0]
    u = record["u"]

    return {
        **dict(u),
        "post_count": record["post_count"],
        "total_likes_received": record["total_likes_received"],
        "follower_count": record["follower_count"],
        "following_count": record["following_count"],
        "following_by_me": record["following_by_me"],
    }

def get_followers_paginated(username: str, skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        // Trovo utente del profilo
        MATCH (u:User {username: $username})
        OPTIONAL MATCH (me:User {id: $my_id})
        MATCH (f:User)-[:FOLLOWS]->(u)

        // Paginazione prima per evitare di portare tutti i follower in memoria
        WITH f, me
        ORDER BY f.username
        SKIP $skip
        LIMIT $limit

        OPTIONAL MATCH (me)-[rel:FOLLOWS]->(f)

        RETURN
            f.id AS id,
            f.username AS username,
            f.bio AS bio,
            f.profile_image AS profile_image,
            CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me,

            // Conteggio follower di f
            SIZE([(f)<-[:FOLLOWS]-(:User) | 1]) AS follower_count
        """,
        username=username,
        skip=skip,
        limit=limit,
        my_id=my_id,
        database_="neo4j"
    )

    return [dict(record) for record in records]

def get_following_paginated(username: str, skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        // Trovo utente profilo
        MATCH (u:User {username: $username})

        // Utenti che segue
        MATCH (u)-[:FOLLOWS]->(f:User)

        // Paginazione prima per evitare di portare tutti i follower in memoria
        WITH f
        ORDER BY f.username
        SKIP $skip
        LIMIT $limit

        // Verifico se io seguo f
        OPTIONAL MATCH (me:User {id: $my_id})
        OPTIONAL MATCH (me)-[rel:FOLLOWS]->(f)

        RETURN
            f.id AS id,
            f.username AS username,
            f.bio AS bio,
            f.profile_image AS profile_image,
            CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me,

            // Numero follower di f
            SIZE([(f)<-[:FOLLOWS]-(:User) | 1]) AS follower_count
        """,
        username=username,
        skip=skip,
        limit=limit,
        my_id=my_id,
        database_="neo4j"
    )

    return [dict(record) for record in records]


def create_user(username: str, email: str, password_hash: str):

    with driver.session() as session:

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

def update_profile(user_id: str, username: str, bio: str, profile_image: str):

    with driver.session() as session:

        # controllo username duplicato (se cambiato)
        check = session.run("""
            MATCH (u:User)
            WHERE u.username = $username AND u.id <> $user_id
            RETURN u LIMIT 1
        """, username=username, user_id=user_id).single()

        if check:
            return False

        session.run("""
            MATCH (u:User {id: $user_id})
            SET u.username = $username,
                u.bio = $bio,
                u.profile_image = $profile_image
        """,
        user_id=user_id,
        username=username,
        bio=bio,
        profile_image=profile_image)

        return True

def update_email(user_id: str, email: str):

    with driver.session() as session:

        check = session.run("""
            MATCH (u:User)
            WHERE u.email = $email AND u.id <> $user_id
            RETURN u LIMIT 1
        """, email=email, user_id=user_id).single()

        if check:
            return False  # email già usata

        session.run("""
            MATCH (u:User {id: $user_id})
            SET u.email = $email
        """, user_id=user_id, email=email)

        return True

def update_password(user_id: str, password_hash: str):
    with driver.session() as session:
        session.run("""
            MATCH (u:User {id: $user_id})
            SET u.password_hash = $password_hash
        """,
        user_id=user_id,
        password_hash=password_hash)

    return True

def update_role(user_id: str, role: str) -> bool:
    with driver.session() as session:
        session.run("""
            MATCH (u:User {id: $user_id})
            SET u.role = $role
            RETURN u
        """,
        user_id=user_id,
        role=role)

    return True

def deactivate_user(user_id: str):
    with driver.session() as session:
        session.run("""
            MATCH (u:User {id: $user_id})
            WHERE u.is_active = true
            SET u.is_active = false
            RETURN u
        """, user_id=user_id)

def reactivate_user(user_id: str):
    with driver.session() as session:
        session.run("""
        MATCH (u:User {id: $user_id})
        WHERE u.is_active = false
        SET u.is_active = true
        RETURN u
        """, user_id=user_id)

def search_users(query: str, bio: str, skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User)
        WHERE
            ($query = "" OR toLower(u.username) CONTAINS toLower($query))
        AND
            ($bio = "" OR u.bio IS NOT NULL AND toLower(u.bio) CONTAINS toLower($bio))

        WITH u
        ORDER BY u.username
        SKIP $skip
        LIMIT $limit

        OPTIONAL MATCH (me:User {id: $my_id})
        OPTIONAL MATCH (me)-[rel:FOLLOWS]->(u)

        RETURN
            u.id AS id,
            u.username AS username,
            u.bio AS bio,
            u.profile_image AS profile_image,
            CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me,
            SIZE([(u)<-[:FOLLOWS]-(:User) | 1]) AS follower_count
        """,
        query=query,
        skip=skip,
        limit=limit,
        my_id=my_id,
        bio=bio,
        database_="neo4j"
    )

    return [dict(record) for record in records]

def get_all_users_paginated(skip: int, limit: int, my_id: str | None):
    records, _, _ = driver.execute_query(
        """
        MATCH (u:User)
        WITH u
        ORDER BY u.username
        SKIP $skip
        LIMIT $limit

        OPTIONAL MATCH (me:User {id: $my_id})
        OPTIONAL MATCH (me)-[rel:FOLLOWS]->(u)

        RETURN
            u.id AS id,
            u.username AS username,
            u.bio AS bio,
            u.profile_image AS profile_image,
            CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me,
            SIZE([(u)<-[:FOLLOWS]-(:User) | 1]) AS follower_count
        """,
        skip=skip,
        limit=limit,
        my_id=my_id,
        database_="neo4j"
    )

    return [dict(record) for record in records]

def discover_users_from_followed(
    my_id: str,
    skip: int,
    limit: int
):
    records, _, _ = driver.execute_query(
        """
        MATCH (me:User {id: $my_id})-[:FOLLOWS]->(f:User)
        MATCH (f)-[:FOLLOWS]->(u:User)

        WHERE u.id <> $my_id
        AND NOT (me)-[:FOLLOWS]->(u)

        WITH u, count(DISTINCT f) AS score

        ORDER BY score DESC, u.username
        SKIP $skip
        LIMIT $limit

        OPTIONAL MATCH (me2:User {id: $my_id})
        OPTIONAL MATCH (me2)-[rel:FOLLOWS]->(u)

        RETURN
            u.id AS id,
            u.username AS username,
            u.bio AS bio,
            u.profile_image AS profile_image,
            score,
            CASE WHEN rel IS NULL THEN false ELSE true END AS following_by_me,
            SIZE([(u)<-[:FOLLOWS]-(:User) | 1]) AS follower_count
        """,
        my_id=my_id,
        skip=skip,
        limit=limit,
        database_="neo4j"
    )

    return [dict(record) for record in records]