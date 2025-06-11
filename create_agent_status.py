import asyncio
import sys
import os
sys.path.append('backend')

from database.database import db_manager
from models.models import AgentStatus, AgentStatusEnum
from datetime import datetime

async def create_agent_status():
    async with db_manager.get_session() as session:
        # Check if any agent status record exists
        from sqlalchemy import select
        result = await session.execute(select(AgentStatus))
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Agent status already exists with ID: {existing.id}")
            return
        
        # Create new agent status record
        status = AgentStatus(
            status=AgentStatusEnum.IDLE,
            started_at=datetime.utcnow(),
            total_tasks_processed=0,
            error_count=0
        )
        session.add(status)
        await session.commit()
        await session.refresh(status)
        print(f'✅ Created agent status record with ID: {status.id}')

if __name__ == "__main__":
    asyncio.run(create_agent_status()) 