CREATE DATABASE IF NOT EXISTS internship_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE internship_db;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student','company','faculty','admin') NOT NULL DEFAULT 'student',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS internships (
  id INT AUTO_INCREMENT PRIMARY KEY,
  company_id INT NOT NULL,
  title VARCHAR(150) NOT NULL,
  description TEXT NOT NULL,
  required_skills VARCHAR(500),
  duration VARCHAR(100),
  stipend DECIMAL(10,2) DEFAULT 0,
  deadline DATE NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (company_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  internship_id INT NOT NULL,
  status ENUM('Under Review','Shortlisted','Selected','Rejected') NOT NULL DEFAULT 'Under Review',
  resume_path VARCHAR(255) NULL,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY one_application_per_student (student_id, internship_id),
  FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE
);


-- Demo faculty account for testing Faculty Monitoring.
-- Login email: faculty@internship.local
-- Password: Faculty@123
-- Password is stored as a Werkzeug-compatible scrypt hash.
INSERT INTO users (name, email, password_hash, role)
VALUES ('Faculty', 'faculty@internship.local', 'scrypt:32768:8:1$b6d21f3f33624a4a$9f487aceb39578aa7572061ef05caeb9414eacb8eda58a8204c015edde6291c63594cf45323586f79ecd6ad83fc9afaf1ad5ad42983c39b278613ea9440fd513', 'faculty')
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  password_hash = VALUES(password_hash),
  role = VALUES(role);
