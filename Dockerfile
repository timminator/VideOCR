# ==========================================
# STAGE 1: Building Environment
# ==========================================
FROM python:3.12-slim AS builder

# Define the build argument (cpu, gpu-cuda11.8, or gpu-cuda12.9)
ARG BUILD_TARGET=gpu-cuda12.9

RUN apt-get update && apt-get install -y \
    gcc \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir . --group all
RUN python build.py --cli-only true --target ${BUILD_TARGET}
RUN mv Releases/videocr-cli-*-Linux /src/final_build

# ==========================================
# STAGE 2: Final Image
# ==========================================
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /src/final_build /app/videocr

ENTRYPOINT ["/app/videocr/videocr-cli.bin"]
