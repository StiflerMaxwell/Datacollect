import os
import requests
import logging
from enum import Enum

# 配置日志记录器
logger = logging.getLogger(__name__)
# 清除已存在的处理器，以避免重复添加，特别是在被多次导入时
if logger.hasHandlers():
    logger.handlers.clear()

# 创建文件处理器，并设置编码为UTF-8
log_file_path = os.path.join(os.path.dirname(__file__), 'fastgpt_updater.log')
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# （可选）如果你也想在控制台看到这个模块的日志，并尝试处理编码
# stream_handler = logging.StreamHandler()
# try:
#     stream_handler.setFormatter(formatter)
#     # 尝试设置控制台编码，但这依赖于环境
#     if hasattr(stream_handler, 'stream') and hasattr(stream_handler.stream, 'reconfigure'):
# stream_handler.stream.reconfigure(encoding='utf-8') # Python 3.7+
# except Exception:
# pass # 忽略控制台编码设置失败的情况
# logger.addHandler(stream_handler)

logger.setLevel(logging.INFO) # 默认日志级别

class UpdateMode(Enum):
    INDEX = "index"         # 索引模式，增量更新，适用于大部分情况
    CHUNK = "chunk"         # 切片模式，适用于需要精确控制文本块的场景
    CUSTOM = "custom"       # 自定义模式，允许更灵活的数据结构，但通常更复杂

