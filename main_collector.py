import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import defaultdict
import json # Para posible depuración de datos complejos
import time
import re

from connectors.woo_data import get_woo_orders_raw_data
from connectors.ga4_data import get_ga4_summary
from connectors.gsc_data import get_gsc_summary
from fastgpt_updater import update_fastgpt_kb_with_content
# import mysql.connector # 已注释

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

# def insert_ga4_traffic_channels(channel_data_list, report_date): # 已注释
#     # ... (整个函数体)
#     pass

# def insert_ga4_page_metrics(page_data_list, report_date): # 已注释
#     # ... (整个函数体)
#     pass

# def insert_ga4_session_depth(session_data_list, report_date): # 已注释
#     # ... (整个函数体)
#     pass

# def insert_ga4_visit_depth(visit_data, report_date): # 已注释
#     # ... (整个函数体)
#     pass

# def insert_ga4_device_metrics(device_data_list, report_date): # 已注释
#     # ... (整个函数体)
#     pass

# def clean_ga4_channels(raw_ga4_data): # 已注释
#     # ... (整个函数体)
#     pass

# def clean_ga4_pages(raw_ga4_data): # 已注释
#     # ... (整个函数体)
#     pass

# def clean_ga4_sessions(raw_ga4_data): # 已注释
#     # ... (整个函数体)
#     pass

# def clean_ga4_visit_depth(raw_ga4_data): # 已注释
#     # ... (整个函数体)
#     pass

# def clean_ga4_devices(raw_ga4_data): # 已注释
#     # ... (整个函数体)
#     pass

COMMON_UTM_KEYS = [
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    '_utm_source', '_utm_medium', '_utm_campaign', '_utm_term', '_utm_content',
    'wc_last_utm_source', 'wc_last_utm_medium', 'wc_last_utm_campaign',
    'initial_utm_source', 'initial_utm_medium', 'initial_utm_campaign',
    'http_referer', # Nota: HTTP_REFERER con mayúsculas también es común
]

def extract_utm_from_meta(meta_data_list):
    utm_params = {}
    if not isinstance(meta_data_list, list):
        return utm_params
    for meta_item in meta_data_list:
        if isinstance(meta_item, dict) and meta_item.get('key','').lower() in COMMON_UTM_KEYS:
            utm_params[meta_item['key'].lower()] = meta_item.get('value')
        # Algunos plugins guardan UTMs como un diccionario serializado en un solo meta
        elif isinstance(meta_item, dict) and meta_item.get('key','').lower() == 'utm_parameters': # Ejemplo
            try:
                value_data = meta_item.get('value')
                if isinstance(value_data, str):
                    possible_utm_dict = json.loads(value_data)
                    if isinstance(possible_utm_dict, dict):
                        for k, v in possible_utm_dict.items():
                            if k.lower().startswith('utm_'):
                                utm_params[k.lower()] = v
                elif isinstance(value_data, dict):
                     for k, v in value_data.items():
                        if k.lower().startswith('utm_'):
                            utm_params[k.lower()] = v
            except json.JSONDecodeError:
                logger.debug(f"No se pudo decodificar JSON para meta key 'utm_parameters': {meta_item.get('value')}")
            except Exception as e:
                logger.debug(f"Error procesando meta key 'utm_parameters': {e}")

    # Priorizar claves sin prefijo '_' si existen duplicados (ej: _utm_source y utm_source)
    cleaned_utm = {}
    for key, value in utm_params.items():
        plain_key = key.lstrip('_')
        if plain_key not in cleaned_utm or key == plain_key: # Tomar el valor de la clave sin _ o si no hay duplicado
            cleaned_utm[plain_key] = value
    return cleaned_utm

