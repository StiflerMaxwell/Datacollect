import os
from mailchimp_marketing import Client
from mailchimp_marketing.api_client import ApiClientError
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def get_mailchimp_summary(start_date_dt, end_date_dt):
    """
    获取Mailchimp营销活动数据摘要
    
    Args:
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        
    Returns:
        str: 格式化的数据摘要
    """
    try:
        client = Client()
        client.set_config({
            "api_key": os.getenv("MAILCHIMP_API_KEY"),
            "server": os.getenv("MAILCHIMP_SERVER_PREFIX")
        })

        # 获取最近的营销活动
        campaigns_response = client.campaigns.list(
            count=5,
            sort_field="send_time",
            sort_dir="DESC",
            status="sent"
        )
        
        campaign_summaries = []
        if campaigns_response['campaigns']:
            for campaign in campaigns_response['campaigns']:
                if 'report_summary' in campaign and campaign['report_summary']:
                    report = campaign['report_summary']
                    campaign_title = campaign['settings']['title']
                    send_time = campaign.get('send_time', 'N/A')
                    opens = report.get('opens', 0)
                    unique_opens = report.get('unique_opens', 0)
                    open_rate = report.get('open_rate', 0) * 100
                    clicks = report.get('clicks', 0)
                    subscriber_clicks = report.get('subscriber_clicks', 0)
                    click_rate = report.get('click_rate', 0) * 100
                    
                    campaign_summaries.append(
                        f"  - 活动: '{campaign_title}' (发送于 {send_time})\n"
                        f"    - 打开数/独立打开数: {opens}/{unique_opens} (打开率: {open_rate:.2f}%)\n"
                        f"    - 点击数/独立点击用户数: {clicks}/{subscriber_clicks} (点击率: {click_rate:.2f}%)"
                    )
        
        if not campaign_summaries:
            return f"## Mailchimp数据 (最近营销活动)\n- 未找到最近的营销活动报告。"

        summary = f"## Mailchimp数据 (最近营销活动总结)\n" + "\n".join(campaign_summaries)
        return summary

    except ApiClientError as error:
        return f"## Mailchimp数据 (错误)\n- API错误: {error.text}"
    except Exception as e:
        return f"## Mailchimp数据 (错误)\n- 处理数据失败: {str(e)}"

if __name__ == '__main__':
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)
    print(get_mailchimp_summary(thirty_days_ago, today)) 