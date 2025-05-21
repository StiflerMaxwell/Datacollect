import os
import json
import time
import jwt
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

load_dotenv()

def format_gsc_data_to_markdown_table(headers, rows_data, metric_formatters=None):
    if not rows_data:
        return "    - 无数据\n"
    table = f"| {' | '.join(headers)} |\n"
    table += f"|{'|'.join(['---'] * len(headers))}|\n"
    for r_data in rows_data:
        formatted_row = []
        for header in headers:
            value = r_data.get(header, 'N/A')
            if metric_formatters and header in metric_formatters:
                try:
                    value = metric_formatters[header](value)
                except Exception:
                    pass 
            formatted_row.append(str(value))
        table += f"| {' | '.join(formatted_row)} |\n"
    return table

class GSCClient:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.site_url = os.getenv("VITE_GSC_SITE_URL")
        self.client_email = os.getenv("VITE_GSC_CLIENT_EMAIL")
        raw_private_key = os.getenv("VITE_GSC_PRIVATE_KEY", "")
        
        logger.debug(f"GSC 原始私钥 (前50字符): {raw_private_key[:50]}")
        
        self.private_key = raw_private_key.replace("\\n", "\n")
        
        # 验证私钥格式
        if not self.private_key.strip().startswith("-----BEGIN PRIVATE KEY-----") or \
           not self.private_key.strip().endswith("-----END PRIVATE KEY-----"):
            logger.warning("GSC私钥格式似乎不正确。请确保它包含完整的BEGIN/END标记并且换行符正确。")

        self.api_url = "https://www.googleapis.com/webmasters/v3/sites"

    def get_access_token(self):
        """获取访问令牌"""
        if self.access_token and self.token_expiry and time.time() < self.token_expiry:
            return self.access_token

        now = int(time.time())
        header = {
            "alg": "RS256",
            "typ": "JWT"
        }
        
        payload = {
            "iss": self.client_email,
            "sub": self.client_email,
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
            "scope": "https://www.googleapis.com/auth/webmasters.readonly"
        }

        try:
            if not self.private_key or not self.client_email:
                logger.error("GSC客户端邮件或私钥未配置。")
                raise ValueError("GSC客户端邮件或私钥未配置。")
            jwt_token = jwt.encode(payload, self.private_key, algorithm="RS256", headers=header)
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt_token
                }
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.token_expiry = now + token_data["expires_in"]
            return self.access_token
        except jwt.exceptions.InvalidKeyError as ike:
            logger.error(f"GSC JWT无效密钥错误: {str(ike)} - 这通常意味着私钥格式无法被解析。请检查VITE_GSC_PRIVATE_KEY环境变量。确保BEGIN/END标记存在且换行符正确。")
            raise
        except Exception as e:
            logger.error(f"获取GSC访问令牌失败: {str(e)}")
            if "Could not deserialize key data" in str(e) or "parse" in str(e).lower():
                 logger.error("详细错误提示：GSC私钥解析失败。请检查VITE_GSC_PRIVATE_KEY环境变量中的私钥格式，确保BEGIN/END标记完整，并且换行符（\n）正确无误。不要使用字面上的\\n。")
            raise

    def query_search_analytics(self, start_date, end_date, dimensions, row_limit=10, search_type='web'):
        """运行GSC报告"""
        if not self.site_url:
            logger.error("GSC站点URL未配置。")
            return None

        try:
            token = self.get_access_token()
            site_url_encoded = quote_plus(self.site_url)
            api_url = f"{self.api_url}/{site_url_encoded}/searchAnalytics/query"
            
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': row_limit,
                'searchType': search_type
            }

            response = requests.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GSC API请求失败 (维度: {dimensions}): {e}", exc_info=True)
            return None

