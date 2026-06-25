FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG TTB_EMBEDDING_MODEL=intfloat/multilingual-e5-base
ENV TTB_EMBEDDING_MODEL=${TTB_EMBEDDING_MODEL}
ENV HF_HOME=/models/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${TTB_EMBEDDING_MODEL}')"

COPY app ./app
COPY policies ./policies
COPY data ./data
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
