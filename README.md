# 🌻 Sunflower

> 对着灵矽设备说一句话，Codex 就开始写代码；进展经 AirPlay 实时投到设备屏幕，完成后语音播报结果。

（完整 README 装修中）

```bash
pip install -r requirements.txt && cp .env.example .env    # 填 LINX_API_KEY / SUNFLOWER_TOKEN
python3 -m sunflower.linx_admin up                          # 按需创建灵矽智能体 + 绑定软设备
python3 -m sunflower.host   --profile dev-single-mac        # 主机：Codex 执行器 + 进展面板
python3 -m sunflower.device --profile dev-single-mac        # 设备：空格说话 / t 输入文字
python3 -m unittest discover -s tests -t .                  # 离线单测（不连云）
```
