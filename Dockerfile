# Use the official Python 3.12 Alpine image
FROM python:3.12-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies and build tools
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    postgresql-dev \
    build-base \
    python3-dev \
    jpeg-dev \
    zlib-dev \
    libjpeg \
    libxml2-dev \
    libxslt-dev \
    curl \
    gettext \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies (including Gunicorn)
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project files
COPY . .

# Expose port used by Gunicorn
EXPOSE 8000

# Start the Gunicorn server
# Replace `myproject.wsgi` with your actual Django project's WSGI module
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "suji.wsgi:application"]
