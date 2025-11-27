CREATE DATABASE IF NOT EXISTS photomanager
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
USE photomanager;

-- 用户
DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(80)  NOT NULL UNIQUE,
  email         VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  avatar_url    VARCHAR(512) NULL,
  is_admin      BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 标签
DROP TABLE IF EXISTS tags;
CREATE TABLE tags (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NULL,
  name       VARCHAR(64) NOT NULL,
  color      VARCHAR(16) NULL,
  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_tags_name_user (name, user_id),
  CONSTRAINT fk_tags_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 文件夹
DROP TABLE IF EXISTS folders;
CREATE TABLE folders (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  parent_id  INT NULL,
  name       VARCHAR(255) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_folders_user (user_id),
  KEY idx_folders_parent (parent_id),
  CONSTRAINT fk_folders_user   FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_folders_parent FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 图片
DROP TABLE IF EXISTS images;
CREATE TABLE images (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  folder_id     INT NULL,
  name          VARCHAR(255) NOT NULL,
  filename      VARCHAR(255) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  mime_type     VARCHAR(64)  NOT NULL,
  size          INT NOT NULL,
  width         INT NULL,
  height        INT NULL,
  taken_at      DATETIME NULL,
  camera        VARCHAR(128) NULL,
  lens          VARCHAR(128) NULL,
  iso           VARCHAR(32)  NULL,
  exposure      VARCHAR(32)  NULL,
  aperture      VARCHAR(32)  NULL,
  focal         VARCHAR(32)  NULL,
  latitude      DOUBLE NULL,
  longitude     DOUBLE NULL,
  thumb_path    VARCHAR(255) NULL,
  visibility    VARCHAR(16)  NOT NULL DEFAULT 'private',
  folder        VARCHAR(128) NULL DEFAULT '默认图库',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at    DATETIME NULL,
  CONSTRAINT fk_images_user   FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_images_folder FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 图片版本
DROP TABLE IF EXISTS image_versions;
CREATE TABLE image_versions (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  image_id   INT NOT NULL,
  name       VARCHAR(255) NOT NULL,
  note       VARCHAR(255) NULL,
  filename   VARCHAR(255) NOT NULL,
  thumb_path VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_image_versions_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 图片-标签关联
DROP TABLE IF EXISTS image_tags;
CREATE TABLE image_tags (
  image_id INT NOT NULL,
  tag_id   INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (image_id, tag_id),
  CONSTRAINT fk_image_tags_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
  CONSTRAINT fk_image_tags_tag   FOREIGN KEY (tag_id)   REFERENCES tags(id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 相册
DROP TABLE IF EXISTS albums;
CREATE TABLE albums (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  title      VARCHAR(255) NOT NULL,
  visibility VARCHAR(16)  NOT NULL DEFAULT 'private',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_albums_user (user_id),
  CONSTRAINT fk_albums_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 相册-图片关联
DROP TABLE IF EXISTS album_images;
CREATE TABLE album_images (
  album_id   INT NOT NULL,
  image_id   INT NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (album_id, image_id),
  KEY idx_album_images_image (image_id),
  CONSTRAINT fk_album_images_album FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
  CONSTRAINT fk_album_images_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- AI 分析
DROP TABLE IF EXISTS image_ai_analysis;
CREATE TABLE image_ai_analysis (
  image_id   INT NOT NULL,
  model      VARCHAR(64) NOT NULL,
  labels     JSON NULL,
  caption    TEXT NULL,
  status     VARCHAR(16) NOT NULL DEFAULT 'pending',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (image_id),
  CONSTRAINT fk_ai_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 任务队列
DROP TABLE IF EXISTS job_queue;
CREATE TABLE job_queue (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NOT NULL,
  image_id    INT NULL,
  job_type    VARCHAR(32) NOT NULL,
  status      VARCHAR(16) NOT NULL DEFAULT 'queued',
  payload     JSON NULL,
  attempts    TINYINT UNSIGNED NOT NULL DEFAULT 0,
  err_msg     VARCHAR(512) NULL,
  queued_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at  DATETIME NULL,
  finished_at DATETIME NULL,
  KEY idx_job_queue_user   (user_id),
  KEY idx_job_queue_image  (image_id),
  KEY idx_job_queue_status (status),
  CONSTRAINT fk_job_queue_user  FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_job_queue_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 默认管理员
INSERT INTO users (username, email, password_hash, is_admin)
SELECT 'hyk', '3230103921@zju.edu.cn', 'bs2025123', TRUE
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username='hyk');
