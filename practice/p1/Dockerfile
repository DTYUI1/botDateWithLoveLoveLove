FROM python:3.13-slim

WORKDIR /app

COPY packages/ /packages/
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/packages -r requirements.txt

COPY app/ .

CMD ["python", "main.py"]
