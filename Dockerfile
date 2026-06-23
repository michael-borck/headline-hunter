FROM python:3.12-slim

WORKDIR /app

# Install deps first so the layer caches when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app + static assets (.dockerignore keeps .env and junk out).
COPY . .

EXPOSE 8000

# Secrets come in at runtime via --env-file .env (never baked into the image).
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
