FROM python:3.11-slim

WORKDIR /backend

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY courseapi/ courseapi/
COPY manage.py manage.py
COPY gsheet_creds.json/ gsheet_creds.json/