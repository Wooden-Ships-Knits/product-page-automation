# PPA app image — runs both the Streamlit web UI and the hourly fetch (same image,
# different command in docker-compose). Matches the project's Python 3.9.
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# tz database so TZ / local-time scheduling works (the fetch window is local time).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

# Install deps in ONE resolution pass so the core's numpy==1.26.4 pin is honored
# even after streamlit is added (numpy 2.x would break the pandas import).
COPY requirements.txt ./requirements.txt
COPY webapp/requirements.txt ./webapp-requirements.txt
RUN pip install -r requirements.txt -r webapp-requirements.txt

# App code (secrets/data are excluded via .dockerignore and mounted at runtime)
COPY . .

EXPOSE 8501

# Default command = the web UI. The fetch service overrides this in compose.
CMD ["streamlit", "run", "webapp/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
