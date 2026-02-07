from fastapi.templating import Jinja2Templates

# Database connection data for Neo4j
URI = "neo4j+s://4148cbd8.databases.neo4j.io"
AUTH = ("neo4j", "Na-BH0ELGuexhejtnBBsUQqDl-KoJpA8soPaelB_gOI")

# Jinja2 Templates initialization
templates = Jinja2Templates(directory="templates")