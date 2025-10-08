from config import GRAPHQL_ENABLED
from core.config_loader import raw_config
from .client import GraphQLClientAdapter

graphql_client = None

if GRAPHQL_ENABLED:
    endpoint = raw_config.get("hasura_graphql_endpoint")
    admin_secret = raw_config.get("hasura_admin_secret")
    graphql_client = GraphQLClientAdapter(endpoint=endpoint, admin_secret=admin_secret)