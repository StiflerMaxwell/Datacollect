import os
import json
import time
import jwt
import requests
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, Dimension, RunReportRequest, OrderBy
from google.oauth2 import service_account
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class GA4Client:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.property_id = os.getenv("VITE_GA4_PROPERTY_ID")
        self.client_email = os.getenv("VITE_GA4_CLIENT_EMAIL")
        raw_private_key = os.getenv("VITE_GA4_PRIVATE_KEY", "")
        
        logger.debug(f"GA4 原始私钥 (前50字符): {raw_private_key[:50]}")
        
        self.private_key = raw_private_key.replace("\\n", "\n")
        
        # 验证私钥格式
        if not self.private_key.strip().startswith("-----BEGIN PRIVATE KEY-----") or \
           not self.private_key.strip().endswith("-----END PRIVATE KEY-----"):
            logger.warning("GA4私钥格式似乎不正确。请确保它包含完整的BEGIN/END标记并且换行符正确。")

        self.api_url = f"https://analyticsdata.googleapis.com/v1beta/properties/{self.property_id}:runReport"

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
            "scope": "https://www.googleapis.com/auth/analytics.readonly"
        }

        try:
            if not self.private_key or not self.client_email:
                logger.error("GA4客户端邮件或私钥未配置。")
                raise ValueError("GA4客户端邮件或私钥未配置。")
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
            logger.error(f"GA4 JWT无效密钥错误: {str(ike)} - 这通常意味着私钥格式无法被解析。请检查VITE_GA4_PRIVATE_KEY环境变量。确保BEGIN/END标记存在且换行符正确。")
            raise
        except Exception as e:
            logger.error(f"获取GA4访问令牌失败: {str(e)}")
            if "Could not deserialize key data" in str(e) or "parse" in str(e).lower():
                 logger.error("详细错误提示：GA4私钥解析失败。请检查VITE_GA4_PRIVATE_KEY环境变量中的私钥格式，确保BEGIN/END标记完整，并且换行符（\n）正确无误。不要使用字面上的\\n。")
            raise

    def run_ga_report(self, dimensions, metrics, date_ranges, order_bys=None, limit=10):
        """运行GA4报告"""
        try:
            token = self.get_access_token()
            report_config = {
                "dateRanges": [{
                    "startDate": date_ranges[0].start_date,
                    "endDate": date_ranges[0].end_date
                }],
                "dimensions": [{"name": dim} for dim in dimensions],
                "metrics": [{"name": met} for met in metrics],
                "limit": limit
            }
            
            if order_bys:
                report_config["orderBys"] = [
                    {
                        "metric": {"metricName": order_by.metric.metric_name},
                        "desc": order_by.desc
                    } for order_by in order_bys
                ]

            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=report_config
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GA4 API请求失败 ({', '.join(dimensions)} / {', '.join(metrics)}): {e}", exc_info=True)
            return None

def format_report_data_to_markdown_table(headers, rows_data, metric_formatters=None):
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

