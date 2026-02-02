import csv
import os
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment, Membership, Channel
from backend.bot.utils.admin import is_admin

router = Router()


# ======================================================
# Helpers
# ======================================================

TMP_DIR = "tmp_exports"

os.makedirs(TMP_DIR, exist_ok=True)


# ======================================================
# /export_users
# ======================================================

@router.message(F.text == "/export_users")
async def export_users(message: Message):

    if not is_admin(message.from_user.id):
        return

    filepath = f"{TMP_DIR}/users.csv"

    async with async_session() as session:

        result = await session.execute(select(User))
        users = result.scalars().all()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow([
                "user_id",
                "username",
                "full_name",
                "tier",
                "total_spent",
                "created_at"
            ])

            for u in users:
                writer.writerow([
                    u.id,
                    u.username,
                    u.full_name,
                    u.tier,
                    float(u.total_spent or 0),
                    u.created_at
                ])

    await message.answer_document(FSInputFile(filepath))


# ======================================================
# /export_payments
# ======================================================

@router.message(F.text == "/export_payments")
async def export_payments(message: Message):

    if not is_admin(message.from_user.id):
        return

    filepath = f"{TMP_DIR}/payments.csv"

    async with async_session() as session:

        result = await session.execute(select(Payment))
        payments = result.scalars().all()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow([
                "payment_id",
                "user_id",
                "membership_id",
                "amount",
                "currency",
                "status",
                "created_at"
            ])

            for p in payments:
                writer.writerow([
                    p.id,
                    p.user_id,
                    p.membership_id,
                    float(p.amount),
                    p.currency,
                    p.status,
                    p.created_at
                ])

    await message.answer_document(FSInputFile(filepath))


# ======================================================
# /export_memberships (bonus useful)
# ======================================================

@router.message(F.text == "/export_memberships")
async def export_memberships(message: Message):

    if not is_admin(message.from_user.id):
        return

    filepath = f"{TMP_DIR}/memberships.csv"

    async with async_session() as session:

        result = await session.execute(select(Membership))
        memberships = result.scalars().all()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow([
                "membership_id",
                "user_id",
                "channel",
                "plan",
                "expiry_date",
                "is_active"
            ])

            for m in memberships:
                channel = await session.get(Channel, m.channel_id)

                writer.writerow([
                    m.id,
                    m.user_id,
                    channel.name if channel else "",
                    m.plan,
                    m.expiry_date,
                    m.is_active
                ])

    await message.answer_document(FSInputFile(filepath))
