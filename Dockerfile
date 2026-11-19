
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Update Debian packages and install runtime library
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .

# Upgrade packaging tools and install application dependencies
RUN python -m pip install --no-cache-dir --upgrade \
      "pip" \
      "setuptools>=78.1.1" && \
    python -m pip install --no-cache-dir \
      -r requirements-api.txt \
      "msgpack>=1.2.3" \
      "urllib3>=2.8.0" && \
    python -m pip check

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
