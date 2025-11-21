CREATE DATABASE IF NOT EXISTS photomanager
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE photomanager;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS image_ai_analysis;
DROP TABLE IF EXISTS image_tags;
DROP TABLE IF EXISTS job_queue;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS folders;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(32) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  is_admin TINYINT(1) NOT NULL DEFAULT 0,
  avatar_url VARCHAR(512) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE folders (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(255) NOT NULL,
  parent_id BIGINT UNSIGNED DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_folders_owner (owner_id),
  KEY idx_folders_parent (parent_id),
  CONSTRAINT fk_folders_owner FOREIGN KEY (owner_id)
    REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_folders_parent FOREIGN KEY (parent_id)
    REFERENCES folders(id) ON DELETE CASCADE,
  UNIQUE KEY uk_folders_owner_parent_name (owner_id, parent_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE images (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_id BIGINT UNSIGNED NOT NULL,
  parent_id BIGINT UNSIGNED DEFAULT NULL,
  folder_id BIGINT UNSIGNED DEFAULT NULL,
  filename VARCHAR(255) NOT NULL,
  original_name VARCHAR(255) DEFAULT NULL,
  storage_path VARCHAR(512) NOT NULL,
  thumb_path VARCHAR(512) DEFAULT NULL,
  mime_type VARCHAR(128) DEFAULT NULL,
  size_bytes BIGINT UNSIGNED DEFAULT NULL,
  width INT UNSIGNED DEFAULT NULL,
  height INT UNSIGNED DEFAULT NULL,
  sha256 CHAR(64) NOT NULL,
  exif_json JSON DEFAULT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_images_owner (owner_id),
  KEY idx_images_folder (folder_id),
  KEY idx_images_parent (parent_id),
  KEY idx_images_is_deleted (is_deleted),
  UNIQUE KEY uk_images_owner_sha256 (owner_id, sha256),
  CONSTRAINT fk_images_owner FOREIGN KEY (owner_id)
    REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_images_folder FOREIGN KEY (folder_id)
    REFERENCES folders(id) ON DELETE SET NULL,
  CONSTRAINT fk_images_parent FOREIGN KEY (parent_id)
    REFERENCES images(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tags (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(64) NOT NULL,
  type ENUM('manual','ai') NOT NULL DEFAULT 'manual',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tags_owner (owner_id),
  UNIQUE KEY uk_tags_owner_name (owner_id, name),
  CONSTRAINT fk_tags_owner FOREIGN KEY (owner_id)
    REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE image_tags (
  image_id BIGINT UNSIGNED NOT NULL,
  tag_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (image_id, tag_id),
  KEY idx_image_tags_tag (tag_id),
  CONSTRAINT fk_image_tags_image FOREIGN KEY (image_id)
    REFERENCES images(id) ON DELETE CASCADE,
  CONSTRAINT fk_image_tags_tag FOREIGN KEY (tag_id)
    REFERENCES tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE image_ai_analysis (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  image_id BIGINT UNSIGNED NOT NULL,
  task_type VARCHAR(64) NOT NULL,
  prompt TEXT,
  result_json JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_image_ai_image (image_id),
  CONSTRAINT fk_image_ai_image FOREIGN KEY (image_id)
    REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE job_queue (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_type VARCHAR(64) NOT NULL,
  image_id BIGINT UNSIGNED DEFAULT NULL,
  status ENUM('pending','processing','done','failed') NOT NULL DEFAULT 'pending',
  priority INT NOT NULL DEFAULT 0,
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT,
  payload JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_job_queue_status (status),
  KEY idx_job_queue_image (image_id),
  CONSTRAINT fk_job_queue_image FOREIGN KEY (image_id)
    REFERENCES images(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;