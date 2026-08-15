# Dockerfile: how to build a container image of our Python app.
# The API, worker, and scheduler all run from this same image — they just
# start with different commands (defined in docker-compose.yml).

FROM python:3.12-slim

# Set the working directory inside the container.
WORKDIR /code

# Install dependencies first (this layer is cached unless requirements change).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code in.
COPY . .

# Default command (overridden per-service in docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
