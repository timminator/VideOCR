# syntax=docker/dockerfile:1

FROM nvcr.io/nvidia/cuda:12.9.2-cudnn-runtime-ubuntu24.04@sha256:5380b8155c710531212b65503b39fd7fef0715fef8aa4de791f67ba4faad4d7f

LABEL org.opencontainers.image.source="https://github.com/timminator/VideOCR"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt/lists,sharing=locked <<-EOF
	set -e
	apt-get update
	apt-get install -y --no-install-recommends python3 python3-pip p7zip-full curl libgl1 libglib2.0-0t64 libgomp1
	rm -f /usr/lib/python3*/EXTERNALLY-MANAGED
EOF

RUN --mount=type=cache,target=/root/.cache/pip <<-EOF
	set -e
	pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu129/

	# these are part of the base image, installing them just consumes space needlessly
	pip uninstall -y \
		nvidia-cublas-cu12 \
		nvidia-cuda-cccl-cu12 \
		nvidia-cuda-cupti-cu12 \
		nvidia-cuda-nvrtc-cu12 \
		nvidia-cuda-runtime-cu12 \
		nvidia-cudnn-cu12 \
		nvidia-cufft-cu12 \
		nvidia-cufile-cu12 \
		nvidia-curand-cu12 \
		nvidia-cusolver-cu12 \
		nvidia-cusparse-cu12 \
		nvidia-cusparselt-cu12 \
		nvidia-nccl-cu12 \
		nvidia-nvjitlink-cu12 \
		nvidia-nvtx-cu12 \
		2>/dev/null || true

	rm -f /usr/local/lib/python3.12/dist-packages/paddle/libs/libflashattn.so
	rm -f /usr/local/lib/python3.12/dist-packages/paddle/libs/libflashattnv3.so
	rm -f /usr/local/lib/python3.12/dist-packages/paddle/libs/libflashmaskv2.so
EOF

RUN --mount=type=cache,target=/root/.cache/pip <<-EOF
	set -e
	pip install "paddleocr>=3.4.0,<3.5.0"
	pip uninstall -y opencv-python || true
EOF

RUN --mount=type=cache,target=/root/.cache/pip <<-EOF
	set -e
	pip install av==17.0.1 cpuid==0.1.1 Fast-SSIM==1.3.1 numpy==2.4.6 opencc==1.3.1 Pillow==12.2.0 thefuzz==0.22.1 wakepy==1.0.0 wordninja-enhanced==3.1.1
EOF

WORKDIR /app/CLI

RUN --mount=type=cache,target=/tmp/paddle-cache <<-EOF
	set -e
	if [ ! -f /tmp/paddle-cache/support-files.7z ]; then
		curl -fSL -o /tmp/paddle-cache/support-files.7z "https://github.com/timminator/PaddleOCR-Standalone/releases/download/v1.4.0/PaddleOCR.PP-OCRv5.support.files.VideOCR.7z"
	fi
	echo "492aebd4d40baf128d823f429d6c2be802186ef60ca2dafe12b2d2494325f4ac  /tmp/paddle-cache/support-files.7z" | sha256sum -c
	7z x /tmp/paddle-cache/support-files.7z -y
EOF

RUN <<-EOF
	set -e
	find /usr/local/lib -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find /usr/local/lib -name "*.pyc" -delete 2>/dev/null || true
EOF

COPY CLI/videocr_cli.py /app/CLI/
COPY CLI/videocr/ /app/CLI/videocr/

COPY <<-'EOF' /app/entrypoint.sh
	#!/bin/bash
	set -e

	VIDEO_PATH=""
	HAS_OUTPUT=false

	for arg in "$@"; do
		if [[ "$prev" == "--video_path" ]]; then
			VIDEO_PATH="$arg"
		fi
		if [[ "$arg" == "--output" ]]; then
			HAS_OUTPUT=true
		fi
		prev="$arg"
	done

	if [[ -z "$VIDEO_PATH" ]]; then
		echo "Error: --video_path is required" >&2
		exit 1
	fi

	if [[ "$HAS_OUTPUT" == false ]]; then
		OUTPUT_DIR=$(dirname "$VIDEO_PATH")
		OUTPUT_BASE=$(basename "${VIDEO_PATH%.*}").srt
		set -- --output "${OUTPUT_DIR}/${OUTPUT_BASE}" "$@"
	fi

	exec python3 /app/CLI/videocr_cli.py --allow_system_sleep true "$@"
EOF

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
