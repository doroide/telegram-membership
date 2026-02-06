from datetime import datetime
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import Membership
from backend.bot.bot import bot


async def run_expiry_check():

    async with async_session() as session:
        result = await session.execute(
            select(Membership).where(Membership.is_active == True)
        )

        memberships = result.scalars().all()

        now = datetime.utcnow()

        for m in memberships:
            if m.expiry_date and m.expiry_date < now:
                m.is_active = False
                await session.commit()

                try:
                    await bot.send_message(
                        m.user.telegram_id,
                        "❌ Your membership expired. Please renew."
                    )
                except:
                    pass
