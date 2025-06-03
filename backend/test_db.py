import asyncio
from database.database import db_manager
from sqlalchemy import text

async def test_db():
    try:
        async with db_manager.get_session() as session:
            result = await session.execute(text("SELECT 1"))
            print("Database connection successful!")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_db()) 