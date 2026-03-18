FROM public.ecr.aws/docker/library/python:3.12-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
ENV PORT=8000
WORKDIR /var/task
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt
COPY . ./
CMD exec uvicorn --port=$PORT main:app