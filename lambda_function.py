import json
import os
import urllib.request
import base64
import boto3

AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')

# 優先讀取環境變數，若無則使用預設設定值
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '7TNGBW60WR')
DATA_SOURCE_ID = os.environ.get('DATA_SOURCE_ID', '1SSDFD75H7') 
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'long-term-care-manuals') 

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=AWS_REGION)
bedrock_agent = boto3.client('bedrock-agent', region_name=AWS_REGION)
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)

USER_IMAGE_CACHE = {}

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        events = body.get('events', [])
        
        if not events:
            return {'statusCode': 200, 'body': 'OK'}
        
        for line_event in events:
            user_id = line_event.get('source', {}).get('userId', 'default_user')
            msg_type = line_event.get('message', {}).get('type')
            reply_token = line_event.get('replyToken')
            message_id = line_event.get('message', {}).get('id')
            
            # 【情況 1】：收到檔案
            if msg_type == 'file':
                file_name = line_event.get('message', {}).get('fileName', f"{message_id}.pdf")
                
                # 1. 下載 LINE 檔案
                file_bytes = download_line_content(message_id)
                if not file_bytes:
                    reply_to_line(reply_token, "❌ 步驟 1 失敗：無法從 LINE 下載檔案內容。")
                    continue

                # 2. 上傳至 S3 clean-md/
                s3_key = f"clean-md/{file_name}"
                try:
                    s3_client.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=s3_key,
                        Body=file_bytes
                    )
                except Exception as s3_err:
                    reply_to_line(reply_token, f"❌ 步驟 2 失敗（S3 權限或桶名錯誤）：\n{str(s3_err)}")
                    continue
                
                # 3. 觸發 Bedrock 知識庫自動同步
                sync_msg = trigger_bedrock_sync()
                
                reply_to_line(reply_token, f"✅ 檔案「{file_name}」已成功上傳至資料庫！\n\n{sync_msg}")

            # 【情況 2】：收到圖片
            elif msg_type == 'image':
                img_bytes = download_line_content(message_id)
                if img_bytes:
                    USER_IMAGE_CACHE[user_id] = base64.b64encode(img_bytes).decode('utf-8')
                    reply_to_line(reply_token, "已收到圖片！您可以接著問我「這是什麼？」或「這要怎麼使用？」。")
                else:
                    reply_to_line(reply_token, "圖片讀取失敗，請重新傳送一次。")

            # 【情況 3】：收到文字
            elif msg_type == 'text':
                user_message = line_event['message']['text']
                user_img_base64 = USER_IMAGE_CACHE.pop(user_id, None)
                
                ai_reply = query_managed_kb_with_vision(user_message, user_img_base64)
                reply_to_line(reply_token, ai_reply)
                
        return {'statusCode': 200, 'body': 'Success'}
        
    except Exception as e:
        print(f"Handler Error: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

def download_line_content(message_id):
    try:
        line_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
        url = f'https://api-data.line.me/v2/bot/message/{message_id}/content'
        
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {line_access_token}'
        })
        
        with urllib.request.urlopen(req) as response:
            return response.read()
    except Exception as e:
        print(f"Download Content Error: {str(e)}")
        return None

def trigger_bedrock_sync():
    try:
        bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID
        )
        return "🔄 系統正在進行自動索引同步，約 1-2 分鐘後可查詢最新資料。"
    except Exception as e:
        return f"⚠️ 檔案已存入，但自動同步失敗：\n{str(e)}"

def query_managed_kb_with_vision(query_text, image_base64=None):
    try:
        retrieve_response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query_text}
        )
        
        retrieved_results = retrieve_response.get('retrievalResults', [])
        context_text = ""
        for result in retrieved_results:
            context_text += result.get('content', {}).get('text', '') + "\n\n"

        if not context_text:
            context_text = "（知識庫中未找到直接相關資訊）"

        prompt_text = f"""你是一個專業且親切的老人醫療器材諮詢助手。

請遵循以下原則回答：
1. 如果使用者提供了圖片，請先分析圖片中的醫療器材（名稱、外觀特徵、用途、顯示的數值意義）。
2. 結合下方提供之【參考資料】對該器材做更詳細的說明與使用注意事項。
3. 如果使用者沒有提供圖片，且只是打招呼，請親切回應並引導諮詢。

【參考資料】:
{context_text}

【使用者問題】: {query_text}"""

        content_blocks = []
        if image_base64:
            content_blocks.append({
                'image': {
                    'format': 'jpeg',
                    'source': {
                        'bytes': base64.b64decode(image_base64)
                    }
                }
            })
            
        content_blocks.append({'text': prompt_text})

        response = bedrock_runtime.converse(
            modelId='us.amazon.nova-pro-v1:0',
            messages=[{
                'role': 'user',
                'content': content_blocks
            }]
        )
        
        return response['output']['message']['content'][0]['text']

    except Exception as e:
        print(f"Vision & KB Error: {str(e)}")
        return f"Bedrock 錯誤訊息：{str(e)}"

def reply_to_line(reply_token, text):
    line_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {line_access_token}'
    }
    payload = {
        'replyToken': reply_token,
        'messages': [{'type': 'text', 'text': text}]
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as response:
        pass
