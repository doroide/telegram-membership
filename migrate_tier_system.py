"""
Migration script to add tier tracking columns to users table
Run this once to update your database schema
"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://telegram_membership_user:ONtLUdEMkW6ljm7npsAZZDBjXu7ayRBy@dpg-d5cuqger433s73a5l4l0-a.virginia-postgres.render.com/telegram_membership"
)

# Convert to async URL if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session():
    """Get database session"""
    async with async_session_factory() as session:
        yield session


async def add_tier_columns():
    """Add tier tracking columns to users table"""
    async with async_session_factory() as session:
        try:
            print("🔄 Adding tier tracking columns...")
            
            # Add columns one by one with error handling
            columns_to_add = [
                ("current_tier", "INTEGER DEFAULT 3"),
                ("channel_1_tier", "INTEGER"),
                ("highest_amount_paid", "INTEGER DEFAULT 0"),
                ("is_lifetime_member", "BOOLEAN DEFAULT FALSE"),
                ("lifetime_amount", "INTEGER")
            ]
            
            for column_name, column_def in columns_to_add:
                try:
                    await session.execute(text(f"""
                        ALTER TABLE users 
                        ADD COLUMN IF NOT EXISTS {column_name} {column_def}
                    """))
                    print(f"✅ Added column: {column_name}")
                except Exception as e:
                    print(f"⚠️  Column {column_name} might already exist: {str(e)}")
            
            # Update existing users to have Tier 3 as default
            await session.execute(text("""
                UPDATE users 
                SET current_tier = 3 
                WHERE current_tier IS NULL
            """))
            print("✅ Updated existing users to Tier 3")
            
            # Remove old plan_slab column if it exists
            try:
                await session.execute(text("""
                    ALTER TABLE users 
                    DROP COLUMN IF EXISTS plan_slab
                """))
                print("✅ Removed old plan_slab column")
            except Exception as e:
                print(f"⚠️  Column plan_slab removal: {str(e)}")
            
            await session.commit()
            print("✅ Successfully migrated users table")
            
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            await session.rollback()


async def add_membership_columns():
    """Add tier column to memberships table"""
    async with async_session_factory() as session:
        try:
            print("🔄 Adding tier column to memberships...")
            
            await session.execute(text("""
                ALTER TABLE memberships 
                ADD COLUMN IF NOT EXISTS tier INTEGER
            """))
            
            # Remove old plan_slab column if it exists
            try:
                await session.execute(text("""
                    ALTER TABLE memberships 
                    DROP COLUMN IF EXISTS plan_slab
                """))
                print("✅ Removed old plan_slab column from memberships")
            except Exception as e:
                print(f"⚠️  Column plan_slab removal: {str(e)}")
            
            await session.commit()
            print("✅ Successfully migrated memberships table")
            
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            await session.rollback()


async def verify_channels():
    """Verify all 10 channels exist with correct is_public flag"""
    async with async_session_factory() as session:
        try:
            print("🔄 Verifying channels...")
            
            # Check channel count
            result = await session.execute(text("SELECT COUNT(*) FROM channels"))
            count = result.scalar()
            
            print(f"📊 Found {count} channels in database")
            
            if count < 10:
                print("⚠️  WARNING: Less than 10 channels found!")
                print("   Run the INSERT statement to add missing channels:")
                print("""
                INSERT INTO channels (name, telegram_chat_id, is_public) VALUES
                ('Adult Webseries', -1003859012753, true),
                ('Uncut Webseries', -1003768724298, true),
                ('Movies Premium', -1003656685764, true),
                ('Savita Bhabhi Comic', -1003704157213, true),
                ('Naughty Plus', -1003527287574, false),
                ('Only Fans', -1003724075459, false),
                ('Only Fans Premium', -1003014266989, false),
                ('Adult Movies Premium', -1003824870056, false),
                ('Instagram Viral', -1003590287133, false),
                ('Indian Desi Premium', -1003792330155, false);
                """)
            else:
                print("✅ All channels verified")
            
        except Exception as e:
            print(f"❌ Error verifying channels: {str(e)}")


async def main():
    """Run all migrations"""
    print("=" * 60)
    print("🚀 TIER SYSTEM MIGRATION")
    print("=" * 60)
    
    await add_tier_columns()
    print()
    
    await add_membership_columns()
    print()
    
    await verify_channels()
    print()
    
    print("=" * 60)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 60)
    print()
    print("📋 Next steps:")
    print("1. Update your models.py with the new version")
    print("2. Add tier_engine.py to backend/app/services/")
    print("3. Replace admin_add_user.py handler")
    print("4. Update start.py and channel_plans.py handlers")
    print("5. Register all handlers in main.py")
    print("6. Deploy to production")


if __name__ == "__main__":
    asyncio.run(main())