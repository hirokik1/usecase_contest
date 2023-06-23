FROM python:3.9-slim-buster

# ワーキングディレクトリの設定
WORKDIR /app

# アプリケーションの依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY . .

# 環境変数の設定
ENV STT_APIKEY=$STT_APIKEY
ENV STT_URL=$STT_URL
ENV LANGUAGE_MODEL_ID=$LANGUAGE_MODEL_ID
ENV NLU_APIKEY=$NLU_APIKEY
ENV NLU_URL=$NLU_URL
ENV WD_APIKEY=$WD_APIKEY
ENV WD_URL=$WD_URL
ENV WD_PROJECT_ID=$WD_PROJECT_ID
ENV CORS_ORIGINS=$CORS_ORIGINS

# ポート番号の設定
EXPOSE 8080

# アプリケーションの実行コマンド
CMD ["python", "navichang.py"]
