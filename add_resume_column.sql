USE internship_db;

-- Add resume_path only if it does not already exist. Safe to run more than once.
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'applications'
      AND COLUMN_NAME = 'resume_path'
);

SET @sql = IF(
    @column_exists = 0,
    'ALTER TABLE applications ADD COLUMN resume_path VARCHAR(255) NULL',
    'SELECT "resume_path column already exists" AS message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
