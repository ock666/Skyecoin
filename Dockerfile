FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY skyecoin/ skyecoin/

RUN pip install --no-cache-dir -e .

EXPOSE 5000

VOLUME ["/app/data"]

CMD ["python", "-m", "skyecoin.app"]