def update_fastgpt_kb_with_content(
    api_key: str,
    base_url: str,
    kb_id: str,
    file_name: str, # 用于FastGPT记录的文件名，不一定是实际本地文件名
    content: str,
    mode: str = UpdateMode.INDEX.value, # 默认为索引模式
    prompt: str = "", # 可选，某些模式下可能用到
    metadata: dict = None # 可选，元数据
):
    """
    使用提供的内容更新FastGPT知识库。

    Args:
        api_key (str): FastGPT API密钥。
        base_url (str): FastGPT实例的基础URL (例如: https://fastgpt.yourdomain.com)。
        kb_id (str): 要更新的知识库ID。
        file_name (str): 在FastGPT中显示的文件名。
        content (str): 要推送到知识库的文本内容。
        mode (str): 更新模式 ('index', 'chunk', 'custom')。
        prompt (str, optional): 提示信息，某些模式下使用。默认为 ""。
        metadata (dict, optional): 附加的元数据。默认为 None。

    Returns:
        bool: 更新是否成功。
    """
    if not all([api_key, base_url, kb_id, file_name, content]):
        logger.error("FastGPT更新参数不完整。")
        return False

    # 确保 base_url 不以 / 结尾
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    
    # 如果 base_url 包含了 /api，而目标端点也以 /api 开头，需要避免重复
    # 正确的API端点: /api/core/dataset/data/pushData
    target_api_path = "/api/core/dataset/data/pushData"
    
    if base_url.endswith('/api') and target_api_path.startswith('/api'):
        # base_url已经是 https://.../api，目标是 /api/core...
        # 我们需要移除 base_url 末尾的 /api，或者移除 target_api_path 开头的 /api
        # 为了统一，我们选择从 target_api_path 移除 /api，因为它更特定
        effective_api_path = target_api_path[len('/api'):] # -> /core/dataset/data/push
        api_url = f"{base_url}{effective_api_path}"
    elif not base_url.endswith('/api') and target_api_path.startswith('/api'):
        # base_url 是 https://... ，目标是 /api/core...
        # 这是最常见的情况，直接拼接
        api_url = f"{base_url}{target_api_path}"
    else:
        # 其他不常见情况，比如 base_url 已经是 https://.../api/core/dataset
        # 或者 base_url 是 https://.../v2/api 而 target_api_path 是 /core...
        # 这种情况下，直接拼接可能不正确，但作为基础尝试
        # 或者，如果用户提供的 base_url 就是完整的到 /api/core/dataset/data/push 的路径，
        # 并且 target_api_path 只是一个占位符或旧值，那么需要更复杂的逻辑。
        # 目前假设 target_api_path 是固定的，base_url 是可变的。
        # 一个更健壮的方式是解析URL，但这里我们先用字符串操作尝试覆盖主要场景。
        # 假设用户提供的 base_url 加上 target_api_path 构成完整路径
        # 如果 target_api_path 不以 / 开头，而 base_url 也不以 / 结尾，则加上
        if not target_api_path.startswith('/') and not base_url.endswith('/'):
            api_url = f"{base_url}/{target_api_path}"
        else:
            api_url = f"{base_url}{target_api_path}"
        logger.warning(f"FastGPT base_url 和 target_api_path 的组合可能不标准: base_url='{base_url}', target_api_path='{target_api_path}', 拼接结果='{api_url}'")


    # 根据不同的模式构建API URL和请求体
    # FastGPT 的 OpenAPI v1 文档中，推送数据的端点是 /api/openapi/v1/kb/pushData # 旧注释，保留参考
    # 更新：根据用户提供的文档 https://doc.tryfastgpt.ai/docs/development/openapi/dataset/
    # 正确的API端点是 /api/core/dataset/data/push
    # api_url = f"{base_url}/api/openapi/v1/kb/pushData" # 旧代码，已替换

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 读取 collectionId
    collection_id = os.getenv("FASTGPT_COLLECTION_ID")
    if not collection_id:
        logger.error("未检测到环境变量 FASTGPT_COLLECTION_ID")
        return False

    # Payload for POST /api/core/dataset/data/push
    # kb_id from args maps to datasetId
    # file_name from args maps to sourceName
    data_payload = {
        "collectionId": collection_id,
        "trainingType": "chunk",
        "data": [
            {
                "q": content,
                "a": "",  # Auxiliary content, can be empty
                "sourceName": file_name, # Name of the source file
            }
        ],
        # "mode": mode, 
        # prompt is optional for this endpoint based on docs, 
        # but including it if provided, FastGPT might ignore if not applicable
        "prompt": prompt 
    }
    
    # The 'prompt' field was part of the old API structure /api/openapi/v1/kb/pushData.
    # For /api/core/dataset/data/push, the documentation shows 'prompt' as an optional top-level field.
    # 'metadata' is not explicitly listed as a top-level field for /api/core/dataset/data/push.
    # If metadata is needed, it might go inside each data object or be handled differently.
    # For now, keeping it simple based on primary fields.

    # logger.info(f"向FastGPT推送数据: URL={api_url}, KB_ID={kb_id}, 文件名={file_name}, 模式={mode}")
    # Corrected log to reflect datasetId
    logger.info(f"向FastGPT推送数据: URL={api_url}, Dataset_ID={kb_id}, 文件名={file_name}, 模式={mode}")
    logger.debug(f"FastGPT请求体 (部分内容): {{datasetId: '{kb_id}', data: [{{q: '{content[:100]}...'}}], mode: '{mode}'}}") # Corrected log key

    try:
        response = requests.post(api_url, headers=headers, json=data_payload, timeout=60) # Using data_payload
        response.raise_for_status()  # 如果HTTP状态码是4xx或5xx，则抛出异常
        
        response_data = response.json()
        logger.info(f"FastGPT API响应: {response_data}")
        
        # 检查响应中是否有指示成功的字段，例如 id 或其他特定于API的成功代码
        # FastGPT pushData API成功时通常会返回插入/更新的数据条数或ID
        # 例如：{"code":200,"message":"请求成功","data":{"insertLen":1,"updateLen":0,"invalidLen":0}}
        if response_data.get("code") == 200 and isinstance(response_data.get("data"), dict):
            push_result = response_data["data"]
            # 新的API响应格式可能不同，例如:
            # {"code":200,"message":"ok","data":{"id":"xxxxxxxx","status":"parsing","sourceId":"xxxx"}}
            # 或者 {"code":200,"message":"ok","data":{"message":"xxxxx","dataId":"xxxxx"}}
            # 或者成功时直接是 {"code":200,"message":"ok","data": "xxxxx"} (data是字符串ID)
            # 或者 {"code":200, "message":"ok", "data": {"id": "...", "status": "parsing"}}

            # 通用成功判断：code == 200 并且 data 字段存在且不为空
            if response_data.get("data"): # 只要data字段存在且非空，就认为API调用是成功的
                insert_len = push_result.get('insertLen', 0) if isinstance(push_result, dict) else 0
                update_len = push_result.get('updateLen', 0) if isinstance(push_result, dict) else 0
                invalid_len = push_result.get('invalidLen', 0) if isinstance(push_result, dict) else 0
                data_id = push_result.get('id') if isinstance(push_result, dict) else (push_result if isinstance(push_result, str) else None)

                if data_id:
                     logger.info(f"FastGPT数据推送成功，数据ID: {data_id}, 状态: {push_result.get('status', '未知') if isinstance(push_result, dict) else '未知'}")
                     return True
                elif insert_len > 0 or update_len > 0:
                    logger.info(f"FastGPT数据推送结果: 插入 {insert_len}, 更新 {update_len}, 无效 {invalid_len}")
                    if invalid_len > 0:
                         logger.warning(f"FastGPT推送时存在无效数据，无效条数: {invalid_len}")
                    return True
                elif insert_len == 0 and update_len == 0 and invalid_len == 0 and not data_id:
                     logger.info("FastGPT 推送了0条有效数据或未返回明确的数据ID，但API调用成功。可能是重复或空内容，或API版本差异。")
                     return True # 行为上没有出错，但可能需要关注具体响应
                else:
                    logger.error(f"FastGPT推送数据后未识别到成功标志，响应: {response_data}")
                    return False
            else: # data 字段为空或不存在
                logger.error(f"FastGPT API返回成功代码，但 'data' 字段为空或不存在。响应: {response_data}")
                return False
        else:
            logger.error(f"FastGPT API未返回成功的响应代码或数据结构。响应: {response_data}")
            return False
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"FastGPT API请求失败: HTTP {e.response.status_code}")
        # 记录更详细的响应内容，帮助调试404等问题
        response_text = ""
        try:
            response_text = e.response.text
        except Exception:
            response_text = "无法获取响应文本"
        logger.error(f"响应内容: {response_text[:1000]}") # 限制长度避免日志过大
        return False
    except Exception as e:
        logger.error(f"更新FastGPT知识库时发生未知错误: {str(e)}", exc_info=True)
        return False

