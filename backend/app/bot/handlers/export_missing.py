import io
import csv
from difflib import SequenceMatcher
from aiogram import Router
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import PaymentHistory, User

router = Router()

# threshold=0.98 ensures that "Shree Kishan" and "Shree K" are treated as DIFFERENT.
# Only near-identical strings (e.g. "Shree Kishan" vs "Shree Kishan ") will be skipped.
def is_strictly_similar(name1, name2, threshold=0.98):
    return SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio() >= threshold

@router.message(Command("export_missing"))
async def export_missing_users(message: Message):
    await message.answer("⏳ Running strict gap analysis...")

    async with async_session() as session:
        # Fetch all legacy records and all live users
        legacy_res = await session.execute(select(PaymentHistory).order_by(PaymentHistory.name))
        legacy_records = legacy_res.scalars().all()
        
        live_res = await session.execute(select(User))
        live_users = [u.full_name.lower().strip() for u in live_res.scalars().all()]

    # Filter: Keep legacy records ONLY if no strictly similar match exists in live users
    missing_data = []
    for rec in legacy_records:
        legacy_name = rec.name.strip()
        # If the legacy name doesn't match any live user within our strict 98% threshold
        if not any(is_strictly_similar(legacy_name, live_name) for live_name in live_users):
            missing_data.append(rec)

    if not missing_data:
        await message.answer("✅ Good news! All legacy members have been matched in the bot.")
        return

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Name", "Channel Name", "Amount"])
    
    # Sort by Name so entries are grouped together for each user
    missing_data.sort(key=lambda x: x.name)
    
    for rec in missing_data:
        writer.writerow([rec.date, rec.name, rec.group_name, rec.amount])
    
    file_bytes = output.getvalue().encode("utf-8")
    
    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename="missing_legacy_users.csv"),
        caption=f"📋 Found {len(missing_data)} legacy entries for users who have not joined the bot."
    )