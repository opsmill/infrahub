from pydantic_settings import BaseSettings


class Config(BaseSettings):
    url: str = "http://localhost:8000"
    api_token: str = "06438eb2-8019-4776-878c-0941b1f1d1ec"
    server_container: str = "infrahub-infrahub-server-1"
    db_container: str = "infrahub-database-1"
    db_volume: str = "infrahub_database_data"
    test_task_iterations: int = 1
    username: str = "admin"
    password: str = "infrahub"
    db_username: str = "neo4j"
    db_password: str = "admin"
    db_protocol: str = "bolt"
    db_host: str = "localhost"
    db_port: int = 7687
    client_timeout: int = 1000

    node_amount: int = 10
    attrs_amount: int = 0
    rels_amount: int = 0
    changes_amount: int = 0

    current_stage: str = ""

    failed_requests: int = 0

    class Config:
        env_prefix = "INFRAHUB_"
        case_sensitive = False


config = Config()
