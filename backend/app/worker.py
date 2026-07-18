import asyncio
import logging
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.campaigns import process_due_campaigns
from app.services.loyalty import process_birthday_bonuses, process_expired_points

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("loyalyn-worker")
settings = get_settings()


async def main():
    logger.info("Loyalyn campaign worker started")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                expired = await process_expired_points(db)
                birthdays = await process_birthday_bonuses(db)
                processed = await process_due_campaigns(db)
                if expired:
                    logger.info("Expired %s point bucket(s)", expired)
                if birthdays:
                    logger.info("Applied %s birthday bonus(es)", birthdays)
                if processed:
                    logger.info("Processed %s campaign(s)", processed)
        except Exception:
            logger.exception("Campaign worker iteration failed")
        await asyncio.sleep(max(5, settings.worker_poll_seconds))


if __name__ == "__main__":
    asyncio.run(main())
