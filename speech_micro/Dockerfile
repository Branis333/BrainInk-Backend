FROM python:3.12-slim as ml-builder
RUN pip install --no-cache-dir torch torchaudio openai-whisper librosa --index-url https://download.pytorch.org/whl/cpu

FROM public.ecr.aws/docker/library/python:3.12-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=ml-builder /usr/local/lib/python3.12/site-packages /var/lang/lib/python3.12/site-packages
ENV PORT=8000
WORKDIR /var/task
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-deps -r requirements.txt
COPY . ./
CMD exec uvicorn --port=$PORT main:app