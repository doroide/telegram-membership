import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://telegram_membership_user:ONtLUdEMkW6ljm7npsAZZDBjXu7ayRBy@dpg-d5cuqger433s73a5l4l0-a.virginia-postgres.render.com/telegram_membership")

# Convert to async URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

descriptions = {
    12: """✅ Premium adult web series
🎬 New episodes added daily
📱 HD quality content
🔥 Exclusive content only here
🔞 18+ only""",

    13: """✅ Uncut web series collection
🎬 Fresh content every day
📱 HD quality streaming
🔥 No cuts, full content
🔞 18+ only""",

    14: """✅ Premium movies collection
🎬 Latest releases
📱 HD & 4K quality
🔥 Exclusive titles
🎭 All genres available""",

    15: """✅ Full Savita Bhabhi comic series
📚 Complete collection
🎨 HD quality images
🔥 New issues added regularly
🔞 18+ only""",
}

async def update():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        for channel_id, desc in descriptions.items():
            await conn.execute(
                text("UPDATE channels SET description = :desc WHERE id = :id"),
                {"desc": desc, "id": channel_id}
            )
            print(f"✅ Updated channel {channel_id}")
    await engine.dispose()
    print("✅ All descriptions updated successfully!")

asyncio.run(update())