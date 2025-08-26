# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Make Python friendlier in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the package (keeps image small)
COPY showads_connector/ ./showads_connector/

# (Optional) run as non-root
RUN useradd -m appuser
USER appuser

# Run the package as a module. Args you pass to `docker run` will be appended.
ENTRYPOINT ["python", "-m", "showads_connector"]
