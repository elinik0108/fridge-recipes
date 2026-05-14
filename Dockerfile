FROM python:3.12-slim

# Lambda Web Adapter — runs as a Lambda extension, forwards events to uvicorn.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 \
     /lambda-adapter /opt/extensions/lambda-adapter

# Tell LWA where to send traffic and how to know we're ready.
ENV PORT=8000
ENV READINESS_CHECK_PATH=/health

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI app
COPY app/ ./app/

# Plain uvicorn — no Lambda handler conflict.
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]