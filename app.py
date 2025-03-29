import os
import base64
import tempfile
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage
from PIL import Image
from io import BytesIO
from openai import OpenAI
import json

# Google Vision API
from google.cloud import vision
from google.oauth2 import service_account

# Decode and write credentials
creds_base64 = os.environ["GOOGLE_CREDENTIALS_BASE64"]
creds_json = base64.b64decode(creds_base64)
with open("gcp_credentials.json", "wb") as f:
    f.write(creds_json)

credentials = service_account.Credentials.from_service_account_file("gcp_credentials.json")
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# LINE API
line_bot_api = LineBotApi(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))

# OpenAI API
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 状態保持用（ユーザーの画像を一時保存）
user_images = {}

app = FastAPI()

@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature")
    try:
        handler.handle(body.decode("utf-8"), signature)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})
    return JSONResponse(status_code=200, content={"message": "OK"})

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    image_data = BytesIO(message_content.content)
    user_images[event.source.user_id] = image_data
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="サイズをテキストで送ってください\n（例：15cm）")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    size_text = event.message.text.strip()

    if user_id not in user_images:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="まずは盆栽の画像を送ってください。")
        )
        return

    try:
        # Vision APIでラベル抽出
        image = vision.Image(content=user_images[user_id].getvalue())
        response = vision_client.label_detection(image=image)
        labels = [label.description for label in response.label_annotations]
        label_text = ", ".join(labels)

        # ChatGPTプロンプト
        prompt = f"""
以下の情報をもとに、ユーザーに返信する形で、
盆栽の特徴・良さ・注意点を簡潔に説明し、最後にざっくりとした査定額の目安を添えてください。
親しみやすく、ややプロっぽい語り口でお願いします。

【情報】
- サイズ：{size_text}
- 画像の特徴（Vision APIのラベル）：{label_text}

※返答は150文字以内を目安にしてください。
        """

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは盆栽の査定士です。"},
                {"role": "user", "content": prompt},
            ]
        )

        message = response.choices[0].message.content.strip()

    except Exception as e:
        message = f"査定中にエラーが発生しました：\n{str(e)}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=message)
    )

    # 一度使った画像は削除
    del user_images[user_id]
