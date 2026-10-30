"""应用配置：从 .env 加载，缺必填项启动即报错。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8086
    app_env: str = "dev"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3310
    mysql_user: str = "root"
    # 修复-SEC005: 密码/key 不给弱默认值，缺 .env 时 fail-closed（连不上即报错）
    mysql_password: str = ""
    mysql_db: str = "eoe"

    clickhouse_host: str = "127.0.0.1"
    clickhouse_http_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    redis_host: str = "127.0.0.1"
    redis_port: int = 6381
    redis_db: int = 3

    # 修复-SEC005: 空默认值时 auth.verify_api_key 拒绝一切请求（fail-closed）
    sdk_api_key: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com"
    openai_model: str = "deepseek-chat"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


settings = Settings()
