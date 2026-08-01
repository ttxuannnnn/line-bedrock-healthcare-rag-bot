# line-bedrock-healthcare-rag-bot
# 🏥 智慧長照 / 醫療器材 AI 諮詢與自動化知識庫系統

基於 **AWS Bedrock Managed Knowledge Base** 與 **LINE Messaging API** 的 Serverless 多模態 RAG（檢索增強生成）機器人。

## 🌟 核心功能
1. **多模態視覺辨識 (Multimodal Vision)：** 支援在 LINE 上傳醫療器材圖片，透過 Amazon Nova Pro / Claude 3.5 辨識器材類型與操作說明。
2. **自動化知識庫上傳與同步 (Auto Ingestion)：** 在 LINE 聊天室直接上傳 PDF/文件，系統自動寫入 AWS S3 並觸發 Bedrock Ingestion Job 進行即時向量索引。
3. **無幻覺專業問答 (Accurate RAG)：** 結合 Bedrock 檢索，精準回答長照與醫療器材規範，自動過濾日常打招呼等雜訊。

## 🏗️ 系統架構
`LINE Messaging API` ➔ `AWS Lambda (Function URL)` ➔ `AWS S3 / Bedrock Agent Runtime` ➔ `Amazon Nova Pro / Claude 3.5`

## 🛠️ 技術棧
- **Cloud Provider:** AWS (Lambda, S3, Bedrock KB, IAM)
- **AI Models:** Amazon Nova Pro / Claude 3.5 Sonnet
- **Backend Language:** Python 3.12 (Boto3)
- **Frontend Integration:** LINE Messaging API (Webhook)

## 🚀 部署步驟
1. 建立 AWS S3 Bucket 與 Bedrock Knowledge Base。
2. 部署 AWS Lambda Function，並綁定環境變數：
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `KNOWLEDGE_BASE_ID`
   - `DATA_SOURCE_ID`
   - `S3_BUCKET_NAME`
3. 配置 IAM Role 權限 (`bedrock:Retrieve`, `bedrock:StartIngestionJob`, `s3:PutObject`)。
4. 設定 LINE Developer Console 的 Webhook URL 指向 Lambda Function URL。
