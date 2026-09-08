from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://repomind:repomind@localhost:5432/repomind"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    repo_storage_dir: str = "../data/repos"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
