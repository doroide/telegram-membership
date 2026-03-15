import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://telegram_membership_user:ONtLUdEMkW6ljm7npsAZZDBjXu7ayRBy@dpg-d5cuqger433s73a5l4l0-a.virginia-postgres.render.com/telegram_membership")

# Convert to async URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

descriptions = {
    12: """📺 Webseries Collection

🔥 Huge collection of webseries from 380+ OTT platforms.

📺 Platforms include:
Ullu • Atrangi • Jugnu • AkkuOTT • Dyzreplay • Kahaniplay and many more.

✨ Features:
- 5000+ webseries already uploaded
- Collection from 2020 till now
- Large organized library
- HD quality videos

📊 Daily Updates
New webseries are uploaded as soon as they release.

💎 Lifetime Membership
Pay once and get lifetime access.

If the group ever gets removed, you will receive free access to the new group.""",

    13: """🔥 Premium collection of Uncut & Uncensored Webseries from multiple OTT platforms.

📺 330+ OTT Platforms Covered, including:
MoodX • MeetX • Xtreme • Yessma • NeonX • Boomex • Navarasa • and many more.

✨ Features:
- Uncut & uncensored content
- HD quality videos
- Large and organized collection
- Regular new uploads

💎 Lifetime Membership
Pay only once and get lifetime access.

If the group is ever banned, you will receive free access to the new group.""",

    14: """🔥 Huge library of 4000+ movies & webseries in one place.

📺 Content Includes:
- Latest movies & webseries
- Bollywood & South movies
- Hindi dubbed & English movies
- Popular OTT platform content

⭐ Platforms Covered:
Netflix • Amazon Prime • Disney+ Hotstar • JioCinema • Zee5 • SonyLiv • MX Player • AltBalaji and more.

✨ Features:
- Direct videos (No links / No ads)
- HD quality content
- Large organized library
- Daily new updates

💎 Lifetime Membership
Pay once and get lifetime access""",

    15: """🔥 Complete collection of the famous Savita Bhabhi digital comics.

📖 Content Categories:
- Classic Savita Bhabhi story arcs
- Romantic & bold comic episodes
- Desi themed comic stories
- Special episode collections
⭐ 200+ comic categories included

✨ Features:
- High-quality comic pages
- Organized comic collections
- Easy mobile reading format
- Huge comic library

💎 Lifetime Membership
Pay once and get lifetime access.
If the group is ever removed, you will receive free access to the new group.""",
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