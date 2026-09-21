from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    instance_name: str = "api-1"

    database_url: str = "postgresql+psycopg2://rubric:rubric@postgres:5432/rubric"
    db_pool_size: int = 20
    db_max_overflow: int = 0
    db_pool_timeout: int = 30

    model_endpoint: str = "http://stub-model:9000"
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    model_read_timeout: int = 30

    # Queue configuration. See docs/ADR-003-async-scoring.md.
    sqs_queue_url: str = "http://localstack:4566/000000000000/rubric-scoring"
    sqs_dlq_url: str = "http://localstack:4566/000000000000/rubric-scoring-dlq"
    sqs_visibility_timeout: int = 60
    sqs_max_receive_count: int = 5

    aws_endpoint_url: str = "http://localstack:4566"
    aws_region: str = "us-east-1"


settings = Settings()
