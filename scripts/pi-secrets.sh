#!/usr/bin/env bash
# 在 Mac 上运行：把树莓派运行所需的密钥经 ssh 管道写入板上 ~/Sunflower/.env（600），明文不落 Mac 磁盘、不进参数、不回显。
#
#   scripts/pi-secrets.sh push <prod1|prod2> <codex-钥匙串服务名>
#   scripts/pi-secrets.sh wipe            # 比赛结束：粉碎板上 .env
#
# 灵矽 key 按笔记里的标签（「生产用API key 1/2」）取其后第一条 lx- 行；
# Codex(qiniu-gpt) key 从本机钥匙串取，板上以 QINIU_GPT_API_KEY 提供给 codex（provider env_key）。
# 板上已有的 SUNFLOWER_TOKEN 保留，没有则在板上生成。
set -euo pipefail
PI=${SUNFLOWER_PI:-sunflower-pi}
NOTES=${SUNFLOWER_NOTES:-"$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/SunYifei/全局TODO/企业bot相关.md"}

fp() { printf %s "$1" | shasum -a 256 | cut -c1-8; }

linx_key() {  # $1 = 笔记里的标签行
  awk -v label="$1" '$0 == label {hit=1; next} hit && /^lx-/ {print; exit} hit && /^$/ {exit}' "$NOTES"
}

case "${1:-}" in
push)
  case "${2:-}" in
    prod1) label="生产用API key 1" ;;
    prod2) label="生产用API key 2" ;;
    *) echo "用法: $0 push <prod1|prod2> <codex-钥匙串服务名>" >&2; exit 2 ;;
  esac
  svc=${3:?缺 codex 钥匙串服务名}
  linx=$(linx_key "$label")
  [ -n "$linx" ] || { echo "笔记里找不到「${label}」下的 lx- key" >&2; exit 1; }
  codex=$(/usr/bin/security find-generic-password -s "$svc" -w) || { echo "钥匙串里没有服务 $svc" >&2; exit 1; }
  printf 'LINX_API_KEY=%s\nQINIU_GPT_API_KEY=%s\n' "$linx" "$codex" | ssh "$PI" 'set -e
    umask 077; cd ~/Sunflower
    tok=$(grep -s "^SUNFLOWER_TOKEN=" .env | cut -d= -f2- || true)
    [ -n "$tok" ] || tok=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    { cat; printf "SUNFLOWER_TOKEN=%s\n" "$tok"; } > .env.new
    chmod 600 .env.new && mv .env.new .env'
  echo "已写入 $PI:~/Sunflower/.env  灵矽=$2(fp $(fp "$linx"))  codex=$svc(fp $(fp "$codex"))"
  ;;
wipe)
  ssh "$PI" 'cd ~/Sunflower && if [ -f .env ]; then shred -u .env && echo "已粉碎 .env"; else echo "无 .env"; fi'
  ;;
*)
  echo "用法: $0 push <prod1|prod2> <codex-钥匙串服务名> | wipe" >&2; exit 2 ;;
esac
