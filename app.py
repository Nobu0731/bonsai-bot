import os
import openai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)

# LINE APIキー
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# OpenAI APIキー
openai.api_key = os.getenv("OPENAI_API_KEY")

# 一時保存用の辞書（user_id: {image_url, size}）
user_data = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)  # ← 必ずここで読み取る

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ 署名不一致です")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    message_id = event.message.id

    # LINEの画像URL（実際は公開URL化が必要／ここは仮置き）
    # LINEの画像は一時URLなのでCloudinaryやS3でホストするのが現実的です
    dummy_image_url = "https://example.com/sample_bonsai.jpg"  # ← 仮の画像URL

    user_data[user_id] = {
        "image_url": dummy_image_url
    }

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="サイズをテキストで送ってください（例：15cm）")
    )


@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    size_text = event.message.text

    if user_id not in user_data or 'image_url' not in user_data[user_id]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="先に盆栽の写真を送ってください。")
        )
        return

    image_url = user_data[user_id]['image_url']

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"この盆栽の写真とサイズ（{size_text}）をもとに、価値を簡易的に査定してください。"},
                        {"type": "image_url", "image_url": image_url}
                    ]
                }
            ],
            max_tokens=500
        )
        reply_text = response.choices[0].message.content.strip()

    except Exception as e:
        reply_text = f"査定中にエラーが発生しました：{str(e)}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

    user_data.pop(user_id, None)  # セッションデータ初期化


if __name__ == "__main__":
    app.run()
