-- Runs once when the volume is first created.
CREATE DATABASE gridline_test OWNER gridline;
\connect gridline
CREATE EXTENSION IF NOT EXISTS vector;
\connect gridline_test
CREATE EXTENSION IF NOT EXISTS vector;
