FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install .
COPY alembic ./alembic
COPY alembic.ini docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && useradd -r -u 10001 ukintel && chown -R ukintel /app
USER ukintel
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
