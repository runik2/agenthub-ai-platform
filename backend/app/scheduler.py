"""Separate scheduler process for APP_MODE=docker (stage 3 placeholder).

Local mode schedules inside the API process (`app/queue/inprocess.py`). The
docker contour runs this file as its own container so that scheduled agent runs
survive API restarts. No schedules exist yet — the loop only reports health.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("agenthub.scheduler")


async def main(interval_seconds: int = 30) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("scheduler started; no scheduled jobs are defined in stage 1-2")
    while True:
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
