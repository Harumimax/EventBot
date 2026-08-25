FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system eventbot \
    && adduser --system --ingroup eventbot eventbot

COPY pyproject.toml README.md ./
COPY eventbot ./eventbot

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN mkdir -p /app/data \
    && chown -R eventbot:eventbot /app

USER eventbot

CMD ["python", "-m", "eventbot"]
