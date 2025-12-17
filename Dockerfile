FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY bot /app/bot
COPY templates /app/templates
COPY dashboard /app/dashboard
COPY scripts /app/scripts
COPY README.md /app/README.md

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
