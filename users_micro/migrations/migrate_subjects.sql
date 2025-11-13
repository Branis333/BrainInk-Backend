-- Migration script to create subjects tables and relationships
-- Run this script to add the subjects functionality to your database

-- Create subjects table
CREATE TABLE subjects (
  id SERIAL PRIMARY KEY
  , name VARCHAR NOT NULL
  , description TEXT
  , school_id INTEGER NOT NULL REFERENCES schools(id)
  ON DELETE CASCADE
  , created_by INTEGER NOT NULL REFERENCES users(id)
  , created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  , is_active BOOLEAN DEFAULT TRUE
  , CONSTRAINT uq_school_subject_name UNIQUE (school_id, name)
);

-- Create subject_teachers association table
CREATE TABLE subject_teachers (
  subject_id INTEGER NOT NULL REFERENCES subjects(id)
  ON DELETE CASCADE
  , teacher_id INTEGER NOT NULL REFERENCES teachers(id)
  ON DELETE CASCADE
  , PRIMARY KEY (subject_id, teacher_id)
);

-- Create subject_students association table
CREATE TABLE subject_students (
  subject_id INTEGER NOT NULL REFERENCES subjects(id)
  ON DELETE CASCADE
  , student_id INTEGER NOT NULL REFERENCES students(id)
  ON DELETE CASCADE
  , PRIMARY KEY (subject_id, student_id)
);

-- Create indexes for better performance
CREATE INDEX idx_subjects_school_id
ON subjects(school_id);
CREATE INDEX idx_subjects_created_by
ON subjects(created_by);
CREATE INDEX idx_subjects_active
ON subjects(is_active);

CREATE INDEX idx_subject_teachers_subject_id
ON subject_teachers(subject_id);
CREATE INDEX idx_subject_teachers_teacher_id
ON subject_teachers(teacher_id);

CREATE INDEX idx_subject_students_subject_id
ON subject_students(subject_id);
CREATE INDEX idx_subject_students_student_id
ON subject_students(student_id);

COMMIT;