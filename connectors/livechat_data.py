import pandas as pd
from datetime import datetime, timedelta
import os

def get_livechat_summary(csv_filepath, start_date_dt, end_date_dt):
    """
    从CSV文件中获取Livechat数据摘要
    
    Args:
        csv_filepath (str): Livechat数据CSV文件的路径
        start_date_dt (datetime): 开始日期
        end_date_dt (datetime): 结束日期
        
    Returns:
        str: 格式化的数据摘要
    """
    try:
        df = pd.read_csv(csv_filepath)
        # 确保日期列是datetime类型
        df['chat_date'] = pd.to_datetime(df['chat_date'])
        
        # 筛选日期范围
        mask = (df['chat_date'] >= start_date_dt) & (df['chat_date'] <= end_date_dt)
        df_period = df.loc[mask]

        if df_period.empty:
            return f"## Livechat数据 ({start_date_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')})\n- 周期内无Livechat数据。"

        total_chats = len(df_period)
        avg_satisfaction = df_period['satisfaction_score'].mean() if 'satisfaction_score' in df_period.columns else "N/A"
        
        # 常见问题标签统计
        if 'tags' in df_period.columns and not df_period['tags'].dropna().empty:
            all_tags = []
            for tags_str in df_period['tags'].dropna():
                all_tags.extend([tag.strip() for tag in str(tags_str).split(',')])
            tag_counts = pd.Series(all_tags).value_counts().nlargest(3).to_dict()
            top_tags_str = ", ".join([f"{tag} ({count}次)" for tag, count in tag_counts.items()])
        else:
            top_tags_str = "无标签数据"
        
        avg_duration = df_period['duration_seconds'].mean() if 'duration_seconds' in df_period.columns else "N/A"

        summary = f"""## Livechat数据 ({start_date_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')})
总聊天数: {total_chats}
平均客户满意度: {avg_satisfaction:.2f}/5 (如果适用)
平均聊天时长: {avg_duration:.0f} 秒 (如果适用)
常见问题标签 (前3): [{top_tags_str}]
"""
        return summary
    except FileNotFoundError:
        return f"## Livechat数据 (错误)\n- 未找到CSV文件: {csv_filepath}"
    except Exception as e:
        return f"## Livechat数据 (错误)\n- 处理CSV失败: {str(e)}"

if __name__ == '__main__':
    # 创建一个示例CSV文件来测试
    sample_data = {
        'chat_date': [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(10)],
        'satisfaction_score': [5,4,5,3,5,4,5,2,4,5],
        'tags': ['物流查询,发票','产品咨询','售后服务,物流查询','产品功能','支付问题','物流查询','产品咨询','售后服务','产品功能','退货'],
        'duration_seconds': [120,300,180,240,60,90,150,400,200,100]
    }
    sample_csv_path = "sample_livechat_data.csv"
    pd.DataFrame(sample_data).to_csv(sample_csv_path, index=False)
    
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    print(get_livechat_summary(sample_csv_path, seven_days_ago, today)) 