FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY matchlab /app/matchlab

WORKDIR /app/matchlab

RUN mkdir -p data

EXPOSE 8000 19204

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
