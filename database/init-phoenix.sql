-- Initialize Phoenix database for LLM observability
-- Phoenix uses PostgreSQL for storing traces and observations

-- Create Phoenix database owned by the main nova user
-- (Phoenix connects using the same credentials as Nova)
CREATE DATABASE phoenix OWNER nova;

-- Grant privileges to nova user
GRANT ALL PRIVILEGES ON DATABASE phoenix TO nova;
