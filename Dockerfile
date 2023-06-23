FROM python:3.9-slim-buster

# ワーキングディレクトリの設定
WORKDIR /app

# アプリケーションの依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY . .

# ポート番号の設定
EXPOSE 8080

# アプリケーションの実行コマンド
CMD ["python", "app.py"]
