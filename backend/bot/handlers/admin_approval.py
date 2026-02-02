from aiogram import Router, F
from aiogram.types import Message

from backend.app.db.session import async_session
from backend.app.db.models import AccessRequest, Channel
from backend.app.services.membership_service import MembershipService
from backend.bot.utils.admin import is_admin

router = Router()


@router.message(F.text.startswith("/approve_request"))
async def approve_request(message: Message):

    if not is_admin(message.from_user.id):
        return

    try:
        _, data = message.text.split(" ", 1)
        request_id, plan, amount = [x.strip() for x in data.split("|")]

        request_id = int(request_id)
        amount = float(amount)

    except Exception:
        await message.answer(
            "Usage:\n"
            "/approve_request request_id | 1m | 199"
        )
        return

    async with async_session() as session:

        req = await session.get(AccessRequest, request_id)

        if not req or req.status != "pending":
            await message.answer("Invalid request id.")
            return

        channel = await session.get(Channel, req.channel_id)

        membership = await MembershipService.create_membership(
            session=session,
            user_id=req.user_id,
            channel_id=req.channel_id,
            plan=plan,
            amount=amount
        )

        invite = await message.bot.create_chat_invite_link(
            chat_id=channel.telegram_chat_id,
            member_limit=1
        )

        await message.bot.send_message(
            req.user_id,
            f"✅ Access approved for *{channel.name}*\n\n"
            f"Plan: {plan}\n"
            f"Expires: {membership.expiry_date or 'Lifetime'}\n\n"
            f"Join here:\n{invite.invite_link}",
            parse_mode="Markdown"
        )

        req.status = "approved"
        await session.commit()

    await message.answer("✅ Membership created & invite sent.")
