import asyncio

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import SecretStr
from sqlalchemy import NullPool, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from competitor_pulse.configuration import DatabaseConfiguration


def to_sqlalchemy_url(database_url: SecretStr) -> URL:
    """postgresql://… URLs need the psycopg (v3) driver name for SQLAlchemy."""
    return make_url(database_url.get_secret_value()).set(drivername="postgresql+psycopg")


class Database:
    """SQLAlchemy Core on top of a psycopg connection pool.

    SQLAlchemy's own pooling is off (NullPool): every connection comes from the psycopg pool,
    and close_returns=True makes SQLAlchemy's close() hand the connection back to that pool
    instead of closing it.
    """

    def __init__(
        self,
        pool: AsyncConnectionPool[AsyncConnection],
        engine: AsyncEngine,
        ping_timeout_seconds: float,
    ):
        self._pool = pool
        self._engine = engine
        self._ping_timeout_seconds = ping_timeout_seconds

    @classmethod
    def from_configuration(cls, config: DatabaseConfiguration) -> "Database":
        pool = AsyncConnectionPool(
            config.url.get_secret_value(),
            min_size=config.pool_min_size,
            max_size=config.pool_max_size,
            kwargs={"connect_timeout": config.connect_timeout_seconds},
            check=AsyncConnectionPool.check_connection,
            timeout=config.pool_timeout_seconds,
            reconnect_timeout=config.reconnect_timeout_seconds,
            close_returns=True,
            open=False,
        )
        engine = create_async_engine(
            "postgresql+psycopg://", poolclass=NullPool, async_creator=pool.getconn
        )
        return cls(pool, engine, config.ping_timeout_seconds)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def open(self) -> None:
        await self._pool.open(wait=False)

    async def ping(self) -> None:
        async with asyncio.timeout(self._ping_timeout_seconds):
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
        await self._pool.close()
