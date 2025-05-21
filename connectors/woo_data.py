import os
import logging
from woocommerce import API
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

logger = logging.getLogger(__name__)

def get_woo_orders_raw_data(start_date_dt, end_date_dt):
    """
    获取WooCommerce在指定日期范围内的所有原始订单数据。
    
    Args:
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        
    Returns:
        list: 包含原始订单数据的列表 (每个订单是一个字典), 或者在失败时返回空列表。
    """
    store_url_env = os.getenv("VITE_WOO_API_URL")
    consumer_key = os.getenv("VITE_WOO_CONSUMER_KEY")
    consumer_secret = os.getenv("VITE_WOO_CONSUMER_SECRET")

    logger.info(f"从环境变量加载的 VITE_WOO_API_URL: {store_url_env}")

    if not all([store_url_env, consumer_key, consumer_secret]):
        logger.error("WooCommerce API凭据未完全配置。请检查VITE_WOO_API_URL, VITE_WOO_CONSUMER_KEY, 和 VITE_WOO_CONSUMER_SECRET环境变量。")
        return [] # 返回空列表表示失败或无数据

    store_url = store_url_env
    if not store_url.startswith(("http://", "https://")):
         logger.error(f"WooCommerce API URL '{store_url}' 格式不正确，应以http://或https://开头。")
         return []

    if "/wp-json/" in store_url:
        store_url = store_url.split("/wp-json/")[0]
    
    if not store_url.endswith("/"):
        store_url += "/"
    
    logger.info(f"调整后的WooCommerce站点基础URL: {store_url}")

    wcapi = API(
        url=store_url, 
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        version="wc/v3",
        timeout=60 # 增加超时时间以应对大量数据
    )

    all_orders = []
    page = 1
    per_page = 100 # 根据API限制和性能考虑调整

    # WooCommerce 日期需要ISO 8601格式
    start_date_iso = start_date_dt.isoformat()
    # For 'before', to include the whole end_date_dt, we might need to set it to the end of that day.
    # Or, if WooCommerce 'before' is exclusive, use start of next day.
    # Let's assume start_date_dt and end_date_dt define an inclusive range desired by user.
    # WC 'before' is exclusive. To include orders on end_date_dt, use (end_date_dt + 1 day).
    end_date_exclusive_iso = (end_date_dt + timedelta(days=1)).isoformat()


    logger.info(f"从WooCommerce获取订单数据，时间范围: {start_date_iso} (inclusive) 到 {end_date_exclusive_iso} (exclusive)")

    while True:
        try:
            logger.debug(f"正在获取订单第 {page} 页...")
            response = wcapi.get(
                "orders",
                params={
                    "after": start_date_iso,
                    "before": end_date_exclusive_iso, 
                    "per_page": per_page, 
                    "page": page,
                    "status": "processing,completed", # 保持状态过滤
                    "orderby": "date", # 确保订单有序，便于分页
                    "order": "asc"
                }
            )
            
            # 检查响应头获取总页数 (更可靠的分页方式)
            total_pages = int(response.headers.get('X-WP-TotalPages', 0))
            current_page_orders = response.json()

            if isinstance(current_page_orders, dict) and current_page_orders.get("code"):
                api_code = current_page_orders.get('code')
                api_message = current_page_orders.get('message', '未知API错误')
                logger.error(f"WooCommerce API请求失败 (页 {page}): {api_message} (代码: {api_code}) - 使用的URL: {wcapi.url}")
                if api_code == "rest_no_route":
                     api_message += " 请检查您的VITE_WOO_API_URL是否正确指向您的WordPress站点根目录，并确保WooCommerce REST API已启用且固定链接设置为非朴素模式。"
                # 如果一页失败，可以选择停止或跳过；这里我们停止
                return [] # 返回空列表表示处理中出错

            if not current_page_orders: # 如果当前页没有订单
                logger.info("当前页没有订单，停止分页。")
                break
            
            all_orders.extend(current_page_orders)
            logger.info(f"成功获取第 {page} 页订单，共 {len(current_page_orders)} 条。累计订单: {len(all_orders)}.")

            if total_pages > 0: # 使用响应头中的总页数
                if page >= total_pages:
                    logger.info(f"已达到总页数 {total_pages}，停止分页。")
                    break
            elif len(current_page_orders) < per_page: # 备用逻辑：如果返回的订单数少于请求数
                logger.info("返回的订单数少于每页请求数，假设已是最后一页。")
                break
            
            page += 1
            # 为防止无限循环或过多请求，可以设置一个最大页数限制
            if page > 200: # 例如，最大200页 (200 * 100 = 20000订单)
                logger.warning("已达到最大分页限制 (200页)，停止获取更多订单。")
                break

        except requests.exceptions.RequestException as req_e:
            logger.error(f"WooCommerce API网络请求时发生异常 (页 {page}): {str(req_e)}")
            return [] # 网络问题也返回空列表
        except Exception as e:
            logger.error(f"处理WooCommerce订单数据时发生未知异常 (页 {page}): {str(e)}", exc_info=True)
            return [] # 其他未知错误也返回空列表

    logger.info(f"成功获取所有WooCommerce订单，总计: {len(all_orders)} 条。")
    return all_orders

# 更新测试代码以反映函数名称和返回类型的更改
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger.info("开始WooCommerce连接器独立测试 (获取原始订单数据)...")

    if not (os.getenv("VITE_WOO_API_URL") and os.getenv("VITE_WOO_CONSUMER_KEY") and os.getenv("VITE_WOO_CONSUMER_SECRET")):
        print("错误：请确保.env文件中已配置VITE_WOO_API_URL, VITE_WOO_CONSUMER_KEY, 和 VITE_WOO_CONSUMER_SECRET。")
    else:
        today = datetime.now()
        # GSC和GA4用过去7天到过去3天，WooCommerce可以更近，比如过去7天到今天
        start_test_date = today - timedelta(days=7)
        end_test_date = today 
        
        print(f"测试WooCommerce订单数据范围: {start_test_date.strftime('%Y-%m-%d')} to {end_test_date.strftime('%Y-%m-%d')}")
        
        raw_orders = get_woo_orders_raw_data(start_test_date, end_test_date)
        
        if raw_orders:
            print(f"成功获取 {len(raw_orders)} 条原始订单数据。")
            print("前2条订单示例:")
            for i, order in enumerate(raw_orders[:2]):
                print(f"--- 订单 {i+1} (ID: {order.get('id')}) ---")
                # 只打印一些关键信息作为示例，避免过多输出
                print(f"  状态: {order.get('status')}")
                print(f"  总金额: {order.get('total')}")
                print(f"  客户ID: {order.get('customer_id')}")
                print(f"  商品数量: {len(order.get('line_items', []))}")
            if len(raw_orders) > 2:
                print("...")
        elif raw_orders == []: # 明确检查空列表，因为函数在错误时返回它
             print("未能获取WooCommerce订单数据，或指定时间范围内无订单。请检查日志。")
        # 如果函数设计为在错误时可能返回None（虽然当前不是这样），也需要检查
        # else:
        # print("获取WooCommerce订单数据失败，返回值为None。请检查日志。")
        print("--- WooCommerce连接器测试结束 ---") 