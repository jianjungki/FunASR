# ==========================================                                                                                                                                                                                                                                
# 1. 构建前置参数定义                                                                                                                                                                                                                                                       
# ==========================================                                                                                                                                                                                                                                
# 默认基础镜像使用 python:3.10-slim
# 如果是 NPU 环境，强烈建议在 build 时传入华为官方镜像：
# --build-arg BASE_IMAGE=ascendhub.huawei.com/public-ascendhub/ascend-pytorch:2.1.0-ubuntu22.04
ARG BASE_IMAGE=python:3.10-slim
FROM ${BASE_IMAGE}

# 定义构建目标设备，可选值: cpu, cuda, npu
ARG BUILD_DEVICE=cpu

# ==========================================
# 2. 运行时环境变量设置
# ==========================================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FUNASR_MODEL=sensevoice \
    FUNASR_PORT=8000 \
    PYTHONWARNINGS="ignore::SyntaxWarning"

# 将构建期的设备参数继承给运行期环境变量
ENV FUNASR_DEVICE=${BUILD_DEVICE}

WORKDIR /app

# ==========================================
# 3. 安装系统级音频与基础依赖
# ==========================================
RUN if command -v apt-get >/dev/null 2>&1; then \
        echo "=== Detecting Debian/Ubuntu System ===" \
        && apt-get update \
        && apt-get install -y --no-install-recommends \
            ffmpeg git libsndfile1 python3 python3-pip python-is-python3 \
        && rm -rf /var/lib/apt/lists/*; \
    elif command -v dnf >/dev/null 2>&1; then \
        echo "=== Detecting OpenEuler/RedHat System (using dnf) ===" \
        && dnf clean all \
        && dnf install -y ffmpeg git libsndfile python3-pip \
        && dnf clean all; \
    elif command -v yum >/dev/null 2>&1; then \
        echo "=== Detecting OpenEuler/RedHat System (using yum) ===" \
        && yum clean all \
        && yum install -y ffmpeg git libsndfile python3-pip \
        && yum clean all; \
    else \
        echo "=== Unknown OS, skipped system package installation ==="; \
    fi \
    && python3 -m pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/

# ==========================================
# 4. 核心深度学习框架条件分支安装
# ==========================================
RUN if [ "${BUILD_DEVICE}" = "cuda" ]; then \
        echo "=== Installing Target: NVIDIA CUDA ===" \
        && pip3 install --no-cache-dir \
            torch==2.7.1 \
            torchaudio==2.7.1 \
            --index-url https://download.pytorch.org/whl/cu129; \
    elif [ "${BUILD_DEVICE}" = "npu" ]; then \
        echo "=== Installing Target: HUAWEI ASCEND NPU ===" \
        && if ! python3 -c "import torch" 2>/dev/null; then \
            pip3 install --no-cache-dir torch==2.10.0 -i https://mirrors.aliyun.com/pypi/simple/; \
        fi \
        && pip3 install --no-cache-dir torch_npu==2.10.0 -i https://mirrors.aliyun.com/pypi/simple/ \
        && pip3 install --no-cache-dir \
            torchaudio==2.10.0 \
            --index-url https://download.pytorch.org/whl/cpu; \
    else \
        echo "=== Installing Target: PURE CPU ===" \
        && pip3 install --no-cache-dir \
            torch==2.7.1 \
            torchaudio==2.7.1 \
            -i https://mirrors.aliyun.com/pypi/simple/; \
    fi

# ==========================================
# 5. 安装业务层依赖 (Private FunASR & FastAPI 服务)
# ==========================================
ARG FUNASR_GIT_URL=https://github.com/jianjungki/FunASR.git
ARG FUNASR_GIT_REF=main
RUN pip3 install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    "git+${FUNASR_GIT_URL}@${FUNASR_GIT_REF}" \
    fastapi \
    "uvicorn[standard]" \
    python-multipart

# 拷贝服务端脚本
COPY server.py /app/server.py

EXPOSE 8000

# ==========================================
# 6. 健康检查与容器启动
# ==========================================
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('FUNASR_PORT', '8000'), timeout=3).read()" || exit 1

# 启动时动态读取环境变量，确保 --device 传入的是运行时设定的实际硬件
CMD ["sh", "-c", "python3 server.py --host 0.0.0.0 --port ${FUNASR_PORT:-8000} --device ${FUNASR_DEVICE} --model ${FUNASR_MODEL:-sensevoice}"]