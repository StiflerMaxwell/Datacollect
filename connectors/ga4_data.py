import os
import json
import time
import jwt
import requests
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, Dimension, RunReportRequest
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
            # 可以选择在这里抛出异常或者允许继续尝试，取决于希望的健壮性
            # raise ValueError("无效的GA4私钥格式") 

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
            # 在这里也检查下原始异常类型，如果是关于密钥解析的，给出更具体的提示
            if "Could not deserialize key data" in str(e) or "parse" in str(e).lower():
                 logger.error("详细错误提示：GA4私钥解析失败。请检查VITE_GA4_PRIVATE_KEY环境变量中的私钥格式，确保BEGIN/END标记完整，并且换行符（\n）正确无误。不要使用字面上的\\n。")
            raise

    def run_report(self, report_config):
        """运行GA4报告"""
        try:
            token = self.get_access_token()
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
            logger.error(f"GA4 API请求失败: {str(e)}")
            raise

def get_ga4_summary(start_date_dt, end_date_dt):
    """
    获取GA4数据摘要
    
    Args:
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        
    Returns:
        str: 格式化的数据摘要
    """
    try:
        if not os.getenv("VITE_GA4_PROPERTY_ID") or not os.getenv("VITE_GA4_CLIENT_EMAIL") or not os.getenv("VITE_GA4_PRIVATE_KEY"):
            logger.warning("GA4环境变量未完全配置 (VITE_GA4_PROPERTY_ID, VITE_GA4_CLIENT_EMAIL, VITE_GA4_PRIVATE_KEY)。跳过GA4数据获取。")
            return "## GA4数据 (警告)\n- 环境变量未完全配置"
        
        client = GA4Client()
        
        # 构建报告请求
        report_config = {
            "dateRanges": [{
                "startDate": start_date_dt.strftime("%Y-%m-%d"),
                "endDate": end_date_dt.strftime("%Y-%m-%d")
            }],
            "metrics": [
                {"name": "activeUsers"},
                {"name": "screenPageViews"},
                {"name": "averageSessionDuration"},
                {"name": "bounceRate"}
            ],
            "dimensions": [
                {"name": "sessionSource"}
            ]
        }

        response = client.run_report(report_config)
        
        # 解析数据
        rows = response.get("rows", [])
        total_users = sum(int(row["metricValues"][0]["value"]) for row in rows)
        total_pageviews = sum(int(row["metricValues"][1]["value"]) for row in rows)
        avg_duration = sum(float(row["metricValues"][2]["value"]) for row in rows) / len(rows) if rows else 0
        avg_bounce_rate = sum(float(row["metricValues"][3]["value"]) for row in rows) / len(rows) if rows else 0

        # 获取主要流量来源
        top_sources = []
        for row in rows[:3]:
            source = row["dimensionValues"][0]["value"]
            users = int(row["metricValues"][0]["value"])
            top_sources.append(f"{source} ({users}用户)")
        top_sources_str = ", ".join(top_sources) if top_sources else "无数据"

        summary = f"""## GA4数据 ({start_date_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')})
总用户数: {total_users}
总页面浏览量: {total_pageviews}
平均会话时长: {avg_duration:.2f}秒
平均跳出率: {avg_bounce_rate:.2f}%
主要流量来源 (前3): {top_sources_str}
"""
        return summary
    except Exception as e:
        logger.error(f"获取GA4数据时出错: {str(e)}")
        return f"## GA4数据 (错误)\n- 获取数据失败: {str(e)}"

if __name__ == '__main__':
    # 测试代码
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    # 为测试添加一些日志级别设置
    logging.basicConfig(level=logging.DEBUG) 
    #确保环境变量已加载，用于独立测试
    if not os.getenv("VITE_GA4_PRIVATE_KEY"):
        print("请确保.env文件中已配置VITE_GA4_PRIVATE_KEY等环境变量用于测试")
    else:
        print(get_ga4_summary(seven_days_ago, today)) 