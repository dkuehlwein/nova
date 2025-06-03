-- Initial PostgreSQL setup for Nova Kanban
-- This file is run automatically when the container starts

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create any initial data or configurations here
-- Tables will be created automatically by SQLAlchemy 