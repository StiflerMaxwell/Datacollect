import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_semrush_summary():
    """
    获取Semrush数据摘要
    
    Returns:
        str: 格式化的数据摘要
    """
    api_key = os.getenv("SEMRUSH_API_KEY")
    domain = "vertu.com"

    try:
        # 域名排名数据
        params_rank = {
            'type': 'domain_rank',
            'key': api_key,
            'export_columns': 'Dn,Rk,Or,Ot,Oc,Ad,At,Ac',
            'domain': domain,
            'database': 'us'
        }
        response_rank = requests.get("https://api.semrush.com/", params=params_rank)
        response_rank.raise_for_status()
        data_rank = response_rank.text.split('\n')[1].split(';')

        organic_keywords = data_rank[2]
        organic_traffic = data_rank[3]
        adwords_keywords = data_rank[5]
        adwords_traffic = data_rank[6]

        # 获取反向链接数据
        params_backlinks = {
            'type': 'backlinks_overview',
            'key': api_key,
            'target': domain,
            'target_type': 'root_domain'
        }
        response_backlinks = requests.get("https://api.semrush.com/", params=params_backlinks)
        response_backlinks.raise_for_status()
        data_backlinks = response_backlinks.text.split('\n')[1].split(';')
        total_backlinks = data_backlinks[0]

        summary = f"""## Semrush数据 (截至 {datetime.now().strftime('%Y-%m-%d')})
自然搜索关键词数: {organic_keywords}
估算自然搜索月流量: {organic_traffic}
付费关键词数: {adwords_keywords}
估算付费月流量: {adwords_traffic}
总反向链接数: {total_backlinks}
"""
        return summary
    except requests.exceptions.RequestException as e:
        return f"## Semrush数据 (错误)\n- API请求失败: {str(e)}"
    except Exception as e:
        return f"## Semrush数据 (错误)\n- 处理数据失败: {str(e)}"

if __name__ == '__main__':
    print(get_semrush_summary()) 