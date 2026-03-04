-- =============================================================================
-- Optional seed data for development
-- Run AFTER setup.sql
-- =============================================================================

-- Example: create a test user (password = "Test1234!")
-- INSERT INTO users (email, password_hash, email_verified)
-- VALUES (
--     'test@example.com',
--     -- Generate hash: python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('Test1234!'))"
--     '$2b$12$REPLACE_WITH_REAL_HASH',
--     TRUE
-- );

SELECT 'Seed file ready — uncomment and customize as needed.' AS message;
