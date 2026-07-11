from datetime import UTC, datetime

from sqlalchemy import delete

from app.database import async_session_maker
from app.models import PasswordResetSession, PendingSignup, PendingAuthPayload


async def cleanup_expired_auth_rows() -> None:
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        await session.execute(delete(PasswordResetSession).where(PasswordResetSession.expires_at <= now))
        await session.execute(delete(PendingSignup).where(PendingSignup.expires_at <= now))
        await session.execute(delete(PendingAuthPayload).where(PendingAuthPayload.expires_at <= now))
        await session.commit()
