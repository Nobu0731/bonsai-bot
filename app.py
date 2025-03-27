import os
import openai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)

# LINE APIキー
LINE_CHANNEL_ACCESS_TOKEN = 'YOUR_LINE_CHANNEL_ACCESS_TOKEN'
LINE_CHANNEL_SECRET = 'YOUR_LINE_CHANNEL_SECRET'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# OpenAI APIキー
openai.api_key = os.getenv("OPENAI_API_KEY")

# ユーザーの画像とサイズを一時保存（簡易対応）
user_data = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)  # ★ここで str のまま受け取る

    try:
        handler.handle(body, signature)  # ★変換せずにそのまま渡す
    except InvalidSignatureError:
        print("❌ 署名不一致です")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    # ユーザーID取得
    user_id = event.source.user_id

    # 画像URL取得
    message_id = event.message.id
    image_content = line_bot_api.get_message_content(message_id)
    
    # 保存して公開URLを取得（今回は一時対応で未実装。CloudinaryやS3等でURLに変換する必要あり）
    # ダミーURLで進めます（実際は画像URLに変換）
    image_url = "https://example.com/sample_bonsai.jpg"
    
    user_data[user_id] = {"image_url": image_url}
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="サイズをテキストで送ってください（例：15cm）")
    )


@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    size_text = event.message.text

    # ユーザーが画像を送っていない場合
    if user_id not in user_data or 'image_url' not in user_data[user_id]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="先に盆栽の写真を送ってください。")
        )
        return

    image_url = user_data[user_id]['image_url']

    try:
        # OpenAI Vision API 呼び出し
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"以下の盆栽の写真とサイズ（{size_text}）を参考に、価値や特徴を簡単に査定してください。"},
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

    # 処理完了後に初期化（任意）
    user_data.pop(user_id, None)


if __name__ == "__main__":
    app.run()
