-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create analytics schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant permissions to the analytics user
GRANT ALL PRIVILEGES ON SCHEMA analytics TO analytics_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO analytics_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA analytics TO analytics_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON TABLES TO analytics_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON SEQUENCES TO analytics_user;
