from flask import Flask, request, jsonify
from flask_cors import CORS # 用于处理跨域请求
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime, timedelta, date # 确保导入 date
from decimal import Decimal # 用于处理数据库中的DECIMAL类型
import json # 用于处理JSON数据，例如meta_data

# 加载环境变量
load_dotenv()

# 初始化Flask应用
app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，生产环境可以配置更严格的规则

# --- 数据库连接信息从 .env 文件读取 ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# --- 辅助函数：获取数据库连接 ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT), # 确保端口是整数
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        # print("数据库连接成功！") # 可以在调试时取消注释
        return conn
    except mysql.connector.Error as err:
        app.logger.error(f"数据库连接失败: {err}") # 使用 app.logger 记录错误
        raise # 重新抛出异常，让上层处理

# --- 辅助函数：序列化特殊数据类型以便JSON转换 ---
def custom_json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj) # 将Decimal转换为float以便JSON序列化
    raise TypeError(f"Type {type(obj)} not serializable")

# --- API 端点 ---
@app.route('/get_data', methods=['POST'])
def get_data_endpoint():
    conn = None
    cursor = None
    try:
        payload = request.json
        if not payload:
            return jsonify({"error": "Missing JSON payload"}), 400

        data_type = payload.get('data_type')
        params = payload.get('params', {}) # 其他参数，如date_range, ids, event_name等
        
        app.logger.info(f"接收到请求: data_type='{data_type}', params={json.dumps(params, indent=2)}")


        # --- 根据 data_type 调用不同的数据获取逻辑 ---
        result_data = None
        sql_query = None
        query_params_tuple = () # 用于参数化查询的元组

        # 默认日期范围 (例如过去7天)，如果params中没有提供
        days_ago_default = params.get('days_ago', 7)
        try:
            end_date_param = params.get('end_date', (datetime.now().date()).isoformat())
            start_date_param = params.get('start_date', (datetime.now().date() - timedelta(days=days_ago_default)).isoformat())
            
            # 将日期字符串转换为 date 对象进行比较
            end_date_obj = date.fromisoformat(end_date_param)
            start_date_obj = date.fromisoformat(start_date_param)
        except ValueError:
            return jsonify({"error": "无效的日期格式。请使用 YYYY-MM-DD 格式。"}), 400


        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # dictionary=True 使fetchall返回字典列表

        # --------------------------------------------------------------------
        # 示例：从您的数据库获取 WooCommerce 订单数据
        # --------------------------------------------------------------------
        if data_type == 'db_woocommerce_orders':
            status_filter = params.get('status', 'completed')
            limit_filter = int(params.get('max_orders', 10)) # 确保是整数
            
            # 注意：MySQL的DATETIME列存储时不带时区，比较时需确保应用端和数据库端对日期的理解一致
            # 如果date_created_gmt存储的是GMT时间，而start_date_obj/end_date_obj是本地日期，需要转换
            # 为简化，这里假设date_created_gmt可以直接与日期部分比较
            sql_query = """
                SELECT order_id, order_number, status, currency, total_amount, 
                       customer_id, date_created_gmt, meta_data
                FROM woocommerce_orders
                WHERE DATE(date_created_gmt) >= %s AND DATE(date_created_gmt) <= %s 
                      AND status = %s
                ORDER BY date_created_gmt DESC
                LIMIT %s;
            """
            query_params_tuple = (start_date_obj, end_date_obj, status_filter, limit_filter)
            
            cursor.execute(sql_query, query_params_tuple)
            orders_from_db = cursor.fetchall()
            result_data = {"orders": orders_from_db}
        
        # --------------------------------------------------------------------
        # 示例：获取 WooCommerce 订单的商品行项目
        # --------------------------------------------------------------------
        elif data_type == 'db_woocommerce_order_items':
            order_id_filter = params.get('order_id')
            if not order_id_filter:
                return jsonify({"error": "请求 'db_woocommerce_order_items' 时缺少 'order_id' 参数。"}), 400
            
            sql_query = """
                SELECT item_id, order_id, product_id, product_name, quantity, total, sku, meta_data
                FROM woocommerce_order_items
                WHERE order_id = %s;
            """
            query_params_tuple = (int(order_id_filter),) # 确保order_id是整数
            
            cursor.execute(sql_query, query_params_tuple)
            items_from_db = cursor.fetchall()
            result_data = {"order_id": order_id_filter, "items": items_from_db}

        # --------------------------------------------------------------------
        # 示例：获取 GA4 每日总体概览
        # --------------------------------------------------------------------
        elif data_type == 'db_ga4_daily_overview':
            sql_query = """
                SELECT report_date, active_users, sessions, engagement_rate, conversions_total, total_revenue
                FROM ga4_daily_overview
                WHERE report_date >= %s AND report_date <= %s
                ORDER BY report_date DESC;
            """
            query_params_tuple = (start_date_obj, end_date_obj)
            cursor.execute(sql_query, query_params_tuple)
            overview_data = cursor.fetchall()
            result_data = {"ga4_daily_overview": overview_data}

        # --------------------------------------------------------------------
        # ... 为您需要实时查询的其他数据类型添加 elif 分支 ...
        # 例如: db_ga4_traffic_sources, db_gsc_query_performance, db_ads_performance 等
        # --------------------------------------------------------------------
        
        else:
            return jsonify({"error": f"不支持的数据类型: {data_type}"}), 400

        # 使用自定义序列化器处理特殊类型
        # Flask的jsonify默认可能无法处理datetime.date或Decimal，所以我们先用json.dumps配合default参数
        json_compatible_result = json.loads(json.dumps(result_data, default=custom_json_serializer))
        
        app.logger.info(f"成功处理请求: data_type='{data_type}', 返回数据键: {list(json_compatible_result.keys()) if isinstance(json_compatible_result, dict) else 'Non-dict response'}")
        return jsonify(json_compatible_result), 200

    except mysql.connector.Error as db_err:
        app.logger.error(f"数据库操作错误 for data_type '{data_type}': {db_err}", exc_info=True)
        return jsonify({"error": f"数据库操作失败: {db_err}", "data_type": data_type}), 500
    except Exception as e:
        app.logger.error(f"处理 /get_data 请求时发生内部错误: {str(e)}", exc_info=True)
        return jsonify({"error": "发生内部服务器错误", "details": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected(): # 检查连接是否仍然打开
            conn.close()
            # print("数据库连接已关闭。") # 调试时取消注释

@app.route('/get_ga4_pages', methods=['GET'])
def get_ga4_pages():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT report_date, page_path, avg_time_on_page, bounce_rate
        FROM ga4_page_metrics
        WHERE report_date >= %s AND report_date <= %s
        ORDER BY report_date DESC, avg_time_on_page DESC
        LIMIT 100
    """
    cursor.execute(sql, (start_date, end_date))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)

@app.route('/get_ga4_channels', methods=['GET'])
def get_ga4_channels():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT report_date, channel, visitors, avg_engagement_time
        FROM ga4_traffic_channels
        WHERE report_date >= %s AND report_date <= %s
        ORDER BY report_date DESC, visitors DESC
        LIMIT 100
    """
    cursor.execute(sql, (start_date, end_date))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)

@app.route('/get_ga4_devices', methods=['GET'])
def get_ga4_devices():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT report_date, device_type, visitors, bounce_rate, avg_visit_time, add_to_cart, checkout
        FROM ga4_device_metrics
        WHERE report_date >= %s AND report_date <= %s
        ORDER BY report_date DESC, visitors DESC
        LIMIT 100
    """
    cursor.execute(sql, (start_date, end_date))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)

@app.route('/get_ga4_sessions', methods=['GET'])
def get_ga4_sessions():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT report_date, session_depth, bounce_rate, add_to_cart, checkout
        FROM ga4_session_depth
        WHERE report_date >= %s AND report_date <= %s
        ORDER BY report_date DESC, session_depth DESC
        LIMIT 100
    """
    cursor.execute(sql, (start_date, end_date))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)

@app.route('/get_ga4_visit_depth', methods=['GET'])
def get_ga4_visit_depth():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT report_date, visitors, visits
        FROM ga4_visit_depth
        WHERE report_date >= %s AND report_date <= %s
        ORDER BY report_date DESC
        LIMIT 100
    """
    cursor.execute(sql, (start_date, end_date))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    # 确保您的 .env 文件已配置，并且MySQL服务正在本地运行
    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        print("错误：一个或多个必要的数据库环境变量未设置。请检查 .env 文件。")
        print("需要: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
    else:
        print(f"API服务将在 http://localhost:5001 上启动...")
        print(f"连接到数据库: host={DB_HOST}, port={DB_PORT}, db={DB_NAME}, user={DB_USER}")
        app.run(debug=True, host='0.0.0.0', port=5001) # host='0.0.0.0' 使其可以从局域网访问（如果需要）