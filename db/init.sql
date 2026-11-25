-- Local only: creates one database and one login per service on the compose
-- SQL Server. Run by the one-off `db-init` compose service on every
-- `docker compose up`, so every statement is guarded and running it again
-- changes nothing (except re-applying the passwords from the environment).
--
-- On Azure the same shape is created once during the initial setup
-- (infra/README.md): contained database users instead of server logins,
-- since Azure SQL serverless databases are separate units.
--
-- Passwords arrive as sqlcmd variables ($(REQUESTS_DB_PASSWORD),
-- $(FEEDBACK_DB_PASSWORD)) from docker-compose.yml, never written here.
--
-- Each login gets DDL (its migrations create and alter tables) plus read
-- and write, in its own database only. Neither can open the other's
-- database: that is the "database per service" rule enforced by SQL Server,
-- not only by convention.

IF DB_ID(N'avdesk_requests') IS NULL CREATE DATABASE avdesk_requests;
GO
IF DB_ID(N'avdesk_feedback') IS NULL CREATE DATABASE avdesk_feedback;
GO

IF SUSER_ID(N'avdesk_requests') IS NULL
    CREATE LOGIN avdesk_requests WITH PASSWORD = N'$(REQUESTS_DB_PASSWORD)', DEFAULT_DATABASE = avdesk_requests;
ELSE
    ALTER LOGIN avdesk_requests WITH PASSWORD = N'$(REQUESTS_DB_PASSWORD)';
GO
IF SUSER_ID(N'avdesk_feedback') IS NULL
    CREATE LOGIN avdesk_feedback WITH PASSWORD = N'$(FEEDBACK_DB_PASSWORD)', DEFAULT_DATABASE = avdesk_feedback;
ELSE
    ALTER LOGIN avdesk_feedback WITH PASSWORD = N'$(FEEDBACK_DB_PASSWORD)';
GO

USE avdesk_requests;
IF USER_ID(N'avdesk_requests') IS NULL CREATE USER avdesk_requests FOR LOGIN avdesk_requests;
ALTER ROLE db_ddladmin ADD MEMBER avdesk_requests;
ALTER ROLE db_datareader ADD MEMBER avdesk_requests;
ALTER ROLE db_datawriter ADD MEMBER avdesk_requests;
GO

USE avdesk_feedback;
IF USER_ID(N'avdesk_feedback') IS NULL CREATE USER avdesk_feedback FOR LOGIN avdesk_feedback;
ALTER ROLE db_ddladmin ADD MEMBER avdesk_feedback;
ALTER ROLE db_datareader ADD MEMBER avdesk_feedback;
ALTER ROLE db_datawriter ADD MEMBER avdesk_feedback;
GO
