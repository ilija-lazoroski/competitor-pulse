import os
from pathlib import Path
from typing import Final, Self

from pydantic import Field, SecretStr, model_validator
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

    @model_validator(mode="after")
    def _max_size_is_not_below_min_size(self) -> Self:
        if self.pool_max_size < self.pool_min_size:
            raise ValueError("pool_max_size must not be smaller than pool_min_size")
        return self


class CompetitorPulseConfiguration(ServiceConfiguration):
    """Settings come from CP_* environment variables or the .env file at CP_CONFIG_PATH."""

    model_config = SettingsConfigDict(
        env_parse_none_str="None",
        env_prefix="CP_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database: DatabaseConfiguration = Field(description="The PostgreSQL settings")


def load_configuration() -> CompetitorPulseConfiguration:
    config_file_path = None
    if CONFIG_PATH_ENV_KEY in os.environ:
        config_file_path = Path(os.environ[CONFIG_PATH_ENV_KEY])
    logger.info(f"Loading configuration - config file: {config_file_path}")

    database = DatabaseConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    return CompetitorPulseConfiguration(
        _env_file=config_file_path, database=database  # type: ignore[call-arg]
    )
