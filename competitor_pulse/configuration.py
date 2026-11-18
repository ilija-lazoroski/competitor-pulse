import os
from pathlib import Path
from typing import Final, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from service_kit import ServiceKitBaseModel
from service_kit.configuration import ServiceConfiguration
from service_kit.logging import logger

CONFIG_PATH_ENV_KEY: Final = "CP_CONFIG_PATH"


class DatabaseConfiguration(BaseSettings, ServiceKitBaseModel):
    """PostgreSQL settings from CP_DATABASE_* environment variables."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_DATABASE_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    url: SecretStr = Field(
        min_length=1, description="The connection string: postgresql://user:password@host/db"
    )
    pool_min_size: int = Field(
        default=2, ge=0, description="Connections the pool keeps open while idle"
    )
    pool_max_size: int = Field(default=10, ge=1, description="Most connections the pool opens")
    connect_timeout_seconds: int = Field(
        default=5, gt=0, description="How long opening one new connection may take"
    )
    pool_timeout_seconds: float = Field(
        default=10,
        gt=0,
        description="How long a query waits for a free connection when all are busy",
    )
    ping_timeout_seconds: float = Field(
        default=5, gt=0, description="How long the database check (/health/db) waits for an answer"
    )
    reconnect_timeout_seconds: float = Field(
        default=300,
        gt=0,
        description=(
            "How long the pool keeps retrying in the background when the database cannot be"
            " reached, before it reports the failure and starts over"
        ),
    )

    @model_validator(mode="after")
    def _max_size_is_not_below_min_size(self) -> Self:
        """:raises ValueError: If pool_max_size is smaller than pool_min_size"""
        if self.pool_max_size < self.pool_min_size:
            raise ValueError("pool_max_size must not be smaller than pool_min_size")
        return self


class APIConfiguration(BaseSettings, ServiceKitBaseModel):
    """Settings of the competitor API from CP_API_* environment variables."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_API_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    recent_change_hours: float = Field(
        default=24,
        gt=0,
        description="A competitor counts as recently changed if its last change is this recent",
    )
    snapshots_page_size: int = Field(
        default=50, ge=1, description="Snapshots per page when the request gives no limit"
    )
    snapshots_max_page_size: int = Field(
        default=200, ge=1, description="Most snapshots a request may ask for (limit)"
    )

    @model_validator(mode="after")
    def _page_size_is_not_above_max_page_size(self) -> Self:
        """:raises ValueError: If snapshots_page_size is larger than snapshots_max_page_size"""
        if self.snapshots_page_size > self.snapshots_max_page_size:
            raise ValueError("snapshots_page_size must not be larger than snapshots_max_page_size")
        return self


class SourceConfiguration(BaseSettings, ServiceKitBaseModel):
    """Settings of the listing source from CP_SOURCE_* environment variables."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_SOURCE_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:4002"),
        description="Where the listing source runs; listings come from <base_url>/listings/<id>",
    )
    timeout_seconds: float = Field(
        default=10,
        gt=0,
        description="How long one request to the source may take, from connecting to the last byte",
    )


class PollerConfiguration(BaseSettings, ServiceKitBaseModel):
    """Settings of the poller from CP_POLLER_* environment variables."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_POLLER_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    interval_seconds: float = Field(
        default=900,
        gt=0,
        description=(
            "How often each competitor is polled; when the request budget is too small for this,"
            " every competitor falls behind evenly"
        ),
    )
    requests_per_second: float = Field(
        default=4,
        gt=0,
        description="Most requests per second to the source, for all competitors together",
    )
    max_in_flight: int = Field(
        default=50, ge=1, description="Most requests to the source waiting for an answer at once"
    )
    claim_batch_size: int = Field(
        default=10, ge=1, description="How many due competitors the poller takes at a time"
    )
    idle_seconds: float = Field(
        default=1, gt=0, description="How long the poller waits when no competitor is due"
    )
    rate_limited_pause_seconds: float = Field(
        default=1,
        gt=0,
        description="How long to pause all requests after a 429 without a usable Retry-After",
    )
    max_rate_limited_pause_seconds: float = Field(
        default=60,
        gt=0,
        description=(
            "Longest pause after a 429, whatever its Retry-After asks for, so a source that"
            " asks for hours cannot stop polling for that long"
        ),
    )

    @model_validator(mode="after")
    def _pause_is_not_above_max_pause(self) -> Self:
        """:raises ValueError: If rate_limited_pause_seconds is larger than
        max_rate_limited_pause_seconds
        """
        if self.rate_limited_pause_seconds > self.max_rate_limited_pause_seconds:
            raise ValueError(
                "rate_limited_pause_seconds must not be larger than max_rate_limited_pause_seconds"
            )
        return self


