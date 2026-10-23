# 待办清单（演示工作区模板）

Sunflower 现场演示时，Codex 在这个项目的**一次性副本**里改代码（`python3 -m sunflower.demo reset` 生成）。
模板里故意留了一个编号差一的 bug，`python3 -m unittest` 会有失败——第一句演示需求就是"跑一下测试，把失败的修好"。
