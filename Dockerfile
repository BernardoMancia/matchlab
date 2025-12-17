services:
  api:
    build: .
    env_file: .env
    volumes:
      - ./matchlab/data:/app/matchlab/data
    ports:
      - "19203:8000"
    restart: unless-stopped

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