class CleanerConfiguration(BaseSettings, ServiceKitBaseModel):
    """Settings of the cleaner, which deletes old history, from CP_CLEANER_* variables."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_CLEANER_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    retention_days: int = Field(
        default=90, ge=1, description="How long snapshots are kept, by when they were fetched"
    )
    interval_seconds: float = Field(
        default=3600, gt=0, description="How often the cleaner deletes what is older"
    )
    batch_size: int = Field(
        default=10_000,
        ge=1,
        description="Most snapshots deleted in one transaction, so each one stays short",
    )


class LLMConfiguration(BaseSettings, ServiceKitBaseModel):
    """Settings of the LLM that writes change summaries, from CP_LLM_* environment variables.

    Any server with an OpenAI-compatible Chat Completions API works: the provided mock, Ollama,
    or a hosted LLM.
    """

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_LLM_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:4001/v1"),
        description="The OpenAI-compatible API; requests go to <base_url>/chat/completions",
    )
    model: str = Field(default="mock-llm", min_length=1, description="The model to ask")
    api_key: SecretStr | None = Field(
        default=None, description="Sent as a bearer token, if the LLM needs one"
    )
    timeout_seconds: float = Field(
        default=60,
        gt=0,
        description="How long one call to the LLM may take, from connecting to the last byte",
    )
    max_attempts: int = Field(
        default=3, ge=1, description="Calls per change before its summary counts as failed"
    )
    retry_backoff_seconds: float = Field(
        default=2, ge=0, description="Wait before the next attempt, multiplied by the attempt"
    )
    daily_cap: int = Field(
        default=2000, ge=0, description="Most LLM calls per UTC day, for all competitors"
    )
    max_in_flight: int = Field(
        default=4, ge=1, description="Most LLM calls waiting for an answer at once"
    )
    max_summary_chars: int = Field(
        default=500, ge=1, description="Longer answers are unusable rather than stored"
    )
    max_tokens: int = Field(
        default=150, ge=1, description="Most tokens the LLM may write; a longer answer is cut off"
    )
    max_field_chars: int = Field(
        default=1000,
        ge=1,
        description="Longer listing values are cut before they go into the prompt",
    )
    idle_seconds: float = Field(
        default=1, gt=0, description="How long the summarizer waits when no change is pending"
    )


class CompetitorPulseConfiguration(ServiceConfiguration):
    """Settings come from CP_* environment variables or the .env file at CP_CONFIG_PATH."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database: DatabaseConfiguration = Field(description="The PostgreSQL settings")
    api: APIConfiguration = Field(description="The competitor API settings")
    source: SourceConfiguration = Field(description="The listing source settings")
    poller: PollerConfiguration = Field(description="The poller settings")
    cleaner: CleanerConfiguration = Field(description="The cleaner settings")
    llm: LLMConfiguration = Field(description="The LLM settings")


def load_configuration() -> CompetitorPulseConfiguration:
    """Loads the settings from CP_* environment variables and the .env file at CP_CONFIG_PATH.

    :returns: The settings, with the database, API, source, poller, cleaner and LLM settings
              as sub-configurations
    :raises ValidationError: If a setting is missing or invalid
    """
    config_file_path = None
    if CONFIG_PATH_ENV_KEY in os.environ:
        config_file_path = Path(os.environ[CONFIG_PATH_ENV_KEY])
    logger.info(f"Loading configuration - config file: {config_file_path}")

    database = DatabaseConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    api = APIConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    source = SourceConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    poller = PollerConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    cleaner = CleanerConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    llm = LLMConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    return CompetitorPulseConfiguration(
        _env_file=config_file_path,
        database=database,
        api=api,
        source=source,
        poller=poller,
        cleaner=cleaner,
        llm=llm,  # type: ignore[call-arg]
    )
