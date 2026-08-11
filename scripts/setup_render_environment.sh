#!/usr/bin/env bash
set -euo pipefail

echo "Installing system dependencies..."
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ffmpeg fonts-dejavu-core curl unzip
else
  echo "apt-get not available; assuming ffmpeg is preinstalled."
fi

echo "Preparing font directory..."
mkdir -p /tmp/fonts

echo "Downloading Vazirmatn font..."
curl -L -o /tmp/fonts/Vazirmatn-Bold.ttf \
  https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf

echo "Render environment setup complete."
