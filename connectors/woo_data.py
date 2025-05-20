import os
import logging
from woocommerce import API
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

logger = logging.getLogger(__name__)

def get_woo_summary(start_date_dt, end_date_dt):
    """
    获取WooCommerce数据摘要
    
    Args:
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        
    Returns:
        str: 格式化的数据摘要
    """
    store_url_env = os.getenv("VITE_WOO_API_URL")
    consumer_key = os.getenv("VITE_WOO_CONSUMER_KEY")
    consumer_secret = os.getenv("VITE_WOO_CONSUMER_SECRET")

    logger.info(f"从环境变量加载的 VITE_WOO_API_URL: {store_url_env}")

    if not all([store_url_env, consumer_key, consumer_secret]):
        logger.error("WooCommerce API凭据未完全配置。请检查VITE_WOO_API_URL, VITE_WOO_CONSUMER_KEY, 和 VITE_WOO_CONSUMER_SECRET环境变量。")
        return "## WooCommerce数据 (错误)\n- API凭据未完全配置"

    store_url = store_url_env
    if not store_url.startswith(("http://", "https://")):
         logger.error(f"WooCommerce API URL '{store_url}' 格式不正确，应以http://或https://开头。")
         return "## WooCommerce数据 (错误)\n- API URL格式不正确"
    
    # WooCommerce Python库通常希望url是站点基础URL，它会自动附加 /wp-json/wc/v3/
    # 我们移除可能的API路径后缀，只保留基础URL
    if "/wp-json/" in store_url:
        store_url = store_url.split("/wp-json/")[0]
    
    if not store_url.endswith("/"):
        store_url += "/"
    
    logger.info(f"调整后的WooCommerce站点基础URL: {store_url}")

    wcapi = API(
        url=store_url, 
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        version="wc/v3", # 确保库知道我们期望v3
        timeout=30 
    )

    try:
        start_date_str = start_date_dt.isoformat()
        end_date_str = end_date_dt.isoformat()

        logger.info(f"从WooCommerce获取订单数据，时间范围: {start_date_str} 到 {end_date_str}")
        orders_data = wcapi.get(
            "orders",
            params={"after": start_date_str, "before": end_date_str, "per_page": 100, "status": "processing,completed"}
        ).json()

        if isinstance(orders_data, dict) and orders_data.get("code"):
            api_code = orders_data.get('code')
            api_message = orders_data.get('message', '未知错误')
            logger.error(f"WooCommerce API请求失败: {api_message} (代码: {api_code}) - 使用的URL: {wcapi.url}")
            if api_code == "rest_no_route":
                 api_message += " 请检查您的VITE_WOO_API_URL是否正确指向您的WordPress站点根目录，并确保WooCommerce REST API已启用且固定链接设置为非朴素模式。WordPress后台 > 设置 > 固定链接。"
            return f"## WooCommerce数据 (错误)\n- API请求失败: {api_message}"

        total_orders = 0
        total_revenue = 0
        total_items_sold = 0
        product_counts = {}
        valid_statuses = ["processing", "completed"]
        for order in orders_data:
            if isinstance(order, dict) and order.get("status") in valid_statuses:
                total_orders +=1
                total_revenue += float(order.get("total", 0))
                for item in order.get("line_items", []):
                    total_items_sold += item.get("quantity", 0)
                    product_name = item.get("name", "未知产品")
                    product_counts[product_name] = product_counts.get(product_name, 0) + item.get("quantity", 0)

        top_products = sorted(product_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        top_products_str = ", ".join([f"{name} ({count})" for name, count in top_products]) if top_products else "无数据"

        summary = f"""## WooCommerce数据 ({start_date_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')})
总订单数 (处理中/已完成): {total_orders}
总收入: {total_revenue:.2f}
总销售件数: {total_items_sold}
热门产品 (前3): {top_products_str}
"""
        return summary

    except Exception as e:
        # 在异常中也打印使用的URL
        final_url_attempted = wcapi.url + wcapi.endpoint if hasattr(wcapi, 'url') and hasattr(wcapi, 'endpoint') else 'N/A'
        logger.error(f"WooCommerce API请求时发生异常: {str(e)} - 尝试的URL可能类似: {final_url_attempted}")
        return f"## WooCommerce数据 (错误)\n- 获取数据失败: {str(e)}"

if __name__ == '__main__':
    # 测试代码
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)
    print(get_woo_summary(thirty_days_ago, today)) 