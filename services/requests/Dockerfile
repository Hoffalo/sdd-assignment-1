# syntax=docker/dockerfile:1
# Requests service image. Built in CI from services/requests as the context.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# A fixed, unprivileged UID: the process can read the code but not change it.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin avdesk

# Dependencies first, in their own layer, so a code change does not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Named copies, never `COPY . .`: nothing reaches the image by accident
# (a local .env, test data, caches).
COPY app.py seed.json ./
COPY migrations ./migrations
COPY avdesk_requests ./avdesk_requests

# The pipeline passes the commit SHA, which GET /health reports as "version".
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

USER avdesk
EXPOSE 8000
CMD ["python", "app.py"]
