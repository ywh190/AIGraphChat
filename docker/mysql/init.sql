-- 创建数据库
CREATE DATABASE IF NOT EXISTS medicine_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE medicine_db;

-- 设置字符集
SET NAMES utf8mb4;

-- 创建测试表
CREATE TABLE IF NOT EXISTS deployment_test (
    id INT AUTO_INCREMENT PRIMARY KEY,
    test_message VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入测试数据
INSERT INTO deployment_test (test_message) VALUES ('MySQL 部署成功！');

-- 创建测试用户
CREATE USER IF NOT EXISTS 'test_user'@'%' IDENTIFIED BY 'test_password';
GRANT SELECT ON medicine_db.* TO 'test_user'@'%';
FLUSH PRIVILEGES;

-- 这里可以添加其他初始数据或配置
-- 实际的数据导入会在应用启动时通过 data_import.py 完成