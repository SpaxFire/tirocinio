from uuid import uuid4
from app.db.neo4j import get_driver

def search_categories(category_search: str):
    driver = get_driver()
    records, _, _ = driver.execute_query(
        """
        MATCH (c:Category)
        WHERE c.name CONTAINS $category_search
        RETURN c.id as id, c.name as name
        """,
        {"category_search": category_search},
        database_="neo4j",
    )
    return records