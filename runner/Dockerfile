FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 1001 --create-home sandbox

COPY runner_service ./runner_service

USER sandbox
EXPOSE 8001

CMD ["uvicorn", "runner_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