def process_and_format_woo_data_to_markdown(raw_orders_list, start_date_dt, end_date_dt):
    if not raw_orders_list:
        logger.info("没有收到WooCommerce订单进行处理.")
        return {"details_md": "### WooCommerce 订单详情 (警告)\n- 未收到任何订单数据。"}

    all_processed_orders_for_detail_md = []
    for order in raw_orders_list:
        if not isinstance(order, dict):
            logger.warning(f"在raw_orders_list中发现非字典项: {order}")
            continue
        
        billing_info = order.get('billing', {})
        customer_country = billing_info.get('country', '未知')
        utm_params = extract_utm_from_meta(order.get('meta_data', []))
        
        processed_order_info = {
            'id': order.get('id'),
            'date_created': order.get('date_created_gmt'),
            'status': order.get('status'),
            'total': order.get('total'),
            'currency': order.get('currency'),
            'customer_email': billing_info.get('email'),
            'customer_country': customer_country,
            'payment_method': order.get('payment_method_title'),
            'line_items': [{'name': li.get('name'), 'sku': li.get('sku'), 'quantity': li.get('quantity'), 'total': li.get('total')} for li in order.get('line_items', [])],
            'utm_params': utm_params
        }
        all_processed_orders_for_detail_md.append(processed_order_info)

    details_md_parts = [f"### WooCommerce 订单详情 ({start_date_dt.strftime('%Y-%m-%d')} 到 {end_date_dt.strftime('%Y-%m-%d')})\n"]
    if not all_processed_orders_for_detail_md:
        details_md_parts.append("- 在此期间没有需要报告的订单详情.")
    else:
        for p_order in all_processed_orders_for_detail_md:
            details_md_parts.append(f"\n---\n**订单ID**: {p_order['id']}")
            details_md_parts.append(f"- **日期**: {p_order['date_created']}")
            details_md_parts.append(f"- **状态**: {p_order['status']}")
            details_md_parts.append(f"- **订单总额**: {p_order['total']} {p_order['currency']}")
            details_md_parts.append(f"- **客户邮箱**: {p_order['customer_email']}")
            details_md_parts.append(f"- **客户国家**: {p_order['customer_country']}")
            details_md_parts.append(f"- **支付方式**: {p_order['payment_method']}")
            
            details_md_parts.append("  **订单商品:**")
            if p_order['line_items']:
                for item in p_order['line_items']:
                    details_md_parts.append(f"    - {item['name']} (SKU: {item['sku']}) - 数量: {item['quantity']}, 总计: {item['total']}")
            else:
                details_md_parts.append("    - 无商品信息.")
                
            details_md_parts.append("  **UTM参数:**")
            if p_order['utm_params']:
                for key, value in p_order['utm_params'].items():
                    details_md_parts.append(f"    - {key}: {value}")
            else:
                details_md_parts.append("    - 未找到UTM参数.")
            
    details_md = "\n".join(details_md_parts)
    
    # 生成主报告的摘要部分
    summary_md_for_main_report = "### WooCommerce 数据\n"
    if not all_processed_orders_for_detail_md:
        summary_md_for_main_report += "- 未处理任何订单数据。\n"
    else:
        summary_md_for_main_report += f"- 总订单数: {len(all_processed_orders_for_detail_md)}\n"
        # 统计USD订单总额
        usd_total_amount = sum(float(order['total']) for order in all_processed_orders_for_detail_md if order['currency'] == 'USD')
        summary_md_for_main_report += f"- 总销售额(USD): {usd_total_amount:.2f} USD\n"
        summary_md_for_main_report += "- 详细订单数据已生成在单独的文件中。\n"
        
    return {"summary_md": summary_md_for_main_report, "details_md": details_md}

