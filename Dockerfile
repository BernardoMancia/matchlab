services:
  api:
    build: .
    env_file: .env
    volumes:
      - ./matchlab/data:/app/matchlab/data
    ports:
      - "19203:8000"
    restart: unless-stopped

<<<<<<< Updated upstream
  bot:
    build: .
    env_file: .env
    environment:
      - MATCHLAB_API_BASE=http://api:8000
    depends_on:
      - api
    command: ["python", "-m", "bot.bot"]
    working_dir: /app/matchlab
    restart: unless-stopped
=======
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código (estrutura atual do repo)
COPY app /app/app
COPY bot /app/bot
COPY templates /app/templates
COPY dashboard /app/dashboard
COPY scripts /app/scripts
COPY README.md /app/README.md

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
>>>>>>> Stashed changes
