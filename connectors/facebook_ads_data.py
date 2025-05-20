import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def get_facebook_ads_summary(start_date_dt, end_date_dt):
    """
    获取Facebook广告数据摘要
    
    Args:
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        
    Returns:
        str: 格式化的数据摘要
    """
    try:
        app_id = os.getenv("FB_APP_ID")
        app_secret = os.getenv("FB_APP_SECRET")
        access_token = os.getenv("FB_ACCESS_TOKEN")
        ad_account_id = os.getenv("FB_AD_ACCOUNT_ID")

        FacebookAdsApi.init(app_id, app_secret, access_token)
        account = AdAccount(f'act_{ad_account_id.replace("act_", "")}')

        start_date_str = start_date_dt.strftime('%Y-%m-%d')
        end_date_str = end_date_dt.strftime('%Y-%m-%d')

        params = {
            'level': AdsInsights.Level.account,
            'time_range': {'since': start_date_str, 'until': end_date_str},
        }
        fields = [
            AdsInsights.Field.spend,
            AdsInsights.Field.impressions,
            AdsInsights.Field.clicks,
            AdsInsights.Field.ctr,
            AdsInsights.Field.cpc,
            AdsInsights.Field.roas,
        ]
        
        insights = account.get_insights(params=params, fields=fields)
        
        if not insights:
            return f"## Facebook广告数据 ({start_date_str} to {end_date_str})\n- 周期内无广告数据。"

        insight = insights[0]
        spend = insight.get(AdsInsights.Field.spend, 0)
        impressions = insight.get(AdsInsights.Field.impressions, 0)
        clicks = insight.get(AdsInsights.Field.clicks, 0)
        ctr = insight.get(AdsInsights.Field.ctr, 0)
        cpc = insight.get(AdsInsights.Field.cpc, 0)
        
        roas_from_api = 0
        if AdsInsights.Field.roas in insight:
            for r_item in insight[AdsInsights.Field.roas]:
                if r_item.get('action_type') == 'offsite_conversion.fb_pixel_purchase':
                    roas_from_api = float(r_item.get('value',0))
                    break
                elif r_item.get('action_type') == 'omni_purchase':
                    roas_from_api = float(r_item.get('value',0))
                    break

        summary = f"""## Facebook广告数据 ({start_date_str} to {end_date_str})
总花费: ${float(spend):,.2f}
展示次数: {int(impressions):,}
点击次数: {int(clicks):,}
点击率 (CTR): {float(ctr):.2f}%
平均每次点击费用 (CPC): ${float(cpc):,.2f}
广告支出回报率 (ROAS): {roas_from_api:.2f} (基于像素购买数据)
"""
        return summary
    except Exception as e:
        return f"## Facebook广告数据 (错误)\n- 获取数据失败: {str(e)}"

if __name__ == '__main__':
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    print(get_facebook_ads_summary(seven_days_ago, today)) 