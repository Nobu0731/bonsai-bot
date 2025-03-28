import os
import base64
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage
from openai import OpenAI
from vision_utils import analyze_image_from_bytes

# credentials.json を /tmp に復元
creds_base64 = os.environ["GOOGLE_CREDENTIALS_BASE64"]
creds_json_path = "/tmp/credentials.json"
with open(creds_json_path, "wb") as f:
    f.write(base64.b64decode(creds_base64))
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_json_path

# API 初期化
app = FastAPI()
line_bot_api = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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
    image_bytes = b"".join(chunk for chunk in message_content.iter_content())
    user_images[user_id] = image_bytes
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="サイズをテキストで送ってください（例：15cm）")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_images:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="先に画像を送ってください📷")
        )
        return

    try:
        image_bytes = user_images.pop(user_id)
        labels = analyze_image_from_bytes(image_bytes)
        label_text = "、".join(labels[:5])

        prompt = (
            f"この盆栽はサイズが{text}です。\n"
            f"以下の特徴が画像から確認されました：{label_text}。\n"
            f"これらの情報から簡単な査定コメントをお願いします。"
        )

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは盆栽査定士です。"},
                {"role": "user", "content": prompt}
            ]
        )

        result = response.choices[0].message.content.strip()

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=result)
        )

    except Exception as e:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"エラー：{str(e)}")
        )
