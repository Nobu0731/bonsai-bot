import os
import requests
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage
from openai import OpenAI
from PIL import Image
from io import BytesIO

# 環境変数
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# インスタンス初期化
app = FastAPI()
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ユーザーごとの画像を一時保存
user_images = {}

@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    signature = request.headers["X-Line-Signature"]
    handler.handle(body.decode("utf-8"), signature)
    return "OK"

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    message_content = line_bot_api.get_message_content(event.message.id)

    image_bytes = b""
    for chunk in message_content.iter_content():
        image_bytes += chunk

    user_images[user_id] = image_bytes

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="サイズをテキストで送ってください（例：15cm）")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text

    if user_id not in user_images:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="先に盆栽の画像を送ってください")
        )
        return

    # Vision APIで画像+テキストから査定
    try:
        image_data = user_images.pop(user_id)
        image_b64 = f"data:image/jpeg;base64,{image_data.hex()}"

        response = openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "system",
                    "content": "あなたはプロの盆栽査定士です。盆栽の見た目とサイズ情報をもとに、簡単な査定コメントを返してください。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"この盆栽は{event.message.text}です。査定をお願いします。"},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_data.hex()}}
                    ]
                }
            ],
            max_tokens=500
        )

        result = response.choices[0].message.content.strip()

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=result)
        )

    except Exception as e:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"査定中にエラーが発生しました：\n{str(e)}")
        )
