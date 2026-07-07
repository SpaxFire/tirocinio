import os

from fastapi.templating import Jinja2Templates

# Database connection data for Neo4j.
# Defaults target local host execution and can be overridden via .env/.env.docker.
URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
AUTH = (
	os.getenv("NEO4J_USER", "neo4j"),
	os.getenv("NEO4J_PASSWORD", "neo4jpassword"),
)

# Jinja2 Templates initialization
templates = Jinja2Templates(directory="templates")