def get_ga4_summary(start_date_dt, end_date_dt):
    if not os.getenv("VITE_GA4_PROPERTY_ID") or not os.getenv("VITE_GA4_CLIENT_EMAIL") or not os.getenv("VITE_GA4_PRIVATE_KEY"):
        logger.warning("GA4环境变量未完全配置。")
        return "### GA4 数据 (警告)\n- 环境变量未完全配置\n"

    try:
        client = GA4Client()
        date_range = [DateRange(start_date=start_date_dt.strftime("%Y-%m-%d"), end_date=end_date_dt.strftime("%Y-%m-%d"))]
        
        markdown_output = [f"### GA4 数据 ({start_date_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')})\n"]

        # 1. 各流量渠道的：访客数，平均互动时长
        logger.info("获取GA4数据: 各流量渠道")
        traffic_channels_response = client.run_ga_report(
            dimensions=["sessionDefaultChannelGroup"],
            metrics=["sessions", "averageSessionDuration"],
            date_ranges=date_range,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            limit=100 
        )
        md_section = "#### 1. 各流量渠道 (前100)\n"
        if traffic_channels_response and "rows" in traffic_channels_response:
            headers = ["流量渠道", "会话数", "平均会话时长(秒)"]
            rows_data = []
            for row in traffic_channels_response["rows"]:
                rows_data.append({
                    "流量渠道": row["dimensionValues"][0]["value"],
                    "会话数": int(row["metricValues"][0]["value"]),
                    "平均会话时长(秒)": float(row["metricValues"][1]["value"])
                })
            md_section += format_report_data_to_markdown_table(
                headers, 
                rows_data,
                {"平均会话时长(秒)": lambda x: f"{x:.2f}"}
            )
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 新增：来源/媒介/活动分析（与前端保持一致，使用firstUserSource等维度）
        logger.info("获取GA4数据: 来源/媒介/活动（firstUserSource/firstUserMedium/firstUserCampaignName）")
        source_medium_campaign_response = client.run_ga_report(
            dimensions=["firstUserSource", "firstUserMedium", "firstUserCampaignName"],
            metrics=["sessions", "activeUsers", "bounceRate", "averageSessionDuration", "addToCarts", "checkouts"],
            date_ranges=date_range,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            limit=100
        )
        md_section = "#### 访问来源/媒介/活动分析 (前100)\n"
        if source_medium_campaign_response and "rows" in source_medium_campaign_response:
            headers = ["来源", "媒介", "活动", "会话数", "访客数", "跳出率(%)", "平均访问时长(秒)", "加购数", "发结数"]
            rows_data = []
            for row in source_medium_campaign_response["rows"]:
                rows_data.append({
                    "来源": row["dimensionValues"][0]["value"],
                    "媒介": row["dimensionValues"][1]["value"],
                    "活动": row["dimensionValues"][2]["value"],
                    "会话数": int(row["metricValues"][0]["value"]),
                    "访客数": int(row["metricValues"][1]["value"]),
                    "跳出率(%)": float(row["metricValues"][2]["value"]),
                    "平均访问时长(秒)": float(row["metricValues"][3]["value"]),
                    "加购数": int(row["metricValues"][4]["value"]),
                    "发结数": int(row["metricValues"][5]["value"])
                })
            md_section += format_report_data_to_markdown_table(
                headers,
                rows_data,
                {
                    "跳出率(%)": lambda x: f"{x:.2f}",
                    "平均访问时长(秒)": lambda x: f"{x:.2f}"
                }
            )
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 2. 各个页面的：停留时长，跳出率
        logger.info("获取GA4数据: 各个页面")
        page_metrics_response = client.run_ga_report(
            dimensions=["pagePath"],
            metrics=["screenPageViews", "averageSessionDuration", "engagementRate"],
            date_ranges=date_range,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
            limit=100
        )
        md_section = "#### 2. 各个页面 (按浏览量前100)\n"
        if page_metrics_response and "rows" in page_metrics_response:
            headers = ["页面路径", "浏览量", "平均会话时长(秒)", "跳出率(%)"]
            rows_data = []
            for row in page_metrics_response["rows"]:
                engagement_rate = float(row["metricValues"][2]["value"])
                bounce_rate = (1 - engagement_rate) * 100
                rows_data.append({
                    "页面路径": row["dimensionValues"][0]["value"],
                    "浏览量": int(row["metricValues"][0]["value"]),
                    "平均会话时长(秒)": float(row["metricValues"][1]["value"]),
                    "跳出率(%)": bounce_rate
                })
            md_section += format_report_data_to_markdown_table(
                headers, 
                rows_data,
                {"平均会话时长(秒)": lambda x: f"{x:.2f}", "跳出率(%)": lambda x: f"{x:.2f}"}
            )
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 3. 会话深度：跳出率，加购数，结账数
        logger.info("获取GA4数据: 总体跳出率、加购、结账")
        overall_conversion_metrics = client.run_ga_report(
            dimensions=[],
            metrics=["sessions", "engagedSessions", "addToCarts", "checkouts"],
            date_ranges=date_range
        )
        md_section = "#### 3. 整体站点表现 (会话相关)\n"
        if overall_conversion_metrics and "rows" in overall_conversion_metrics:
            row = overall_conversion_metrics["rows"][0]
            total_sessions = int(row["metricValues"][0]["value"])
            engaged_sessions = int(row["metricValues"][1]["value"])
            add_to_carts = int(row["metricValues"][2]["value"])
            checkouts = int(row["metricValues"][3]["value"])

            engagement_rate_overall = (engaged_sessions / total_sessions) if total_sessions > 0 else 0
            bounce_rate_overall = (1 - engagement_rate_overall) * 100
            
            md_section += f"    - **总跳出率**: {bounce_rate_overall:.2f}%\n"
            md_section += f"    - **总加购数 (事件: addToCarts)**: {add_to_carts}\n"
            md_section += f"    - **总结账/购买数 (事件: checkouts)**: {checkouts}\n"
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 4. 访问深度：访客数/访问量
        logger.info("获取GA4数据: 访问深度 (总用户与会话)")
        total_users_response = client.run_ga_report(
            dimensions=[],
            metrics=["activeUsers", "sessions"],
            date_ranges=date_range
        )
        md_section = "#### 4. 访问深度\n"
        if total_users_response and "rows" in total_users_response:
            row = total_users_response["rows"][0]
            total_active_users = int(row["metricValues"][0]["value"])
            total_sessions_for_depth = int(row["metricValues"][1]["value"])
            md_section += f"    - **总访客数 (活跃用户)**: {total_active_users}\n"
            md_section += f"    - **总访问量 (会话数)**: {total_sessions_for_depth}\n"
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        # 5. PC端移动端的：访客，跳出率，平均访问时长，加购数，结账数
        logger.info("获取GA4数据: PC与移动端对比")
        device_metrics_response = client.run_ga_report(
            dimensions=["deviceCategory"],
            metrics=["activeUsers", "sessions", "engagedSessions", "averageSessionDuration", "addToCarts", "checkouts"],
            date_ranges=date_range,
            limit=100
        )
        md_section = "#### 5. PC端 vs 移动端表现\n"
        if device_metrics_response and "rows" in device_metrics_response:
            headers = ["设备类型", "活跃用户", "跳出率(%)", "平均会话时长(秒)", "加购数", "结账数"]
            rows_data = []
            for row in device_metrics_response["rows"]:
                device_cat = row["dimensionValues"][0]["value"]
                active_users_dev = int(row["metricValues"][0]["value"])
                sessions_dev = int(row["metricValues"][1]["value"])
                engaged_sessions_dev = int(row["metricValues"][2]["value"])
                avg_session_duration_dev = float(row["metricValues"][3]["value"])
                add_to_carts_dev = int(row["metricValues"][4]["value"])
                checkouts_dev = int(row["metricValues"][5]["value"])

                engagement_rate_dev = (engaged_sessions_dev / sessions_dev) if sessions_dev > 0 else 0
                bounce_rate_dev = (1 - engagement_rate_dev) * 100
                
                rows_data.append({
                    "设备类型": device_cat,
                    "活跃用户": active_users_dev,
                    "跳出率(%)": bounce_rate_dev,
                    "平均会话时长(秒)": avg_session_duration_dev,
                    "加购数": add_to_carts_dev,
                    "结账数": checkouts_dev
                })
            md_section += format_report_data_to_markdown_table(
                headers, 
                rows_data,
                {"跳出率(%)": lambda x: f"{x:.2f}", "平均会话时长(秒)": lambda x: f"{x:.2f}"}
            )
        else:
            md_section += "    - 数据获取失败或无数据\n"
        markdown_output.append(md_section)

        return "\n".join(markdown_output)

    except Exception as e:
        logger.error(f"获取GA4详细数据时发生严重错误: {str(e)}", exc_info=True)
        return f"### GA4 数据 (严重错误)\n- 获取数据失败: {str(e)}\n"

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("开始GA4连接器独立测试...")
    
    if not os.getenv("VITE_GA4_PROPERTY_ID") or not os.getenv("VITE_GA4_PRIVATE_KEY"):
        print("请确保.env文件中已配置VITE_GA4_PROPERTY_ID, VITE_GA4_CLIENT_EMAIL, VITE_GA4_PRIVATE_KEY 等环境变量用于测试")
    else:
        today = datetime.now()
        seven_days_ago = today - timedelta(days=7)
        print("\n--- GA4 Report Start ---")
        summary = get_ga4_summary(seven_days_ago, today)
        print(summary)
        print("--- GA4 Report End ---\n")
        if "错误" in summary or "失败" in summary:
            print("测试运行中检测到错误或失败。请检查日志。")
        else:
            print("测试运行似乎已成功完成（未检测到明显错误文本）。") 