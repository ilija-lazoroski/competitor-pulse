import asyncio
import signal

from service_kit.logging import configure_logger, logger

from competitor_pulse.configuration import load_configuration
from competitor_pulse.database import Database
from competitor_pulse.poller.cleaner import Cleaner
from competitor_pulse.poller.listing_source import HTTPListingSource
from competitor_pulse.poller.llm_client import OpenAILLMClient
from competitor_pulse.poller.poll_repository import PostgresPollRepository
from competitor_pulse.poller.poller import Poller
from competitor_pulse.poller.rate_limiter import RateLimiter
from competitor_pulse.poller.retention_repository import PostgresRetentionRepository
from competitor_pulse.poller.summarizer import Summarizer
from competitor_pulse.poller.summary_repository import PostgresSummaryRepository


async def run() -> None:
    """Loads the configuration, then polls, cleans and summarizes until SIGTERM or SIGINT.

    :raises ValidationError: If a setting is missing or invalid
    """
    config = load_configuration()
    configure_logger(config.log_level, config.log_directory, config.pretty_print_logs)
    logger.info("Poller configuration", config=config)

    database = Database.from_configuration(config.database)
    source = HTTPListingSource.from_configuration(config.source)
    poller = Poller(
        PostgresPollRepository(database.engine),
        source,
        RateLimiter(config.poller.requests_per_second),
        config.poller,
    )
    cleaner = Cleaner(PostgresRetentionRepository(database.engine), config.cleaner)
    llm = OpenAILLMClient.from_configuration(config.llm)
    summarizer = Summarizer(PostgresSummaryRepository(database.engine), llm, config.llm)

    current = asyncio.current_task()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop_signal, current.cancel)  # type: ignore[union-attr]

    await database.open()
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(poller.run())
            tasks.create_task(cleaner.run())
            tasks.create_task(summarizer.run())
    except asyncio.CancelledError:
        logger.info("Poller stopping")
    finally:
        await source.close()
        await llm.close()
        await database.close()


def main():
    """Starts the poller; it runs until it receives SIGTERM or SIGINT."""
    asyncio.run(run())