if __name__ == '__main__':
    # 测试代码 (需要配置相关的环境变量)
    logger.info("测试FastGPT更新模块...")
    API_KEY = "fastgpt-x79YmADkoOOc8QoZ2rCfT5o2R0gsGDYvgm1vXVZ4slNrIiUiS8D9DXbTf"
    BASE_URL = "https://fastgpt.vertu.cn"
    KB_ID = "682c8b22a3d78b91b9bdc6ec"

    if not all([API_KEY, BASE_URL, KB_ID]):
        logger.error("测试FastGPT更新需要环境变量: FASTGPT_API_KEY, FASTGPT_BASE_URL, FASTGPT_KB_ID")
    else:
        logger.debug(f"使用配置: BASE_URL={BASE_URL}, KB_ID={KB_ID[:10]}...")
        test_content = "这是一个测试内容，用于验证FastGPT知识库更新功能。\n第二行测试内容。"
        test_file_name = "test_document.txt"
        
        success = update_fastgpt_kb_with_content(
            api_key=API_KEY,
            base_url=BASE_URL,
            kb_id=KB_ID,
            file_name=test_file_name,
            content=test_content,
            mode=UpdateMode.INDEX.value
        )
        
        if success:
            logger.info("FastGPT测试更新成功！")
        else:
            logger.error("FastGPT测试更新失败。") 