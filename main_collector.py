import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from connectors.woo_data import get_woo_summary
from connectors.ga4_data import get_ga4_summary
from connectors.gsc_data import get_gsc_summary
from fastgpt_updater import update_fastgpt_kb_with_content
import mysql.connector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('main_collector.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def insert_ga4_traffic_channels(channel_data_list, report_date):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()
    sql = """
        INSERT INTO ga4_traffic_channels (report_date, channel, visitors, avg_engagement_time)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            visitors=VALUES(visitors),
            avg_engagement_time=VALUES(avg_engagement_time)
    """
    for row in channel_data_list:
        cursor.execute(sql, (
            report_date,
            row['channel'],
            row['visitors'],
            row['avg_engagement_time']
        ))
    conn.commit()
    cursor.close()
    conn.close()

def insert_ga4_page_metrics(page_data_list, report_date):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()
    sql = """
        INSERT INTO ga4_page_metrics (report_date, page_path, avg_time_on_page, bounce_rate)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_time_on_page=VALUES(avg_time_on_page),
            bounce_rate=VALUES(bounce_rate)
    """
    for row in page_data_list:
        cursor.execute(sql, (
            report_date,
            row['page_path'],
            row['avg_time_on_page'],
            row['bounce_rate']
        ))
    conn.commit()
    cursor.close()
    conn.close()

def insert_ga4_session_depth(session_data_list, report_date):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()
    sql = """
        INSERT INTO ga4_session_depth (report_date, session_depth, bounce_rate, add_to_cart, checkout)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            bounce_rate=VALUES(bounce_rate),
            add_to_cart=VALUES(add_to_cart),
            checkout=VALUES(checkout)
    """
    for row in session_data_list:
        cursor.execute(sql, (
            report_date,
            row['session_depth'],
            row['bounce_rate'],
            row['add_to_cart'],
            row['checkout']
        ))
    conn.commit()
    cursor.close()
    conn.close()

def insert_ga4_visit_depth(visit_data, report_date):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()
    sql = """
        INSERT INTO ga4_visit_depth (report_date, visitors, visits)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            visitors=VALUES(visitors),
            visits=VALUES(visits)
    """
    cursor.execute(sql, (
        report_date,
        visit_data['visitors'],
        visit_data['visits']
    ))
    conn.commit()
    cursor.close()
    conn.close()

def insert_ga4_device_metrics(device_data_list, report_date):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()
    sql = """
        INSERT INTO ga4_device_metrics (report_date, device_type, visitors, bounce_rate, avg_visit_time, add_to_cart, checkout)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            visitors=VALUES(visitors),
            bounce_rate=VALUES(bounce_rate),
            avg_visit_time=VALUES(avg_visit_time),
            add_to_cart=VALUES(add_to_cart),
            checkout=VALUES(checkout)
    """
    for row in device_data_list:
        cursor.execute(sql, (
            report_date,
            row['device_type'],
            row['visitors'],
            row['bounce_rate'],
            row['avg_visit_time'],
            row['add_to_cart'],
            row['checkout']
        ))
    conn.commit()
    cursor.close()
    conn.close()

def clean_ga4_channels(raw_ga4_data):
    """
    清洗GA4流量渠道数据，返回list[dict]，每个dict包含channel, visitors, avg_engagement_time
    """
    result = []
    # 假设原始数据结构类似于：
    # dimension: channel, metrics: visitors, avg_engagement_time
    for row in raw_ga4_data.get("rows", []):
        # 你需要根据实际API返回的dimension/metric顺序调整索引
        channel = row["dimensionValues"][0]["value"]
        visitors = int(row["metricValues"][0]["value"])
        avg_engagement_time = float(row["metricValues"][1]["value"])
        result.append({
            "channel": channel,
            "visitors": visitors,
            "avg_engagement_time": avg_engagement_time
        })
    return result

def clean_ga4_pages(raw_ga4_data):
    """
    清洗GA4页面数据，返回list[dict]，每个dict包含page_path, avg_time_on_page, bounce_rate
    """
    result = []
    for row in raw_ga4_data.get("rows", []):
        page_path = row["dimensionValues"][0]["value"]
        avg_time_on_page = float(row["metricValues"][3]["value"])
        bounce_rate = float(row["metricValues"][2]["value"])
        result.append({
            "page_path": page_path,
            "avg_time_on_page": avg_time_on_page,
            "bounce_rate": bounce_rate
        })
    return result

def clean_ga4_sessions(raw_ga4_data):
    """
    清洗GA4会话深度数据，返回list[dict]，每个dict包含session_depth, bounce_rate, add_to_cart, checkout
    """
    result = []
    # 假设dimension: session_depth, metrics: bounce_rate, add_to_cart, checkout
    for row in raw_ga4_data.get("rows", []):
        session_depth = int(row["dimensionValues"][0]["value"])
        bounce_rate = float(row["metricValues"][0]["value"])
        add_to_cart = int(row["metricValues"][1]["value"])
        checkout = int(row["metricValues"][2]["value"])
        result.append({
            "session_depth": session_depth,
            "bounce_rate": bounce_rate,
            "add_to_cart": add_to_cart,
            "checkout": checkout
        })
    return result

def clean_ga4_visit_depth(raw_ga4_data):
    """
    清洗GA4访问深度数据，返回dict，包含visitors, visits
    """
    # 假设metrics: visitors, visits
    visitors = int(raw_ga4_data["totals"][0]["metricValues"][0]["value"])
    visits = int(raw_ga4_data["totals"][0]["metricValues"][1]["value"])
    return {"visitors": visitors, "visits": visits}

def clean_ga4_devices(raw_ga4_data):
    """
    清洗GA4设备端数据，返回list[dict]，每个dict包含device_type, visitors, bounce_rate, avg_visit_time, add_to_cart, checkout
    """
    result = []
    # 假设dimension: device_type, metrics: visitors, bounce_rate, avg_visit_time, add_to_cart, checkout
    for row in raw_ga4_data.get("rows", []):
        device_type = row["dimensionValues"][0]["value"]
        visitors = int(row["metricValues"][0]["value"])
        bounce_rate = float(row["metricValues"][1]["value"])
        avg_visit_time = float(row["metricValues"][2]["value"])
        add_to_cart = int(row["metricValues"][3]["value"])
        checkout = int(row["metricValues"][4]["value"])
        result.append({
            "device_type": device_type,
            "visitors": visitors,
            "bounce_rate": bounce_rate,
            "avg_visit_time": avg_visit_time,
            "add_to_cart": add_to_cart,
            "checkout": checkout
        })
    return result

def main():
    try:
        # 加载环境变量
        load_dotenv()
        logger.info("环境变量加载完成")

        # 设置日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        logger.info(f"数据收集时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

        # 获取各平台数据
        woo_summary = get_woo_summary(start_date, end_date)
        ga4_summary = get_ga4_summary(start_date, end_date)
        gsc_summary = get_gsc_summary(start_date, end_date)

        # 生成报告
        report_content = f"""# Vertu.com 运营数据报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
数据周期: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}

{woo_summary}

{ga4_summary}

{gsc_summary}
"""

        # 保存报告
        os.makedirs('data_exports', exist_ok=True)
        report_filename = f'report_{datetime.now().strftime("%Y%m%d%H%M%S")}.txt'
        report_file_path = os.path.join('data_exports', report_filename)
        with open(report_file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        logger.info(f"报告已保存到: {report_file_path}")

        # 更新FastGPT知识库
        fastgpt_api_key = os.getenv("FASTGPT_API_KEY")
        fastgpt_kb_id = os.getenv("FASTGPT_KB_ID")
        fastgpt_base_url = os.getenv("FASTGPT_BASE_URL")

        if all([fastgpt_api_key, fastgpt_kb_id, fastgpt_base_url, report_content]):
            logger.info(f"准备更新FastGPT知识库 {fastgpt_kb_id}...")
            success = update_fastgpt_kb_with_content(
                api_key=fastgpt_api_key,
                base_url=fastgpt_base_url,
                kb_id=fastgpt_kb_id,
                file_name=report_filename,
                content=report_content,
                mode="index"
            )
            if success:
                logger.info("FastGPT知识库更新成功！")
            else:
                logger.error("FastGPT知识库更新失败。请检查日志。")
        else:
            logger.warning("FastGPT配置不完整或报告内容为空，跳过知识库更新。请检查.env文件中的FASTGPT_API_KEY, FASTGPT_KB_ID, FASTGPT_BASE_URL以及报告生成过程。")

        # 获取GA4原始数据（你需要实现get_ga4_raw_data）
        # raw_ga4_data = get_ga4_raw_data(start_date, end_date)
        # report_date = end_date.date()
        # # 清洗并插入
        # insert_ga4_traffic_channels(clean_ga4_channels(raw_ga4_data), report_date)
        # insert_ga4_page_metrics(clean_ga4_pages(raw_ga4_data), report_date)
        # insert_ga4_session_depth(clean_ga4_sessions(raw_ga4_data), report_date)
        # insert_ga4_visit_depth(clean_ga4_visit_depth(raw_ga4_data), report_date)
        # insert_ga4_device_metrics(clean_ga4_devices(raw_ga4_data), report_date)

    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 