-- Migration script to update student_pdfs table for binary storage
-- Run this script to add new columns for database PDF storage

-- Add new columns to student_pdfs table
ALTER TABLE student_pdfs
ADD COLUMN
IF
  NOT EXISTS pdf_data BYTEA
  , ADD COLUMN
  IF
    NOT EXISTS pdf_size INTEGER
    , ADD COLUMN
    IF
      NOT EXISTS content_hash VARCHAR(32)
      , ADD COLUMN
      IF
        NOT EXISTS mime_type VARCHAR(50) DEFAULT 'application/pdf';

        -- Update existing records to set default mime_type
        UPDATE
          student_pdfs
        SET mime_type = 'application/pdf'
        WHERE
          mime_type IS NULL;

        -- Create index on content_hash for deduplication queries
        CREATE INDEX
        IF
          NOT EXISTS idx_student_pdfs_content_hash
          ON student_pdfs(content_hash);

          -- Create index on pdf_size for analytics
          CREATE INDEX
          IF
            NOT EXISTS idx_student_pdfs_size
            ON student_pdfs(pdf_size);

            -- Show current table structure
            \ d student_pdfs;

            -- Show summary of migration
            SELECT
              COUNT(*) as total_records
              , COUNT(pdf_data) as records_with_binary_data
              , COUNT(pdf_path) as records_with_file_paths
              , AVG(pdf_size) as avg_pdf_size_bytes
              , SUM(pdf_size) as total_storage_bytes
            FROM
              student_pdfs;

            COMMIT;