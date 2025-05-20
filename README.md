# 项目名称：DataCollect & FastGPT Uploader

## 1. 项目概览

本项目是一个Python自动化脚本，旨在从多个数据源（包括WooCommerce, Google Analytics 4, Google Search Console）收集数据，将收集到的数据整合成结构化的文本报告，并将这些报告自动上传到FastGPT知识库。

## 2. 功能特性

- **多数据源集成**：
    - 从WooCommerce API获取订单数据。
    - 从Google Analytics 4 (GA4) API获取网站分析数据。
    - 从Google Search Console (GSC) API获取搜索性能数据。
- **数据整合与报告生成**：
    - 将来自不同来源的数据汇总。
    - 生成包含关键指标和信息的文本报告。
    - 报告以日期时间戳命名，存储在 `data_exports` 目录中。
- **自动化上传**：
    - 将生成的报告自动推送到指定的FastGPT知识库。
- **配置灵活**：
    - 通过 `.env` 文件管理所有API密钥、URL和配置参数，确保敏感信息安全。
- **日志记录**：
    - 为每个模块和主脚本记录详细的操作日志，包括错误信息，方便追踪和调试。
    - 日志文件存储在 `logs` 目录和各连接器子目录中，使用UTF-8编码。
- **模块化设计**：
    - `connectors` 目录包含各个数据源的连接和数据提取逻辑。
    - `fastgpt_updater.py` 负责与FastGPT API交互。
    - `main_collector.py` 作为主执行脚本，协调整个流程。

## 3. 目录结构

```
DataCollect/
│
├── connectors/                 # 数据源连接器模块
│   ├── __init__.py
│   ├── ga4_data.py             # Google Analytics 4 数据收集
│   ├── ga4_data.log
│   ├── gsc_data.py             # Google Search Console 数据收集
│   ├── gsc_data.log
│   └── woo_data.py             # WooCommerce 数据收集
│   └── woo_data.log
│
├── data_exports/               # 存放生成的报告文件
│   └── report_YYYY-MM-DD_HH-MM-SS.txt (示例)
│
├── logs/                       # 主脚本和通用日志
│   └── main_collector.log
│   └── fastgpt_updater.log
│
├── .env                        # 环境变量配置文件 (重要：不应提交到Git仓库)
├── .gitignore                  # Git忽略文件配置
├── main_collector.py           # 主数据收集和上传脚本
├── fastgpt_updater.py          # FastGPT知识库更新模块
├── requirements.txt            # Python依赖包列表
└── README.md                   # 项目说明文件
```

## 4. 环境配置

### 4.1. Python环境
确保您已安装Python 3.7或更高版本。

### 4.2. 安装依赖库
在项目根目录下，通过以下命令安装所需的Python库：
```bash
pip install -r requirements.txt
```
`requirements.txt` 文件内容如下：
```
python-dotenv
requests
PyJWT
google-analytics-data
google-auth
google-auth-oauthlib
google-api-python-client
woocommerce
cryptography
```

### 4.3. 配置环境变量 (`.env` 文件)
在项目根目录下创建一个名为 `.env` 的文件。此文件用于存储API密钥和配置信息，**请勿将此文件提交到版本控制系统（如Git）**。

`.env` 文件示例内容：

