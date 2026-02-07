from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import Channel, User

router = Router()

# =====================================================
# /start
# =====================================================
@router.message(Command("start"))
async def start_handler(message: Message):
    print(f"START command from user {message.from_user.id}")
    
    # Create user if not exists
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                plan_slab="A"
            )
            session.add(user)
            await session.commit()
            print(f"✅ Created new user: {message.from_user.id}")
        
        # Get public channels
        result = await session.execute(
            select(Channel).where(Channel.is_public == True)
        )
        channels = result.scalars().all()
    
    if not channels:
        await message.answer("⚠️ No channels available right now.")
        return
    
    keyboard = []
    for ch in channels:
        keyboard.append(
            [InlineKeyboardButton(
                text=ch.name,
                callback_data=f"userch_{ch.id}"  # ✅ FIXED: matches channel_plans.py
            )]
        )
    
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        "🎬 <b>Available Channels</b>\n\nSelect a channel to view plans 👇",
        reply_markup=markup,
        parse_mode="HTML"
    )
    print(f"✅ Sent {len(channels)} channels to user")