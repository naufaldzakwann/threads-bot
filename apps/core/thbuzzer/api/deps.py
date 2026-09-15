from fastapi import Request

from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncSession:  # type: ignore[misc]
    async with request.app.state.sessions() as s:
        yield s  # type: ignore
