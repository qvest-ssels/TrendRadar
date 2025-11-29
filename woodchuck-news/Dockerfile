# Multi-stage Dockerfile for Woodchuck News

# ============================================
# Stage 1: Generator (Python)
# ============================================
FROM python:3.11-slim AS generator

WORKDIR /app

# Install dependencies
COPY generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy generator code
COPY generator/ ./generator/
COPY templates/ ./templates/
COPY static/ ./static/

# Create output directory
RUN mkdir -p /app/output

# Default command
CMD ["python", "-m", "generator"]

# ============================================
# Stage 2: nginx (for serving static files)
# ============================================
FROM nginx:alpine AS nginx

# Copy nginx configuration
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/sites/ /etc/nginx/conf.d/

# Copy static assets
COPY static/ /usr/share/nginx/html/static/

# Output will be mounted as volume
VOLUME ["/usr/share/nginx/html"]

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
