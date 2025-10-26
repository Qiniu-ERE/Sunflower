#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web服务器启动脚本
用于启动演讲视频合成系统的Web界面
"""
import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入Web应用
from src.web.app import create_app, cleanup_sessions


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='启动演讲视频合成系统Web服务器'
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='服务器监听地址 (默认: 0.0.0.0, 允许外部访问)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='服务器监听端口 (默认: 5000)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '--env',
        choices=['development', 'production', 'testing'],
        default='development',
        help='运行环境 (默认: development)'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='清理过期会话后退出'
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 如果只是清理会话
    if args.cleanup:
        print("清理过期会话...")
        app = create_app(args.env)
        with app.app_context():
            cleanup_sessions()
        print("完成")
        return
    
    # 创建应用
    app = create_app(args.env)
    
    # 打印启动信息
    print("=" * 60)
    print("演讲视频合成系统 - Web服务器")
    print("=" * 60)
    print(f"环境: {args.env}")
    print(f"调试模式: {'开启' if args.debug else '关闭'}")
    print(f"服务器地址: http://{args.host}:{args.port}")
    print("=" * 60)
    print()
    print("提示:")
    print("  - 在浏览器中打开上述地址访问Web界面")
    print("  - 按 Ctrl+C 停止服务器")
    print()
    
    # 启动服务器
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
