FROM python:3.12-slim

WORKDIR /app

# Install dependencies required for some python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and source code
COPY pyproject.toml .
COPY README.md .
COPY cca/ cca/
COPY examples/ examples/

# Install the framework along with all optional dependencies
RUN pip install --no-cache-dir ".[all,viz]"

# Create a non-root user for security
RUN useradd -m ccauser
USER ccauser

ENTRYPOINT ["cca"]
CMD ["--help"]
