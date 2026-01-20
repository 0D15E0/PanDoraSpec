# Use official Python runtime as a parent image
# Slim variant is good for production size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for WeasyPrint (Pango, etc)
# This is crucial for PDF report generation
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
# Since we don't have a requirements.txt, we install from setup.py (pyproject.toml)
# Copying valid files for pip install
COPY pyproject.toml README.md ./

# Install dependencies (temporarily creating an empty package structure to allow pip install .)
# Or simpler: COPY . . AND THEN INSTALL
# Let's copy everything and install.
COPY pandoraspec ./pandoraspec
# COPY scripts ./scripts # Only if needed
# COPY tests ./tests # Only if needed for running tests in docker

# Copy entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Install the package in editable mode? No, standard install for prod image.
RUN pip install .

# Entrypoint to the CLI (Default, but overridden by Action if used)
ENTRYPOINT ["pandoraspec"]

# Default arguments (can be overridden)
CMD ["--help"]
