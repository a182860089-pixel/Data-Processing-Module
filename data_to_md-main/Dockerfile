# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
# - libvips42t64: pyvips 运行时库（比 libvips-dev 依赖少很多）
# - libgl1: opencv 需要
# - 其他: 字体支持
RUN apt-get update && apt-get install -y --no-install-recommends \
    libvips42t64 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 playwright 浏览器（crawl4ai 需要）
RUN playwright install chromium --with-deps || true

# 复制应用代码
COPY . .

# 创建存储目录
RUN mkdir -p storage/uploads storage/outputs storage/cache storage/logs

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
