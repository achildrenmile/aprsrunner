FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aprsrunner.py .
COPY config-carinthia.yaml .

ENTRYPOINT ["python", "aprsrunner.py"]
CMD ["--config", "config-carinthia.yaml"]
