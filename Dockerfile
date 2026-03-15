# Use an official, lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for PostGIS (GeoAlchemy2) and PIL (Images)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy your requirements file first (to leverage Docker caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project into the container
COPY . .

# Expose the port FastAPI will run on
EXPOSE 8000

# The command to run your API
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]