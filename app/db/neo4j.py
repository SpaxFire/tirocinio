from neo4j import GraphDatabase
from app.core.config import AUTH, URI

driver = GraphDatabase.driver(URI, auth=AUTH)
driver.verify_connectivity()

def get_driver():
    return driver