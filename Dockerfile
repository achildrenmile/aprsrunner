FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aprsrunner.py .
COPY config-austria.yaml .

ENTRYPOINT ["python", "aprsrunner.py"]
CMD ["--config", "config-austria.yaml", "--state-file", "/data/state.json"]
