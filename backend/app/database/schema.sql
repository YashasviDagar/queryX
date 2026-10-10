-- queryX benchmark schema.
-- This schema mirrors backend/app/compiler/config/statistics.yaml. It is used
-- ONLY for optional real-execution validation; the custom optimizer does not
-- depend on PostgreSQL.

DROP TABLE IF EXISTS enrollments CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

CREATE TABLE departments (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    building TEXT,
    head     TEXT
);

CREATE TABLE students (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    cgpa    DOUBLE PRECISION,
    dept_id INTEGER NOT NULL REFERENCES departments (id),
    age     INTEGER,
    city    TEXT
);

CREATE TABLE courses (
    id      INTEGER PRIMARY KEY,
    title   TEXT NOT NULL,
    credits INTEGER NOT NULL,
    dept_id INTEGER NOT NULL REFERENCES departments (id)
);

CREATE TABLE enrollments (
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students (id),
    course_id  INTEGER NOT NULL REFERENCES courses (id),
    grade      DOUBLE PRECISION
);

CREATE INDEX students_dept_id_idx ON students (dept_id);
CREATE INDEX students_cgpa_idx ON students (cgpa);
CREATE INDEX departments_name_idx ON departments (name);
CREATE INDEX courses_dept_id_idx ON courses (dept_id);
CREATE INDEX enrollments_student_id_idx ON enrollments (student_id);
CREATE INDEX enrollments_course_id_idx ON enrollments (course_id);
