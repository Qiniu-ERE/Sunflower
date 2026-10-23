"""待办清单：Sunflower 现场演示用的小项目（语音指挥 Codex 在它上面改代码）。

    python3 todo.py add 买牛奶
    python3 todo.py list
    python3 todo.py done 1
"""
import json
import os
import sys

DB = os.environ.get("TODO_DB", "todos.json")


def load():
    try:
        with open(DB, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save(items):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add(title):
    items = load()
    items.append({"title": title, "done": False})
    save(items)
    return len(items)


def done(number):
    """把第 number 条（从 1 开始编号）标记为完成。"""
    items = load()
    items[number]["done"] = True
    save(items)
    return items[number]["title"]


def render(items):
    return "\n".join(f"{i}. [{'x' if it['done'] else ' '}] {it['title']}" for i, it in enumerate(items, 1))


def main(argv):
    if argv[:1] == ["add"] and len(argv) > 1:
        print(f"已添加 #{add(' '.join(argv[1:]))}")
    elif argv[:1] == ["done"] and len(argv) == 2:
        print(f"已完成：{done(int(argv[1]))}")
    else:
        print(render(load()))


if __name__ == "__main__":
    main(sys.argv[1:])
