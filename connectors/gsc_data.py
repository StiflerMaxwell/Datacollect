import os
import json
import time
import jwt
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from urllib.parse import quote_plus # Import quote_plus for URL encoding

logger = logging.getLogger(__name__)

load_dotenv()

class GSCClient:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        site_url_from_env = os.getenv("VITE_GSC_SITE_URL")
        if not site_url_from_env:
            logger.error("VITE_GSC_SITE_URL 环境变量未设置。")
            # 可以选择抛出异常或设置一个无效的URL来使其在后续步骤中失败
            self.site_url_encoded = ""
        else:
            self.site_url_encoded = quote_plus(site_url_from_env) # URL encode the site URL
        
        self.client_email = os.getenv("VITE_GSC_CLIENT_EMAIL")
        raw_private_key = os.getenv("VITE_GSC_PRIVATE_KEY", "")
        
        logger.debug(f"GSC 原始私钥 (前50字符): {raw_private_key[:50]}")

        self.private_key = raw_private_key.replace("\\n", "\n")
        
        # 验证私钥格式
        if not self.private_key.strip().startswith("-----BEGIN PRIVATE KEY-----") or \
           not self.private_key.strip().endswith("-----END PRIVATE KEY-----"):
            logger.warning("GSC私钥格式似乎不正确。请确保它包含完整的BEGIN/END标记并且换行符正确。")
            # raise ValueError("无效的GSC私钥格式")

        # Construct the API URL with the encoded site URL
        self.api_url = f"https://www.googleapis.com/webmasters/v3/sites/{self.site_url_encoded}/searchAnalytics/query"
        logger.info(f"GSC API URL: {self.api_url}")

    def get_access_token(self):
        if self.access_token and self.token_expiry and time.time() < self.token_expiry:
            return self.access_token

        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT"}
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
            if not self.site_url_encoded: # Check if site_url_encoded is empty due to missing env var
                logger.error("GSC站点URL未配置或无效，无法获取访问令牌。")
                raise ValueError("GSC站点URL未配置或无效。")
                
            jwt_token = jwt.encode(payload, self.private_key, algorithm="RS256", headers=header)
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt_token}
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

    def query_search_analytics(self, start_date, end_date, dimensions=None):
        try:
            if not self.site_url_encoded: # Check if site_url_encoded is empty
                logger.error("GSC站点URL未配置或无效，无法查询搜索分析。")
                raise ValueError("GSC站点URL未配置或无效。")

            token = self.get_access_token()
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"startDate": start_date, "endDate": end_date, "dimensions": dimensions or ["query"], "rowLimit": 100}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GSC API请求失败: {str(e)}")
            raise

def get_gsc_summary(start_date_dt, end_date_dt):
    """
    获取GSC数据摘要
    """
    try:
        if not os.getenv("VITE_GSC_SITE_URL") or not os.getenv("VITE_GSC_CLIENT_EMAIL") or not os.getenv("VITE_GSC_PRIVATE_KEY"):
            logger.warning("GSC环境变量未完全配置 (VITE_GSC_SITE_URL, VITE_GSC_CLIENT_EMAIL, VITE_GSC_PRIVATE_KEY)。跳过GSC数据获取。")
            return "## GSC数据 (警告)\n- 环境变量未完全配置"

        client = GSCClient()
        if not client.site_url_encoded: # If site URL was not properly set up in constructor
             return "## GSC数据 (错误)\n- VITE_GSC_SITE_URL环境变量配置错误"

        query_data = client.query_search_analytics(start_date_dt.strftime("%Y-%m-%d"), end_date_dt.strftime("%Y-%m-%d"), ["query"])
        page_data = client.query_search_analytics(start_date_dt.strftime("%Y-%m-%d"), end_date_dt.strftime("%Y-%m-%d"), ["page"])
        
        query_rows = query_data.get("rows", [])
        page_rows = page_data.get("rows", [])
        
        total_clicks = sum(row.get("clicks", 0) for row in query_rows)
        total_impressions = sum(row.get("impressions", 0) for row in query_rows)
        avg_ctr = sum(row.get("ctr", 0) * row.get("impressions", 0) for row in query_rows) / total_impressions if total_impressions else 0
        avg_position = sum(row.get("position", 0) * row.get("impressions", 0) for row in query_rows) / total_impressions if total_impressions else 0

        top_queries = []
        for row in query_rows[:3]:
            query = row.get("keys", [""])[0]
            clicks = row.get("clicks", 0)
            top_queries.append(f"{query} ({clicks}点击)")
        top_queries_str = ", ".join(top_queries) if top_queries else "无数据"

        top_pages = []
        for row in page_rows[:3]:
            page = row.get("keys", [""])[0]
            clicks = row.get("clicks", 0)
            top_pages.append(f"{page} ({clicks}点击)")
        top_pages_str = ", ".join(top_pages) if top_pages else "无数据"

        summary = f"""## GSC数据 ({start_date_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')})
总点击量: {total_clicks}
总展示量: {total_impressions}
平均点击率: {avg_ctr*100:.2f}%
平均排名: {avg_position:.2f}
热门搜索词 (前3): {top_queries_str}
热门页面 (前3): {top_pages_str}
"""
        return summary
    except Exception as e:
        logger.error(f"获取GSC数据时出错: {str(e)}")
        return f"## GSC数据 (错误)\n- 获取数据失败: {str(e)}"

if __name__ == '__main__':
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    logging.basicConfig(level=logging.DEBUG) 
    from dotenv import load_dotenv # Add for standalone testing
    load_dotenv() 
    if not os.getenv("VITE_GSC_PRIVATE_KEY") or not os.getenv("VITE_GSC_SITE_URL"):
        print("请确保.env文件中已配置VITE_GSC_PRIVATE_KEY, VITE_GSC_SITE_URL等环境变量用于测试")
    else:
        print(get_gsc_summary(seven_days_ago, today)) 