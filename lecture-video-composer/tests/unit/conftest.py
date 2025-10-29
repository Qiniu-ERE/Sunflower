"""
Unit tests conftest - 单元测试配置
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
tests_dir = Path(__file__).parent
project_dir = tests_dir.parent.parent
sys.path.insert(0, str(project_dir))
