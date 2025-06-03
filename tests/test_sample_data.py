"""
Test sample data creation for Nova backend.

Run this script to populate the database with sample data for development and testing.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database.database import db_manager
from models.models import (
    Task, TaskComment, Person, Project, Chat, ChatMessage,
    TaskStatus
)


async def create_sample_data():
    """Create sample data for testing."""
    print("Creating sample data...")
    
    async with db_manager.get_session() as session:
        # Create sample persons
        persons = [
            Person(
                name="John Smith",
                email="john.smith@example.com",
                role="Senior Developer",
                description="Lead developer with 10+ years experience",
                current_focus="Working on the new authentication system"
            ),
            Person(
                name="Jane Doe",
                email="jane.doe@example.com", 
                role="Project Manager",
                description="Experienced PM specializing in agile methodologies",
                current_focus="Managing the Q1 product roadmap"
            ),
            Person(
                name="Bob Wilson",
                email="bob.wilson@example.com",
                role="Sales Director",
                description="Sales lead for enterprise accounts",
                current_focus="Closing the major enterprise deal with TechCorp"
            ),
            Person(
                name="Alice Brown",
                email="alice.brown@example.com",
                role="UX Designer",
                description="Senior UX designer focused on user research",
                current_focus="Redesigning the main dashboard interface"
            )
        ]
        
        for person in persons:
            session.add(person)
        
        await session.flush()
        
        # Create sample projects
        projects = [
            Project(
                name="Nova AI Assistant",
                client="Internal",
                booking_code="NOVA-2024",
                summary="Development of the Nova AI assistant platform"
            ),
            Project(
                name="Enterprise CRM",
                client="TechCorp",
                booking_code="TECH-001",
                summary="Custom CRM implementation for enterprise client"
            ),
            Project(
                name="Mobile App Redesign",
                client="StartupXYZ",
                booking_code="SUZ-2024",
                summary="Complete mobile application redesign and development"
            )
        ]
        
        for project in projects:
            session.add(project)
        
        await session.flush()
        
        # Create sample tasks
        tasks = [
            Task(
                title="Review quarterly reports",
                description="Analyze Q4 performance metrics and prepare summary for stakeholders",
                status=TaskStatus.NEW,
                due_date=datetime.now() + timedelta(days=3),
                tags=["reports", "analysis", "quarterly"]
            ),
            Task(
                title="Implement user dashboard",
                description="Build the main dashboard with charts and metrics for the Nova platform",
                status=TaskStatus.IN_PROGRESS,
                due_date=datetime.now() + timedelta(days=7),
                tags=["frontend", "dashboard", "charts"]
            ),
            Task(
                title="Email approval for John Smith",
                description="Review and approve the email draft response to John's inquiry about project timeline",
                status=TaskStatus.NEEDS_REVIEW,
                due_date=datetime.now() + timedelta(hours=2),
                tags=["email", "approval", "communication"],
                summary="Nova has prepared a response addressing the project delay and proposing a revised timeline"
            ),
            Task(
                title="Choose deployment strategy",
                description="Select between AWS and Azure for the new microservice architecture",
                status=TaskStatus.NEEDS_REVIEW,
                due_date=datetime.now() + timedelta(days=2),
                tags=["deployment", "infrastructure", "cloud"],
                summary="Analysis completed comparing AWS vs Azure. Decision needed on primary cloud provider"
            ),
            Task(
                title="Setup CI/CD pipeline",
                description="Configure GitHub Actions for automated testing and deployment",
                status=TaskStatus.DONE,
                due_date=datetime.now() - timedelta(days=2),
                completed_at=datetime.now() - timedelta(days=1),
                tags=["devops", "automation", "ci-cd"]
            ),
            Task(
                title="Database optimization",
                description="Optimize database queries for better performance on the reporting dashboard",
                status=TaskStatus.IN_PROGRESS,
                due_date=datetime.now() + timedelta(days=5),
                tags=["database", "performance", "optimization"]
            ),
            Task(
                title="User authentication review",
                description="Security review of the new JWT-based authentication system",
                status=TaskStatus.WAITING,
                due_date=datetime.now() + timedelta(days=1),
                tags=["security", "authentication", "review"]
            )
        ]
        
        for i, task in enumerate(tasks):
            session.add(task)
            # Assign persons and projects to some tasks
            if i < len(persons):
                task.persons.append(persons[i % len(persons)])
            if i < len(projects):
                task.projects.append(projects[i % len(projects)])
        
        await session.flush()
        
        # Add comments to some tasks
        comments = [
            TaskComment(
                task_id=tasks[0].id,
                content="Started the analysis, focusing on revenue metrics first",
                author="nova"
            ),
            TaskComment(
                task_id=tasks[1].id,
                content="Dashboard wireframes are complete, moving to implementation",
                author="alice.brown@example.com"
            ),
            TaskComment(
                task_id=tasks[2].id,
                content="The email draft looks good but needs a more specific timeline. Can you add dates?",
                author="user"
            ),
            TaskComment(
                task_id=tasks[3].id,
                content="AWS seems like the better option based on our current infrastructure",
                author="john.smith@example.com"
            )
        ]
        
        for comment in comments:
            session.add(comment)
        
        # Create sample chat
        chat = Chat(
            title="Email draft approval for TechCorp",
            project_id=projects[1].id  # Enterprise CRM project
        )
        session.add(chat)
        await session.flush()
        
        # Add chat messages
        chat_messages = [
            ChatMessage(
                chat_id=chat.id,
                sender="user",
                content="I need to respond to Bob from TechCorp about our project timeline delay"
            ),
            ChatMessage(
                chat_id=chat.id,
                sender="assistant",
                content="I can help you draft a professional response. Based on our project data, I see there's been a 2-week delay due to resource constraints. Would you like me to draft an email that acknowledges this delay and proposes a revised timeline?"
            ),
            ChatMessage(
                chat_id=chat.id,
                sender="user",
                content="Yes, please make it professional but honest about the situation"
            ),
            ChatMessage(
                chat_id=chat.id,
                sender="assistant",
                content="Here's a draft email:\n\nHi Bob,\n\nThank you for your patience regarding the project timeline. I wanted to provide you with an honest update on our progress.\n\nDue to some resource allocation challenges, we're looking at a revised timeline that extends our original delivery date by approximately 2 weeks. I understand this may impact your planning, and I want to be transparent about this as early as possible.\n\nHere's what we're doing to minimize the delay:\n- Reallocating senior developers to critical path items\n- Implementing daily stand-ups to track progress\n- Identifying opportunities to parallelize tasks\n\nWould you like me to send this, or would you prefer to make changes first?",
                needs_decision=True,
                decision_type="email_approval",
                decision_metadata={"recipient": "bob@techcorp.com", "subject": "Project Timeline Update"}
            )
        ]
        
        for message in chat_messages:
            session.add(message)
        
        await session.commit()
        print("Sample data created successfully!")
        
        # Print summary
        print(f"Created:")
        print(f"  - {len(persons)} persons")
        print(f"  - {len(projects)} projects") 
        print(f"  - {len(tasks)} tasks")
        print(f"  - {len(comments)} task comments")
        print(f"  - 1 chat with {len(chat_messages)} messages")


async def main():
    """Main entry point."""
    await db_manager.create_tables()
    await create_sample_data()
    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main()) 