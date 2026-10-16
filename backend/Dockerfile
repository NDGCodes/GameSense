FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools wheel

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

RUN groupadd --system gamesense && useradd --system --gid gamesense --home-dir /app gamesense \
    && chown -R gamesense:gamesense /app
USER gamesense

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
