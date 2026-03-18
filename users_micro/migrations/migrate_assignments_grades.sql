-- Migration script for Assignments and Grades system
-- This script creates the assignments and grades tables with proper relationships and constraints

-- Create assignments table
CREATE TABLE
IF
  NOT EXISTS assignments (
    id SERIAL PRIMARY KEY
    , title VARCHAR(200) NOT NULL
    , description TEXT
    , subtopic VARCHAR(100)
    , subject_id INTEGER NOT NULL REFERENCES subjects(id)
    ON DELETE CASCADE
    , teacher_id INTEGER NOT NULL REFERENCES teachers(id)
    ON DELETE CASCADE
    , max_points INTEGER NOT NULL DEFAULT 100 CHECK (max_points > 0)
    , due_date TIMESTAMP
    , created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , is_active BOOLEAN DEFAULT TRUE
  );

  -- Create grades table
  CREATE TABLE
  IF
    NOT EXISTS grades (
      id SERIAL PRIMARY KEY
      , assignment_id INTEGER NOT NULL REFERENCES assignments(id)
      ON DELETE CASCADE
      , student_id INTEGER NOT NULL REFERENCES students(id)
      ON DELETE CASCADE
      , teacher_id INTEGER NOT NULL REFERENCES teachers(id)
      ON DELETE CASCADE
      , points_earned INTEGER NOT NULL CHECK (points_earned >= 0)
      , feedback TEXT
      , graded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      , is_active BOOLEAN DEFAULT TRUE
      , -- Ensure one grade per student per assignment
        CONSTRAINT uq_assignment_student UNIQUE (assignment_id, student_id)
    );

    -- Create indexes for better performance
    CREATE INDEX
    IF
      NOT EXISTS idx_assignments_subject_id
      ON assignments(subject_id);
      CREATE INDEX
      IF
        NOT EXISTS idx_assignments_teacher_id
        ON assignments(teacher_id);
        CREATE INDEX
        IF
          NOT EXISTS idx_assignments_due_date
          ON assignments(due_date);
          CREATE INDEX
          IF
            NOT EXISTS idx_assignments_is_active
            ON assignments(is_active);

            CREATE INDEX
            IF
              NOT EXISTS idx_grades_assignment_id
              ON grades(assignment_id);
              CREATE INDEX
              IF
                NOT EXISTS idx_grades_student_id
                ON grades(student_id);
                CREATE INDEX
                IF
                  NOT EXISTS idx_grades_teacher_id
                  ON grades(teacher_id);
                  CREATE INDEX
                  IF
                    NOT EXISTS idx_grades_is_active
                    ON grades(is_active);
                    CREATE INDEX
                    IF
                      NOT EXISTS idx_grades_graded_date
                      ON grades(graded_date);

                      -- Add constraint to ensure grades don't exceed assignment max_points
                      -- Note: This constraint is enforced at the application level due to PostgreSQL limitations with cross-table constraints

                      -- Add some initial data validation
                      -- Ensure existing data integrity (if any)
                    DO
                      $ $
                      BEGIN
                        -- Add any data validation or cleanup here if needed
                        RAISE NOTICE 'Assignments and Grades tables created successfully';
                      END $ $;

                      -- Comments for documentation
                      COMMENT ON TABLE assignments IS 'Stores assignments created by teachers for subjects';
                      COMMENT ON TABLE grades IS 'Stores grades given by teachers to students for specific assignments';

                      COMMENT ON COLUMN assignments.title IS 'Title of the assignment';
                      COMMENT ON COLUMN assignments.description IS 'Detailed description of the assignment';
                      COMMENT ON COLUMN assignments.subtopic IS 'Optional subtopic or category for the assignment';
                      COMMENT ON COLUMN assignments.max_points IS 'Maximum points possible for this assignment';
                      COMMENT ON COLUMN assignments.due_date IS 'Due date for the assignment (optional)';

                      COMMENT ON COLUMN grades.points_earned IS 'Points earned by the student for this assignment';
                      COMMENT ON COLUMN grades.feedback IS 'Teacher feedback for the grade';
                      COMMENT ON COLUMN grades.graded_date IS 'Date and time when the grade was given or last updated';

                      COMMENT ON CONSTRAINT uq_assignment_student
                      ON grades IS 'Ensures each student can only have one grade per assignment';