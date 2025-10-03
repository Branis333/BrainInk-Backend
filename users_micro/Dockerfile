FROM public.ecr.aws/docker/library/python:3.12-alpine
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

ENV PORT=8000
WORKDIR /var/task

# Install build dependencies and clean up in single layer
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    postgresql-dev \
    && apk add --no-cache \
    libpq \
    && rm -rf /var/cache/apk/*

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# Copy only necessary files
COPY main.py ./
COPY Endpoints/ ./Endpoints/
COPY db/ ./db/
COPY models/ ./models/
COPY schemas/ ./schemas/
COPY functions/ ./functions/
COPY services/ ./services/

# Create ALL upload directories that code tries to create
RUN mkdir -p uploads/after_school \
             uploads/textbooks \
             uploads/student_pdfs \
             uploads/student_images \
             uploads/bulk_pdfs

CMD exec uvicorn --port=$PORT main:app

