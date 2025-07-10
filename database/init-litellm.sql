-- Initialize LiteLLM database and user
-- This script creates a separate database and user for LiteLLM
-- to prevent schema conflicts with Nova's main database

-- Create LiteLLM user if it doesn't exist
CREATE USER litellm WITH PASSWORD 'litellm_dev_password';

-- Create LiteLLM database
CREATE DATABASE litellm OWNER litellm;

-- Grant privileges to LiteLLM user
GRANT ALL PRIVILEGES ON DATABASE litellm TO litellm;