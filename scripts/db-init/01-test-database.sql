-- Runs once when the Postgres data volume is first created.
-- Creates the test database used by `uv run pytest` and enables pgvector in both databases.
CREATE DATABASE gridline_test OWNER gridline;
\connect gridline
CREATE EXTENSION IF NOT EXISTS vector;
\connect gridline_test
CREATE EXTENSION IF NOT EXISTS vector;
