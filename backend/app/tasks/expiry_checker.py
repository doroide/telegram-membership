import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import Membership, Channel

from backend.app.services.membership_service import MembershipService

# import bot lazily to avoid circular import
from backend.bot.bot import bot


# =========================================================
# Settings
# =========================================================

CHECK_INTERVAL_SECONDS = 3600  # run every 1 hour


# =========================================================
# Helpers
# =========================================================

def parse_flags(text: str) -> dict:
    """
    reminders_sent stored as '{"3d": true}'
    convert safely → dict
    """
    try:
        return eval(text) if text else {}
    except Exception:
        return {}


def dump_flags(flags: dict) -> str:
    return str(flags)


# =========================================================
# Core loop
# =========================================================

async def run_expiry_check():
    """
    Runs forever:
    - send reminders
    - remove expired users
    """

    while True:
        try:
            async with async_session() as session:

                result = await session.execute(
                    select(Membership)
                    .where(Membership.is_active == True)
                )

                memberships = result.scalars().all()

                now = datetime.utcnow()

                for membership in memberships:

                    # lifetime never expires
                    if not membership.expiry_date:
                        continue

                    flags = parse_flags(membership.reminders_sent)

                    user_id = membership.user_id

                    # get channel info
                    channel = await session.get(Channel, membership.channel_id)
                    if not channel:
                        continue

                    chat_id = channel.telegram_chat_id

                    days_left = (membership.expiry_date - now).days

                    # =====================================================
                    # 3 DAYS REMINDER
                    # =====================================================
                    if days_left == 3 and not flags.get("3d"):
                        try:
                            await bot.send_message(
                                user_id,
                                f"⏰ Your access to *{channel.name}* expires in 3 days.\nRenew soon to avoid removal.",
                                parse_mode="Markdown"
                            )
                            flags["3d"] = True
                        except Exception:
                            pass

                    # =====================================================
                    # 1 DAY REMINDER
                    # =====================================================
                    elif days_left == 1 and not flags.get("1d"):
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ Your access to *{channel.name}* expires tomorrow.\nRenew now to continue.",
                                parse_mode="Markdown"
                            )
                            flags["1d"] = True
                        except Exception:
                            pass

                    # =====================================================
                    # EXPIRY DAY
                    # =====================================================
                    elif days_left <= 0:

                        try:
                            # remove from channel
                            await bot.ban_chat_member(chat_id, user_id)
                            await bot.unban_chat_member(chat_id, user_id)
                        except Exception:
                            pass

                        try:
                            await bot.send_message(
                                user_id,
                                f"❌ Your subscription for *{channel.name}* has expired.\n\nUse /myplan to renew.",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass

                        await MembershipService.deactivate(session, membership)
                        continue

                    # save updated flags
                    membership.reminders_sent = dump_flags(flags)

                await session.commit()

        except Exception as e:
            print("Expiry checker error:", e)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
