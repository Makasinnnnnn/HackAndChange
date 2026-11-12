FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS dependencies
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app

FROM dependencies AS semantic-dependencies
COPY backend/requirements-semantic.txt ./requirements-semantic.txt
RUN pip install --no-cache-dir -r requirements-semantic.txt

FROM dependencies AS base
COPY backend/app ./app
COPY backend/data ./data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM semantic-dependencies AS semantic
COPY backend/app ./app
COPY backend/data ./data
COPY scripts/download_model.py ./scripts/download_model.py
RUN mkdir -p /app/.private/models/e5 && chown -R app:app /app/.private
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
