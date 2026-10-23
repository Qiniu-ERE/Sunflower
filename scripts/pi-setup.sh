#!/usr/bin/env bash
# 树莓派 4B（Raspberry Pi OS 64-bit Desktop）一键整备：设备客户端 + UxPlay AirPlay 接收端
set -euo pipefail
cd "$(dirname "$0")/.."

sudo apt-get update
sudo apt-get install -y uxplay gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-libav alsa-utils avahi-daemon python3-venv git
sudo usermod -aG input,audio "$USER"   # evdev 翻页笔 + 声卡

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo
echo "== USB 声卡（把 CARD 名填进 profiles/demo-pi.json 的 plughw:CARD=...）"
arecord -l | grep -E '^card' || echo "未发现录音设备：插上 USB 会议麦"
echo
echo "== 下一步"
echo "  1. cp .env.example .env 并填 SUNFLOWER_TOKEN（与 Mac 主机一致）"
echo "  2. 重新登录一次（input 组生效）"
echo "  3. AirPlay 接收:  uxplay -n linxpi -s 1920x1080 -fs -bt709"
echo "  4. 设备客户端:    .venv/bin/python -m sunflower.device --profile demo-pi"
