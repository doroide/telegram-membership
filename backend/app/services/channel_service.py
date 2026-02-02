from sqlalchemy import select
from backend.app.db.models import Channel


class ChannelService:

    @staticmethod
    async def get_active_channels(session):
        result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        return result.scalars().all()

    @staticmethod
    async def get_channel(session, channel_id: int):
        return await session.get(Channel, channel_id)

    @staticmethod
    async def disable_channel(session, channel_id: int):
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = False
            await session.commit()