def get_gsc_summary(start_date_dt, end_date_dt):
    if not (os.getenv("VITE_GSC_SITE_URL") and os.getenv("VITE_GSC_CLIENT_EMAIL") and os.getenv("VITE_GSC_PRIVATE_KEY")):
        logger.warning("GSC环境变量未完全配置。")
        return "### GSC 数据 (警告)\n- 环境变量未完全配置\n"

    try:
        client = GSCClient()
        start_date_str = start_date_dt.strftime("%Y-%m-%d")
        end_date_str = end_date_dt.strftime("%Y-%m-%d")
        
        markdown_output = [f"### GSC 数据 ({start_date_str} to {end_date_str})\n"]

        # 1. 总体概要指标
        logger.info("获取GSC数据: 总体概要")
        data_for_totals = client.query_search_analytics(start_date_str, end_date_str, dimensions=['query'], row_limit=25000)
        
        total_clicks = 0
        total_impressions = 0
        avg_ctr = 0
        avg_position = 0

        if data_for_totals and data_for_totals.get('rows'):
            rows_for_totals = data_for_totals.get('rows', [])
            total_clicks = sum(r.get('clicks', 0) for r in rows_for_totals)
            total_impressions = sum(r.get('impressions', 0) for r in rows_for_totals)
            if total_impressions > 0:
                avg_ctr = sum(r.get('ctr', 0) * r.get('impressions', 0) for r in rows_for_totals) / total_impressions
                avg_position = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows_for_totals) / total_impressions
            
            markdown_output.append(f"- **总点击量**: {total_clicks}")
            markdown_output.append(f"- **总展示量**: {total_impressions}")
            markdown_output.append(f"- **平均点击率**: {avg_ctr*100:.2f}%")
            markdown_output.append(f"- **平均排名**: {avg_position:.2f}\n")
        else:
            markdown_output.append("- **总体数据**: 获取失败或无数据\n")

        metric_formatters_pct = {'点击率(%)': lambda x: f"{x*100:.2f}%"}
        metric_formatters_pos = {'平均排名': lambda x: f"{x:.2f}"}
        metric_formatters_combined = {**metric_formatters_pct, **metric_formatters_pos}

        # 2. 按"搜索词" (Query) 的详细表格
        logger.info("获取GSC数据: 按搜索词")
        query_data = client.query_search_analytics(start_date_str, end_date_str, dimensions=['query'], row_limit=100)
        md_section = "#### 1. 热门搜索词 (前100)\n"
        if query_data and query_data.get('rows'):
            headers = ["搜索词", "点击量", "展示量", "点击率(%)", "平均排名"]
            rows_for_table = []
            for row in query_data['rows']:
                rows_for_table.append({
                    "搜索词": row['keys'][0],
                    "点击量": row.get('clicks', 0),
                    "展示量": row.get('impressions', 0),
                    "点击率(%)": row.get('ctr', 0),
                    "平均排名": row.get('position', 0)
                })
            md_section += format_gsc_data_to_markdown_table(headers, rows_for_table, metric_formatters_combined)
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 3. 按"页面" (Page) 的详细表格
        logger.info("获取GSC数据: 按页面")
        page_data = client.query_search_analytics(start_date_str, end_date_str, dimensions=['page'], row_limit=100)
        md_section = "#### 2. 热门页面 (前100)\n"
        if page_data and page_data.get('rows'):
            headers = ["页面URL", "点击量", "展示量", "点击率(%)", "平均排名"]
            rows_for_table = []
            for row in page_data['rows']:
                rows_for_table.append({
                    "页面URL": row['keys'][0],
                    "点击量": row.get('clicks', 0),
                    "展示量": row.get('impressions', 0),
                    "点击率(%)": row.get('ctr', 0),
                    "平均排名": row.get('position', 0)
                })
            md_section += format_gsc_data_to_markdown_table(headers, rows_for_table, metric_formatters_combined)
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 4. 按"国家" (Country) 的详细表格
        logger.info("获取GSC数据: 按国家")
        country_data = client.query_search_analytics(start_date_str, end_date_str, dimensions=['country'], row_limit=100)
        md_section = "#### 3. 主要国家 (前100)\n"
        if country_data and country_data.get('rows'):
            headers = ["国家", "点击量", "展示量", "点击率(%)", "平均排名"]
            rows_for_table = []
            for row in country_data['rows']:
                rows_for_table.append({
                    "国家": row['keys'][0],
                    "点击量": row.get('clicks', 0),
                    "展示量": row.get('impressions', 0),
                    "点击率(%)": row.get('ctr', 0),
                    "平均排名": row.get('position', 0)
                })
            md_section += format_gsc_data_to_markdown_table(headers, rows_for_table, metric_formatters_combined)
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 5. 按"设备" (Device) 的详细表格
        logger.info("获取GSC数据: 按设备")
        device_data = client.query_search_analytics(start_date_str, end_date_str, dimensions=['device'], row_limit=100)
        md_section = "#### 4. 按设备类型\n"
        if device_data and device_data.get('rows'):
            headers = ["设备类型", "点击量", "展示量", "点击率(%)", "平均排名"]
            rows_for_table = []
            for row in device_data['rows']:
                rows_for_table.append({
                    "设备类型": row['keys'][0],
                    "点击量": row.get('clicks', 0),
                    "展示量": row.get('impressions', 0),
                    "点击率(%)": row.get('ctr', 0),
                    "平均排名": row.get('position', 0)
                })
            md_section += format_gsc_data_to_markdown_table(headers, rows_for_table, metric_formatters_combined)
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        return "\n".join(markdown_output)

    except Exception as e:
        logger.error(f"获取GSC详细数据时发生严重错误: {str(e)}", exc_info=True)
        return f"### GSC 数据 (严重错误)\n- 获取数据失败: {str(e)}\n"

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("开始GSC连接器独立测试...")
    
    if not (os.getenv("VITE_GSC_SITE_URL") and os.getenv("VITE_GSC_CLIENT_EMAIL") and os.getenv("VITE_GSC_PRIVATE_KEY")):
        print("请确保.env文件中已配置VITE_GSC_SITE_URL, VITE_GSC_CLIENT_EMAIL, VITE_GSC_PRIVATE_KEY 等环境变量用于测试")
    else:
        today = datetime.now()
        end_date_test = today - timedelta(days=3)
        start_date_test = end_date_test - timedelta(days=7)
        
        print(f"测试GSC数据范围: {start_date_test.strftime('%Y-%m-%d')} to {end_date_test.strftime('%Y-%m-%d')}")
        print("\n--- GSC Report Start ---")
        summary = get_gsc_summary(start_date_test, end_date_test)
        print(summary)
        print("--- GSC Report End ---\n")
        if "错误" in summary or "失败" in summary or "警告" in summary:
            print("测试运行中检测到错误/失败/警告。请检查日志和输出。")
        else:
            print("测试运行似乎已成功完成。") 