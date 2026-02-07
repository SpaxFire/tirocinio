from app.db.neo4j import get_driver

def get_all_comments():
    driver = get_driver()
    records, _, _ = driver.execute_query(
        """
        MATCH (c:Comment)
        RETURN c.id as id, c.user as user, c.text as text, c.verified as verified
        """,
        database_="neo4j",
    )
    return records