```env
# WooCommerce API 配置
VITE_WOO_API_URL="https://yourdomain.com/" # 您的WordPress/WooCommerce站点基础URL
VITE_WOO_CONSUMER_KEY="ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
VITE_WOO_CONSUMER_SECRET="cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Google Cloud Service Account (用于 GA4 和 GSC)
## 服务账户JSON密钥文件中的相关信息
VITE_GA4_PROPERTY_ID="ga:xxxxxxxx"
VITE_GA4_CLIENT_EMAIL="your-service-account-email@your-project.iam.gserviceaccount.com"
VITE_GA4_PRIVATE_KEY_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# 将JSON密钥文件中的 private_key 内容（包括 "-----BEGIN PRIVATE KEY-----" 和 "-----END PRIVATE KEY-----"）
# 复制到这里，并将所有换行符替换为 "\n" (双反斜杠n)
VITE_GA4_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_CONTENT_HERE\n-----END PRIVATE KEY-----\n"

VITE_GSC_CLIENT_EMAIL="your-service-account-email@your-project.iam.gserviceaccount.com"
VITE_GSC_PRIVATE_KEY_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# 同上，将GSC服务账户的 private_key 内容（包含头尾）复制并替换换行符
VITE_GSC_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_GSC_PRIVATE_KEY_CONTENT_HERE\n-----END PRIVATE KEY-----\n"
VITE_GSC_SITE_URL="sc-domain:yourdomain.com" # 或者 "https://yourdomain.com/"，根据GSC API要求

# FastGPT 配置
FASTGPT_API_KEY="fk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FASTGPT_BASE_URL="https://your-fastgpt-domain.com/api" # FastGPT API的基础URL，通常包含 /api
FASTGPT_KB_ID="xxxxxxxxxxxxxxxxxxxx" # 要更新的FastGPT知识库ID

# 数据收集日期范围 (可选, 默认最近7天)
# START_DATE="YYYY-MM-DD"
# END_DATE="YYYY-MM-DD"

# WooCommerce 订单状态 (可选, 默认 processing,completed)
# WOO_ORDER_STATUSES="processing,completed,on-hold"
```

**重要提示关于私钥格式：**
在 `.env` 文件中，`VITE_GA4_PRIVATE_KEY` 和 `VITE_GSC_PRIVATE_KEY` 必须是包含 `-----BEGIN PRIVATE KEY-----` 和 `-----END PRIVATE KEY-----` 的完整密钥，并且其中所有的实际换行符需要被替换为字符串 `\n`。

例如，如果原始私钥部分是：
```
-----BEGIN PRIVATE KEY-----
ABCDE
FGHIJ
-----END PRIVATE KEY-----
```
在 `.env` 文件中应写为：
`VITE_GA4_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nABCDE\nFGHIJ\n-----END PRIVATE KEY-----\n"`

## 5. 如何运行脚本

配置好 `.env` 文件并安装完依赖后，可以直接运行主脚本：
```bash
python main_collector.py
```
脚本将执行以下操作：
1. 加载 `.env` 文件中的环境变量。
2. 连接到WooCommerce, GA4, 和 GSC，获取指定日期范围内的数据。
3. 将收集到的数据整合成一份文本报告，保存在 `data_exports` 目录。
4. 将生成的报告上传到配置的FastGPT知识库。
5. 操作过程和结果将记录在相应的日志文件中。

## 6. 日志文件

- `logs/main_collector.log`: 记录主脚本的运行情况和整体流程。
- `logs/fastgpt_updater.log`: 记录与FastGPT API交互的日志。
- `connectors/woo_data.log`: WooCommerce数据收集日志。
- `connectors/ga4_data.log`: GA4数据收集日志。
- `connectors/gsc_data.log`: GSC数据收集日志。

所有日志文件均使用UTF-8编码。

## 7. 注意事项

- **API配额**：请注意各平台API的使用频率限制和配额，避免请求过于频繁导致临时封禁。
- **私钥安全**：确保包含私钥的 `.env` 文件和服务账户JSON文件得到妥善保管，不要泄露或提交到公共代码库。`.gitignore` 文件已配置忽略 `.env`。
- **FastGPT端点**：脚本目前使用的FastGPT数据推送端点是 `/api/core/dataset/data/push`。如果您的FastGPT版本或配置不同，可能需要调整 `fastgpt_updater.py` 中的API路径和payload。
- **错误处理**：脚本包含基本的错误处理和日志记录。如果遇到问题，请首先检查日志文件获取详细错误信息。
- **数据准确性**：报告中数据的准确性依赖于各API返回的数据。

---
该README提供了项目的基本信息和使用指南。您可以根据实际情况进一步完善。 