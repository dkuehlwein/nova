"""
Checkpointer Utilities.

Utilities for accessing PostgreSQL checkpointer from ServiceManager.
Extracted to avoid circular imports between endpoints and services.
"""

from utils.logging import get_logger

logger = get_logger(__name__)


async def get_checkpointer_from_service_manager():
    """Get the PostgreSQL checkpointer from ServiceManager.

    Returns:
        AsyncPostgresSaver checkpointer instance

    Raises:
        RuntimeError: If PostgreSQL connection pool is not available
    """
    try:
        # Import here to avoid circular dependency
        from start_website import get_service_manager
        from utils.service_manager import create_postgres_checkpointer

        service_manager = get_service_manager()

        # Initialize pg_pool if needed
        if service_manager.pg_pool is None:
            logger.debug("PostgreSQL pool is None, initializing...")
            await service_manager.init_pg_pool()

        if service_manager.pg_pool:
            checkpointer = create_postgres_checkpointer(service_manager.pg_pool)
            return checkpointer
        else:
            # PostgreSQL is mandatory - raise error if not available
            logger.error("PostgreSQL connection pool is required but not available")
            raise RuntimeError("PostgreSQL connection pool is required but not available")

    except Exception as e:
        logger.error("Error creating PostgreSQL checkpointer", extra={"data": {"error": str(e)}})
        raise RuntimeError(f"Failed to create PostgreSQL checkpointer: {str(e)}")