def main():
    logger.info("开始数据收集和 Markdown 报告生成...")
    load_dotenv()

    # 获取FastGPT API密钥和配置
    fastgpt_api_key = os.getenv("FASTGPT_API_KEY")
    fastgpt_base_url = os.getenv("FASTGPT_BASE_URL")
    fastgpt_kb_id = os.getenv("FASTGPT_KB_ID")
    # fastgpt_collection_id = os.getenv("FASTGPT_COLLECTION_ID") # 这个在 fastgpt_updater.py 内部获取

    if not all([fastgpt_api_key, fastgpt_base_url, fastgpt_kb_id]):
        logger.error("FastGPT API密钥、基础URL或知识库ID (FASTGPT_KB_ID) 未配置。请检查.env文件。")
        return

    # 定义日期范围
    default_days = 7
    try:
        data_collection_days = int(os.getenv("DATA_COLLECTION_DAYS", default_days))
    except ValueError:
        logger.warning(f"DATA_COLLECTION_DAYS环境变量值无效，将使用默认值: {default_days} 天")
        data_collection_days = default_days

    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=data_collection_days)

    env_start_date_str = os.getenv("START_DATE")
    env_end_date_str = os.getenv("END_DATE")

    if env_start_date_str and env_end_date_str:
        try:
            start_date_dt = datetime.strptime(env_start_date_str, "%Y-%m-%d")
            end_date_dt = datetime.strptime(env_end_date_str, "%Y-%m-%d")
            logger.info(f"使用环境变量中的自定义日期范围: {start_date_dt.strftime('%Y-%m-%d')} 到 {end_date_dt.strftime('%Y-%m-%d')}")
        except ValueError:
            logger.error("环境变量中的START_DATE或END_DATE格式不正确 (应为 YYYY-MM-DD)。将使用计算出的日期范围。")
    
    report_generation_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    current_date_for_report_title = end_date_dt.strftime("%Y-%m-%d") # 通常报告是关于截止到某天的数据

    all_markdown_for_main_report = [] # Cambiado de all_markdown_summaries
    woo_detailed_report_md = ""

    # 1. WooCommerce 数据
    logger.info(f"获取WooCommerce数据 (从 {start_date_dt.strftime('%Y-%m-%d')} 到 {end_date_dt.strftime('%Y-%m-%d')})...")
    raw_woo_orders = get_woo_orders_raw_data(start_date_dt, end_date_dt)
    
    all_processed_orders_for_detail_md = []  # 初始化变量
    
    if raw_woo_orders:
        logger.info(f"成功获取 {len(raw_woo_orders)} 条原始WooCommerce订单。开始处理和格式化...")
        woo_processed_data = process_and_format_woo_data_to_markdown(raw_woo_orders, start_date_dt, end_date_dt)
        # woo_summary_for_main_report contendrá una nota sobre el archivo de detalles o una advertencia.
        woo_summary_for_main_report = woo_processed_data.get("summary_md", "") 
        woo_detailed_report_md = woo_processed_data.get("details_md", "") 
        
        # 保存处理后的订单数据
        all_processed_orders_for_detail_md = raw_woo_orders
        
        if woo_summary_for_main_report: # Siempre agregar la nota o advertencia de Woo al reporte principal
            all_markdown_for_main_report.append(woo_summary_for_main_report)
        logger.info("WooCommerce数据处理完成。详细报告已生成。")
    else:
        logger.warning("未能获取WooCommerce原始订单数据或返回空列表。")
        all_markdown_for_main_report.append("### WooCommerce 数据 (警告)\n- 未能获取原始订单数据。")

    # 2. GA4 数据
    logger.info(f"获取GA4数据 (从 {start_date_dt.strftime('%Y-%m-%d')} 到 {end_date_dt.strftime('%Y-%m-%d')})...")
    ga4_summary_md = get_ga4_summary(start_date_dt, end_date_dt)
    if ga4_summary_md and "(错误)" not in ga4_summary_md and "(警告)" not in ga4_summary_md:
        all_markdown_for_main_report.append(ga4_summary_md)
        logger.info("GA4 Markdown摘要获取完成。")
    elif ga4_summary_md: # Incluir si es mensaje de error/advertencia
        all_markdown_for_main_report.append(ga4_summary_md)
        logger.warning(f"获取GA4数据时返回警告或错误: {ga4_summary_md}")
    else:
        logger.warning("GA4数据获取返回空。")
        all_markdown_for_main_report.append("### GA4 数据 (警告)\n- 未返回任何数据。")

    # 3. GSC 数据
    logger.info(f"获取GSC数据...")
    gsc_end_date_dt = end_date_dt - timedelta(days=2) 
    gsc_start_date_dt = gsc_end_date_dt - timedelta(days=data_collection_days) # Asegurar la misma duración que otros conectores, pero desfasado
    # Corregir si el rango es inválido debido al desfase
    if gsc_start_date_dt > gsc_end_date_dt:
        gsc_start_date_dt = gsc_end_date_dt - timedelta(days=max(0, data_collection_days-2)) # Evitar duración negativa
        if gsc_start_date_dt > gsc_end_date_dt: # Si aún es problemático, ajustar a un solo día
             gsc_start_date_dt = gsc_end_date_dt

    logger.info(f"Ajustando rango de fechas para GSC: {gsc_start_date_dt.strftime('%Y-%m-%d')} a {gsc_end_date_dt.strftime('%Y-%m-%d')}")
    gsc_summary_md = get_gsc_summary(gsc_start_date_dt, gsc_end_date_dt)
    if gsc_summary_md and "(错误)" not in gsc_summary_md and "(警告)" not in gsc_summary_md:
        all_markdown_for_main_report.append(gsc_summary_md)
        logger.info("GSC Markdown摘要获取完成。")
    elif gsc_summary_md:
        all_markdown_for_main_report.append(gsc_summary_md)
        logger.warning(f"获取GSC数据时返回警告或错误: {gsc_summary_md}")
    else:
        logger.warning("GSC数据获取返回空。")
        all_markdown_for_main_report.append("### GSC 数据 (警告)\n- 未返回任何数据。")

    if not all_markdown_for_main_report or all( ("(错误)" in text or "(警告)" in text) and "WooCommerce 数据" not in text for text in all_markdown_for_main_report ):
        # Si all_markdown_for_main_report está vacío O todos sus elementos son errores/advertencias (excluyendo la nota de Woo)
        logger.info("没有收集到有效的数据摘要 (solo errores/advertencias o vacío)，脚本将不生成主报告文件或上传。")
    else:
        final_markdown_report = f"# 综合数据报告 - {current_date_for_report_title}\n\n"
        final_markdown_report += "\n\n---\n\n".join(all_markdown_for_main_report)

        export_dir = "data_exports"
        if not os.path.exists(export_dir):
            try:
                os.makedirs(export_dir)
                logger.info(f"创建目录: {export_dir}")
            except OSError as e:
                logger.error(f"创建目录 {export_dir} 失败: {e}")
        
        if os.path.exists(export_dir):
            report_filename_md = f"data_report_main_{report_generation_time_str}.md"
            report_filepath_md = os.path.join(export_dir, report_filename_md)
            try:
                with open(report_filepath_md, "w", encoding="utf-8") as f:
                    f.write(final_markdown_report)
                logger.info(f"Informe principal Markdown guardado en: {report_filepath_md}")

                logger.info(f"Comenzando subida del informe principal {report_filename_md} a FastGPT KB {fastgpt_kb_id}...")
                # 汇总数据只按###大标题分块推送到FastGPT
                if fastgpt_api_key and fastgpt_base_url and fastgpt_kb_id:
                    logger.info(f"开始按###大标题分块推送主报告汇总数据到FastGPT KB {fastgpt_kb_id}...")
                    for idx, summary_md in enumerate(all_markdown_for_main_report):
                        # 只按###大标题分块
                        blocks = re.split(r'(### .+)', summary_md)
                        chunk_list = []
                        i = 1
                        while i < len(blocks):
                            title = blocks[i].strip()
                            content = blocks[i+1].strip() if (i+1)<len(blocks) else ''
                            chunk = f"{title}\n{content}"
                            chunk_list.append(chunk)
                            i += 2
                        for chunk_idx, chunk in enumerate(chunk_list):
                            file_name = f"main_summary_part{idx+1}_section{chunk_idx+1}_{report_generation_time_str}.md"
                            logger.info(f"推送主报告汇总 section{chunk_idx+1} 内容预览: {chunk[:200]} ...")
                            success = update_fastgpt_kb_with_content(
                                api_key=fastgpt_api_key,
                                base_url=fastgpt_base_url,
                                kb_id=fastgpt_kb_id,
                                file_name=file_name,
                                content=chunk
                            )
                            if success:
                                logger.info(f"主报告汇总 section{chunk_idx+1} 推送成功")
                            else:
                                logger.error(f"主报告汇总 section{chunk_idx+1} 推送失败")
                            time.sleep(1)
                    logger.info("主报告汇总数据按###大标题分块推送完成")

            except IOError as e:
                logger.error(f"Error al guardar o procesar el informe principal Markdown: {e}")
        else:
            logger.error("El directorio de exportación no existe y no pudo ser creado. No se guardará ni subirá el informe principal.")

    # Guardar el informe detallado de WooCommerce si existe y contiene datos reales
    if woo_detailed_report_md and "未收到任何订单数据" not in woo_detailed_report_md and "没有需要报告的订单详情" not in woo_detailed_report_md:
        export_dir = "data_exports" # Asegurar que existe, aunque ya se haya verificado arriba
        if not os.path.exists(export_dir):
            try:
                os.makedirs(export_dir)
                logger.info(f"创建目录: {export_dir}") # Log creation
            except OSError as e:
                logger.error(f"创建目录 {export_dir} 失败: {e}") # Log error if creation fails
        
        if os.path.exists(export_dir):
            woo_detail_filename = f"woo_orders_detail_{report_generation_time_str}.md"
            woo_detail_filepath = os.path.join(export_dir, woo_detail_filename)
            try:
                # 分批推送WooCommerce详细数据到FastGPT（每条订单单独推送）
                if fastgpt_api_key and fastgpt_base_url and fastgpt_kb_id:
                    logger.info(f"开始分批推送WooCommerce详细订单数据到FastGPT KB {fastgpt_kb_id}...")
                    for order in all_processed_orders_for_detail_md:
                        # 生成单条订单的markdown内容
                        items_info = []
                        for item in order.get('line_items', []):
                            items_info.append(f"{item.get('name', 'N/A')} (SKU: {item.get('sku', 'N/A')})")
                        items_str = "<br>".join(items_info)
                        customer_info = []
                        if order.get('billing'):
                            billing = order['billing']
                            customer_info.append(f"{billing.get('first_name', '')} {billing.get('last_name', '')}")
                            if billing.get('email'):
                                customer_info.append(billing['email'])
                        customer_str = "<br>".join(customer_info) if customer_info else "N/A"
                        notes = []
                        for note in order.get('meta_data', []):
                            if note.get('key') == '_order_comments':
                                notes.append(note.get('value', ''))
                        notes_str = "<br>".join(notes) if notes else "N/A"
                        order_md = (
                            f"### WooCommerce 订单\n"
                            f"- 订单ID: {order.get('id', 'N/A')}\n"
                            f"- 日期: {order.get('date_created', 'N/A')}\n"
                            f"- 状态: {order.get('status', 'N/A')}\n"
                            f"- 客户: {customer_str}\n"
                            f"- 商品: {items_str}\n"
                            f"- 数量: {sum(item.get('quantity', 0) for item in order.get('line_items', []))}\n"
                            f"- 总金额: {order.get('total', 'N/A')}\n"
                            f"- 币种: {order.get('currency', 'N/A')}\n"
                            f"- 支付方式: {order.get('payment_method_title', 'N/A')}\n"
                            f"- 备注: {notes_str}\n"
                        )
                        file_name = f"woo_order_{order.get('id', 'N/A')}.md"
                        logger.info(f"推送订单ID {order.get('id', 'N/A')} 内容预览: {order_md[:200]} ...")
                        success = update_fastgpt_kb_with_content(
                            api_key=fastgpt_api_key,
                            base_url=fastgpt_base_url,
                            kb_id=fastgpt_kb_id,
                            file_name=file_name,
                            content=order_md
                        )
                        if success:
                            logger.info(f"订单ID {order.get('id', 'N/A')} 推送成功")
                        else:
                            logger.error(f"订单ID {order.get('id', 'N/A')} 推送失败")
                        time.sleep(1)  # 避免接口限流
                    logger.info("WooCommerce详细订单数据分批推送完成")

            except IOError as e:
                logger.error(f"Error al guardar o procesar el informe detallado de WooCommerce: {e}")
        else:
             logger.error("El directorio de exportación no existe y no pudo ser creado. No se guardará ni subirá el informe detallado de WooCommerce.")

    logger.info("Proceso de generación de informes Markdown completado.")

if __name__ == "__main__":
    # 加载环境变量，确保日志等配置在main()调用前生效
    load_dotenv() 
    main()