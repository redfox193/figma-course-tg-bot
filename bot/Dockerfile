FROM python:3.11-slim

WORKDIR /bot

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY routers/ routers/
COPY bot.py/ bot.py/
COPY settings.py/ settings.py/
COPY shared.py/ shared.py/
COPY utils.py/ utils.py/