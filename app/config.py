from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_token: str
    github_webhook_secret: str
    github_repo: str
    github_docs_repo: str = ""
    anthropic_api_key: str
    database_url: str = "sqlite+aiosqlite:///./docs_agent.db"
    environment: str = "development"
    log_level: str = "INFO"
    default_approver: str
    confidence_threshold: float = 0.5
    notion_token: str = ""
    notion_database_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def docs_repo(self) -> str:
        return self.github_docs_repo or self.github_repo


settings = Settings()
