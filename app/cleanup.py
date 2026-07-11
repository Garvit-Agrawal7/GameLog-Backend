from datetime import UTC, datetime

import logging

from sqlalchemy import delete
from sqlalchemy.exc import ProgrammingError

from app.database import async_session_maker
from app.models import PasswordResetSession, PendingSignup, PendingAuthPayload


logger = logging.getLogger(__name__)


async def cleanup_expired_auth_rows() -> None:
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        try:
            await session.execute(delete(PasswordResetSession).where(PasswordResetSession.expires_at <= now))
            await session.execute(delete(PendingSignup).where(PendingSignup.expires_at <= now))
            await session.execute(delete(PendingAuthPayload).where(PendingAuthPayload.expires_at <= now))
            await session.commit()
        except ProgrammingError:
            await session.rollback()
            logger.warning("Skipping auth cleanup because one or more auth tables are missing")
