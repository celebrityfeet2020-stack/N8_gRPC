FROM python:3.11-slim

WORKDIR /app

# 安装后端依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码（包括后端代码和static目录）
COPY . .

# 暴露端口
EXPOSE 18032

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:18032/health')"

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "18032"]
