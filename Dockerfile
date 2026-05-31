# 📰 股票资讯聚合平台 - Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（lxml 需要 libxml2/libxslt）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# Render 注入 PORT，默认 8000
EXPOSE 8000

CMD ["sh", "-c", "python3 run.py --port ${PORT:-8000}"]
