FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY rag_api/requirements_simple.txt .
RUN pip install --no-cache-dir -r requirements_simple.txt

# Copy application code
COPY rag_api/ ./rag_api/

# Create necessary directories
RUN mkdir -p rag_api/data rag_api/storage

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app

# Run the application
CMD ["uvicorn", "rag_api.api:app", "--host", "0.0.0.0", "--port", "8000"] 