FROM python:3.11-slim

WORKDIR /app

# Install compile-time dependencies
RUN pip install grpcio grpcio-tools

# Copy the proto folder from root into /app/proto
COPY proto/ proto/

# Make sure we have __init__.py so that "proto" becomes a Python package
RUN touch proto/__init__.py && touch proto/v1/__init__.py
RUN apt-get update && apt-get install -y tree

# Generate Python stubs
RUN python3 -m grpc_tools.protoc \
    -I=. \
    --python_out=. \
    --grpc_python_out=. \
    --proto_path=. \
    ./proto/v1/document.proto \
    ./proto/v1/logic.proto \
    ./proto/v1/orchestrator.proto


# Copy the actual orchestrator server code
COPY services/orchestrator-service/src/ ./src/

# Optionally set a PYTHONPATH
ENV PYTHONPATH=/app:$PYTHONPATH

EXPOSE 50050

RUN tree


CMD ["python", "-u", "src/app.py"]
