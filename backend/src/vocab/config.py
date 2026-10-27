"""Чтение окружения — единственное место в проекте, где оно происходит."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": в контейнер приезжают и переменные постгреса (POSTGRES_*),
    # они нужны самой базе, а не приложению.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Пусто у бота осознанно: он в базу не ходит, и DSN в его окружении
    # только приглашал бы туда пойти. API проверяет непустоту при старте.
    database_url: str = ""
    bot_token: str
    api_token: str
    owner_tg_id: int

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    # Запросов к ИИ на пользователя в день. Бот публичный, платим мы;
    # уже переведённые слова из общего словаря лимит не тратят.
    llm_daily_limit: int = 30

    # Бот и MCP ходят в API по имени сервиса в docker-сети: снаружи запрос
    # уехал бы через Caddy и внешний канал ради вызова соседа по локальной сети.
    api_base_url: str = "http://api:8000"

    # Домен нужен не только Caddy: fastmcp проверяет заголовок Host у
    # запросов к /mcp и незнакомый хост отвергает.
    domain: str = ""

    # Часовой пояс владельца. От него зависят «сколько сегодня» и время
    # напоминаний — UTC здесь дал бы сдвиг на полдня.
    tz: str = "UTC"
    reminder_hours: str = "9,20"

    log_level: str = "INFO"
    queue_limit: int = Field(default=50, ge=1, le=200)

    @property
    def miniapp_url(self) -> str:
        # Telegram открывает мини-апп только по HTTPS, поэтому схема жёстко
        # зашита: http сюда попадёт разве что опечаткой в DOMAIN.
        return f"https://{self.domain}/app/"

    @property
    def reminder_hour_list(self) -> list[int]:
        return [int(h) for h in self.reminder_hours.split(",") if h.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
