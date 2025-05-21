-- 创建专用数据库（如已存在则跳过）
CREATE DATABASE IF NOT EXISTS vertudata 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

-- 创建专用用户（如已存在则跳过）
-- 请将 'your_strong_password' 替换为实际强密码
CREATE USER IF NOT EXISTS 'vertu_app_user'@'localhost' 
    IDENTIFIED BY 'your_strong_password';

-- 授予该用户对 vertudata 数据库的所有权限
GRANT ALL PRIVILEGES ON vertudata.* TO 'vertu_app_user'@'localhost';
FLUSH PRIVILEGES;

-- 切换到目标数据库
USE vertudata;

-- 创建 WooCommerce 订单主表
CREATE TABLE IF NOT EXISTS `woocommerce_orders` (
  `order_id` BIGINT NOT NULL COMMENT 'WooCommerce原始订单ID',
  `order_number` VARCHAR(255) NOT NULL COMMENT 'WooCommerce订单号',
  `status` VARCHAR(50) NOT NULL COMMENT '订单状态 (如processing, completed)',
  `currency` VARCHAR(10) NOT NULL COMMENT '货币代码 (如USD)',
  `total_amount` DECIMAL(12,2) NOT NULL COMMENT '订单总金额',
  `discount_total` DECIMAL(12,2) NULL DEFAULT 0.00 COMMENT '总折扣金额',
  `shipping_total` DECIMAL(12,2) NULL DEFAULT 0.00 COMMENT '运费总额',
  `customer_id` BIGINT NULL COMMENT 'WooCommerce客户ID (如有)',
  `billing_first_name` VARCHAR(255) NULL,
  `billing_last_name` VARCHAR(255) NULL,
  `billing_email` VARCHAR(255) NULL,
  `billing_phone` VARCHAR(100) NULL,
  `billing_company` VARCHAR(255) NULL,
  `billing_address_1` VARCHAR(255) NULL,
  `billing_address_2` VARCHAR(255) NULL,
  `billing_city` VARCHAR(255) NULL,
  `billing_state` VARCHAR(100) NULL,
  `billing_postcode` VARCHAR(20) NULL,
  `billing_country` VARCHAR(5) NULL COMMENT 'ISO 3166-1 alpha-2 国家代码',
  `shipping_first_name` VARCHAR(255) NULL,
  `shipping_last_name` VARCHAR(255) NULL,
  `shipping_company` VARCHAR(255) NULL,
  `shipping_address_1` VARCHAR(255) NULL,
  `shipping_address_2` VARCHAR(255) NULL,
  `shipping_city` VARCHAR(255) NULL,
  `shipping_state` VARCHAR(100) NULL,
  `shipping_postcode` VARCHAR(20) NULL,
  `shipping_country` VARCHAR(5) NULL,
  `customer_ip_address` VARCHAR(100) NULL,
  `customer_user_agent` TEXT NULL,
  `payment_method_id` VARCHAR(100) NULL,
  `payment_method_title` VARCHAR(255) NULL,
  `transaction_id` VARCHAR(255) NULL,
  `date_created_gmt` DATETIME NULL COMMENT '订单创建时间 (GMT)',
  `date_paid_gmt` DATETIME NULL,
  `date_completed_gmt` DATETIME NULL,
  `date_modified_gmt` DATETIME NULL COMMENT '订单最后修改时间 (GMT)',
  `customer_note` TEXT NULL,
  `meta_data` JSON NULL,
  `raw_api_response` JSON NULL,
  `last_synced_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`order_id`),
  UNIQUE INDEX `order_number_UNIQUE` (`order_number` ASC) VISIBLE,
  INDEX `idx_wc_orders_date_created` (`date_created_gmt` DESC),
  INDEX `idx_wc_orders_status` (`status` ASC),
  INDEX `idx_wc_orders_customer_id` (`customer_id` ASC),
  INDEX `idx_wc_orders_billing_email` (`billing_email` ASC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = '存储从WooCommerce同步的订单核心信息';

-- 创建 WooCommerce 订单商品明细表
CREATE TABLE IF NOT EXISTS `woocommerce_order_items` (
  `item_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '订单商品行ID',
  `order_id` BIGINT NOT NULL COMMENT '关联订单ID',
  `product_id` BIGINT NULL COMMENT '商品ID',
  `product_name` VARCHAR(255) NOT NULL COMMENT '商品名称',
  `quantity` INT NOT NULL DEFAULT 1 COMMENT '数量',
  `total` DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '该商品行总价',
  `sku` VARCHAR(100) NULL COMMENT 'SKU',
  `meta_data` JSON NULL COMMENT '商品行附加信息',
  PRIMARY KEY (`item_id`),
  INDEX `idx_order_id` (`order_id` ASC),
  INDEX `idx_product_id` (`product_id` ASC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'WooCommerce订单的商品明细';

-- 创建 GA4 每日总体概览表
CREATE TABLE IF NOT EXISTS `ga4_daily_overview` (
  `report_date` DATE NOT NULL COMMENT '统计日期',
  `active_users` INT NOT NULL DEFAULT 0 COMMENT '活跃用户数',
  `sessions` INT NOT NULL DEFAULT 0 COMMENT '会话数',
  `engagement_rate` DECIMAL(5,2) NULL COMMENT '互动率',
  `conversions_total` INT NULL COMMENT '转化总数',
  `total_revenue` DECIMAL(12,2) NULL COMMENT '总收入',
  PRIMARY KEY (`report_date`)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'GA4每日总体概览';

-- 1. 各流量渠道
CREATE TABLE IF NOT EXISTS ga4_traffic_channels (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_date DATE NOT NULL,
  channel VARCHAR(100) NOT NULL,
  visitors INT NOT NULL DEFAULT 0,
  avg_engagement_time DECIMAL(10,2) DEFAULT 0,
  UNIQUE KEY uq_channel_date (channel, report_date)
) COMMENT='GA4各流量渠道访客数与平均互动时长';

-- 2. 各页面
CREATE TABLE IF NOT EXISTS ga4_page_metrics (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_date DATE NOT NULL,
  page_path VARCHAR(255) NOT NULL,
  avg_time_on_page DECIMAL(10,2) DEFAULT 0,
  bounce_rate DECIMAL(5,2) DEFAULT 0,
  UNIQUE KEY uq_page_date (page_path, report_date)
) COMMENT='GA4各页面停留时长与跳出率';

-- 3. 会话深度
CREATE TABLE IF NOT EXISTS ga4_session_depth (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_date DATE NOT NULL,
  session_depth INT NOT NULL,
  bounce_rate DECIMAL(5,2) DEFAULT 0,
  add_to_cart INT DEFAULT 0,
  checkout INT DEFAULT 0,
  UNIQUE KEY uq_depth_date (session_depth, report_date)
) COMMENT='GA4会话深度相关指标';

-- 4. 访问深度
CREATE TABLE IF NOT EXISTS ga4_visit_depth (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_date DATE NOT NULL,
  visitors INT DEFAULT 0,
  visits INT DEFAULT 0,
  UNIQUE KEY uq_visitdepth_date (report_date)
) COMMENT='GA4访问深度（访客数/访问量）';

-- 5. PC/移动端
CREATE TABLE IF NOT EXISTS ga4_device_metrics (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_date DATE NOT NULL,
  device_type VARCHAR(20) NOT NULL, -- 'pc' 或 'mobile'
  visitors INT DEFAULT 0,
  bounce_rate DECIMAL(5,2) DEFAULT 0,
  avg_visit_time DECIMAL(10,2) DEFAULT 0,
  add_to_cart INT DEFAULT 0,
  checkout INT DEFAULT 0,
  UNIQUE KEY uq_device_date (device_type, report_date)
) COMMENT='GA4 PC/移动端各项指标';

-- (可选) 查看用户和权限以确认
-- SHOW GRANTS FOR 'vertu_app_user'@'localhost';