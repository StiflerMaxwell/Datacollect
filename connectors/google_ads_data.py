import os
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def get_google_ads_summary(start_date_dt, end_date_dt, customer_id):
    """
    获取Google广告数据摘要
    
    Args:
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        customer_id (str): Google Ads客户ID
        
    Returns:
        str: 格式化的数据摘要
    """
    try:
        client = GoogleAdsClient.load_from_storage(version="v16")
    except Exception as e:
        return f"## Google Ads数据 (错误)\n- 加载配置失败: {str(e)}. 请确保google-ads.yaml配置正确或环境变量已设置。"

    ga_service = client.get_service("GoogleAdsService")

    start_date_str = start_date_dt.strftime('%Y-%m-%d')
    end_date_str = end_date_dt.strftime('%Y-%m-%d')

    query = f"""
        SELECT
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            metrics.all_conversions_value
        FROM
            customer_client
        WHERE
            segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
    """

    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        
        total_cost = 0
        total_impressions = 0
        total_clicks = 0
        total_ctr_weighted_sum = 0
        total_cpc_weighted_sum = 0
        total_conversions = 0
        total_conversion_value = 0

        for batch in stream:
            for row in batch.results:
                metrics = row.metrics
                cost = metrics.cost_micros / 1_000_000
                impressions = metrics.impressions
                clicks = metrics.clicks
                
                total_cost += cost
                total_impressions += impressions
                total_clicks += clicks
                total_ctr_weighted_sum += metrics.ctr * impressions
                total_cpc_weighted_sum += metrics.average_cpc / 1_000_000 * clicks
                total_conversions += metrics.conversions
                total_conversion_value += metrics.conversions_value
        
        avg_ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0
        avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
        roas = (total_conversion_value / total_cost) if total_cost > 0 else 0
        cpa = (total_cost / total_conversions) if total_conversions > 0 else 0

        summary = f"""## Google广告数据 ({start_date_str} to {end_date_str})
总花费: ${total_cost:,.2f}
展示次数: {total_impressions:,}
点击次数: {total_clicks:,}
平均点击率 (CTR): {avg_ctr:.2%}
平均每次点击费用 (CPC): ${avg_cpc:,.2f}
转化次数: {total_conversions:,.2f}
每次转化费用 (CPA): ${cpa:,.2f}
广告支出回报率 (ROAS): {roas:.2f}
"""
        return summary
    except GoogleAdsException as ex:
        error_details = ""
        for error in ex.failure.errors:
            error_details += f"\tMessage: {error.message}\n"
            if error.location:
                for field_path_element in error.location.field_path_elements:
                    error_details += f"\t\tOn field: {field_path_element.field_name}\n"
        return f"## Google广告数据 (错误)\n- API请求失败:\n{error_details}"
    except Exception as e:
        return f"## Google广告数据 (错误)\n- 获取数据失败: {str(e)}"

if __name__ == '__main__':
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    gg_ads_customer_id = os.getenv("GOOGLE_ADS_LINKED_CUSTOMER_ID")
    if not gg_ads_customer_id:
        print("请在.env文件中设置GOOGLE_ADS_LINKED_CUSTOMER_ID")
    else:
        print(get_google_ads_summary(seven_days_ago, today, gg_ads_customer_id)) 