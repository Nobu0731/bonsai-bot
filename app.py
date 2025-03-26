from flask import Flask, request, abort
import os
import openai
import base64
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage

app = Flask(__name__)

# 環境変数からキーを取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# 一時保存：ユーザーIDごとに画像を一時保存
user_temp_images = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    message_id = event.message.id
    content = line_bot_api.get_message_content(message_id)
    image_data = content.content

    # 一時保存（メモリ上）
    user_temp_images[user_id] = image_data

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="サイズをテキストで送ってください（例：15cm）")
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # ユーザーに画像が一時保存されている場合はVisionへ送信
    if user_id in user_temp_images:
        image_data = user_temp_images.pop(user_id)
        encoded_image = base64.b64encode(image_data).decode("utf-8")

        prompt = f"この画像は盆栽です。サイズは{text}です。種類（例：黒松、真柏など）と状態、推定価格帯を日本語で詳しく教えてください。"

        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]}
            ],
            max_tokens=1000
        )

        result = response.choices[0].message.content.strip()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result))
    else:
        # 通常テキスト対応
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="画像を先に送ってからサイズを送ってください。")
        )

if __name__ == "__main__":
    app.run()
