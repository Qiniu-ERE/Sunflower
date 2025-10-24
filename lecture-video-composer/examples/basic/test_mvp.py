#!/usr/bin/env python3
"""
MVP Test Script
演讲视频合成系统 - MVP 核心功能测试脚本

使用示例:
    python test_mvp.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from core.lecture_composer import LectureComposer


def create_test_files():
    """创建测试用的示例文件（仅创建文件名，不创建实际内容）"""
    print("=" * 60)
    print("测试文件创建说明")
    print("=" * 60)
    print("\n请准备以下格式的文件:")
    print("\n1. 音频文件 (10分钟):")
    print("   格式: YYYY-MM-DD-hh:mm:ss.mp3")
    print("   示例: 2025-10-24-14:30:00.mp3")
    print("\n2. 照片文件 (10张):")
    print("   格式: YYYY-MM-DD-hh:mm:ss.jpg")
    print("   示例:")
    
    # 生成示例文件名
    base_time = datetime(2025, 10, 24, 14, 30, 0)
    
    # 音频文件名
    audio_name = base_time.strftime("%Y-%m-%d %H:%M:%S.mp3")
    print(f"   音频: {audio_name}")
    
    # 照片文件名 (在10分钟内均匀分布)
    print("   照片:")
    photo_offsets = [135, 195, 255, 315, 375, 435, 495, 555, 615, 675]  # 秒
    for i, offset in enumerate(photo_offsets, 1):
        photo_time = base_time + timedelta(seconds=offset)
        photo_name = photo_time.strftime("%Y-%m-%d %H:%M:%S.jpg")
        print(f"     {i:2d}. {photo_name} (偏移 {offset}秒 = {offset/60:.1f}分钟)")
    
    print("\n" + "=" * 60)
    print("文件准备建议:")
    print("=" * 60)
    print("1. 将准备好的文件放在 examples/fixtures/ 目录下")
    print("2. 确保文件名严格遵循上述格式")
    print("3. 音频文件建议使用MP3格式，照片使用JPG格式")
    print("4. 确保系统已安装 ffmpeg: brew install ffmpeg (macOS)")
    print("5. 安装Python依赖: pip install -r requirements.txt")
    print()


def test_timeline_parsing():
    """测试时间轴解析功能"""
    from core.timeline.timeline_sync import TimelineSync
    
    print("\n" + "=" * 60)
    print("测试 1: 时间戳解析")
    print("=" * 60)
    
    test_filenames = [
        "2025-10-24-14:30:00.mp3",
        "2025-10-24-14:32:15.jpg",
        "2025-10-24-14:35:40.jpg"
    ]
    
    for filename in test_filenames:
        try:
            timestamp = TimelineSync.parse_timestamp(filename)
            print(f"✓ {filename} -> {timestamp}")
        except ValueError as e:
            print(f"✗ {filename} -> Error: {e}")


def test_full_workflow():
    """测试完整工作流程"""
    print("\n" + "=" * 60)
    print("测试 2: 完整工作流程")
    print("=" * 60)
    
    # 检查示例文件目录
    fixtures_dir = project_root / "examples" / "fixtures"
    
    if not fixtures_dir.exists():
        print(f"\n⚠ 示例文件目录不存在: {fixtures_dir}")
        print("请先创建目录并添加测试文件")
        return
    
    # 查找音频文件
    audio_files = list(fixtures_dir.glob("*.mp3"))
    if not audio_files:
        print(f"\n⚠ 未找到音频文件 (*.mp3) in {fixtures_dir}")
        print("请添加格式为 'YYYY-MM-DD-hh:mm:ss.mp3' 的音频文件")
        return
    
    audio_file = audio_files[0]
    print(f"\n找到音频文件: {audio_file.name}")
    
    # 查找照片文件
    photo_files = sorted(fixtures_dir.glob("*.jpg")) + sorted(fixtures_dir.glob("*.jpeg"))
    if not photo_files:
        print(f"\n⚠ 未找到照片文件 (*.jpg) in {fixtures_dir}")
        print("请添加格式为 'YYYY-MM-DD-hh:mm:ss.jpg' 的照片文件")
        return
    
    print(f"找到 {len(photo_files)} 个照片文件")
    
    # 设置输出目录
    output_dir = project_root / "examples" / "output" / "test_project"
    
    try:
        # 创建合成器
        print("\n创建 LectureComposer...")
        composer = LectureComposer(
            audio_file=audio_file,
            photo_files=photo_files,
            output_dir=output_dir
        )
        
        # 执行处理
        print("\n开始处理...")
        metadata = composer.process(title="测试演讲项目")
        
        # 显示摘要
        print(composer.get_summary())
        
        # 显示元数据
        print("\n生成的元数据 JSON:")
        print(metadata.to_json())
        
        print("\n✓ 测试成功完成!")
        print(f"✓ 项目已保存到: {output_dir}")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("演讲视频合成系统 - MVP 核心功能测试")
    print("=" * 60)
    
    # 显示文件准备说明
    create_test_files()
    
    # 运行测试
    test_timeline_parsing()
    
    # 提示用户
    print("\n" + "=" * 60)
    print("准备运行完整工作流程测试")
    print("=" * 60)
    response = input("\n是否继续运行完整测试? (需要准备好测试文件) [y/N]: ")
    
    if response.lower() in ['y', 'yes']:
        test_full_workflow()
    else:
        print("\n已跳过完整测试。请先准备测试文件后再运行。")
    
    print("\n" + "=" * 60)
    print("测试脚本执行完毕")
    print("=" * 60)
    print("\n下一步:")
    print("1. 准备测试文件 (音频 + 照片)")
    print("2. 运行: python examples/basic/test_mvp.py")
    print("3. 或使用命令行: python src/core/lecture_composer.py <audio_file> <photo_dir>")
    print()


if __name__ == '__main__':
    main()
