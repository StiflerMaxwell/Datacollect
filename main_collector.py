import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from connectors.woo_data import get_woo_summary
from connectors.ga4_data import get_ga4_summary
from connectors.gsc_data import get_gsc_summary
from fastgpt_updater import update_fastgpt_kb_with_content

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

def main():
    try:
        # 加载环境变量
        load_dotenv()
        logger.info("环境变量加载完成")

        # 设置日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        logger.info(f"数据收集时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

        # 获取各平台数据
        woo_summary = get_woo_summary(start_date, end_date)
        ga4_summary = get_ga4_summary(start_date, end_date)
        gsc_summary = get_gsc_summary(start_date, end_date)

        # 生成报告
        report_content = f"""# Vertu.com 运营数据报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
数据周期: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}

{woo_summary}

{ga4_summary}

{gsc_summary}
"""

        # 保存报告
        os.makedirs('data_exports', exist_ok=True)
        report_filename = f'report_{datetime.now().strftime("%Y%m%d%H%M%S")}.txt'
        report_file_path = os.path.join('data_exports', report_filename)
        with open(report_file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        logger.info(f"报告已保存到: {report_file_path}")

        # 更新FastGPT知识库
        fastgpt_api_key = os.getenv("FASTGPT_API_KEY")
        fastgpt_kb_id = os.getenv("FASTGPT_KB_ID")
        fastgpt_base_url = os.getenv("FASTGPT_BASE_URL")

        if all([fastgpt_api_key, fastgpt_kb_id, fastgpt_base_url, report_content]):
            logger.info(f"准备更新FastGPT知识库 {fastgpt_kb_id}...")
            success = update_fastgpt_kb_with_content(
                api_key=fastgpt_api_key,
                base_url=fastgpt_base_url,
                kb_id=fastgpt_kb_id,
                file_name=report_filename,
                content=report_content,
                mode="index"
            )
            if success:
                logger.info("FastGPT知识库更新成功！")
            else:
                logger.error("FastGPT知识库更新失败。请检查日志。")
        else:
            logger.warning("FastGPT配置不完整或报告内容为空，跳过知识库更新。请检查.env文件中的FASTGPT_API_KEY, FASTGPT_KB_ID, FASTGPT_BASE_URL以及报告生成过程。")

    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 