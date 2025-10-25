#!/usr/bin/env python3
"""
快速字幕功能测试
使用短音频片段测试 Whisper 字幕生成
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from services.subtitle.subtitle_service import SubtitleService, SubtitleConfig

def test_whisper_availability():
    """测试 Whisper 是否可用"""
    print("\n" + "="*60)
    print("测试 1: Whisper 可用性检查")
    print("="*60)
    
    try:
        import whisper
        print(f"✅ Whisper 已安装")
        print(f"   版本: {whisper.__version__}")
        
        # 列出可用模型
        models = ["tiny", "base", "small", "medium", "large"]
        print(f"\n可用模型: {', '.join(models)}")
        print(f"推荐模型:")
        print(f"  - tiny: 最快，准确度较低")
        print(f"  - base: 快速，准确度中等 ⭐ 推荐")
        print(f"  - small: 较慢，准确度高")
        
        return True
    except ImportError as e:
        print(f"❌ Whisper 未安装: {e}")
        return False


def test_subtitle_service():
    """测试字幕服务初始化"""
    print("\n" + "="*60)
    print("测试 2: 字幕服务初始化")
    print("="*60)
    
    try:
        # 使用 tiny 模型进行快速测试
        config = SubtitleConfig(
            model='tiny',  # 最小模型，测试最快
            language='zh',
            font_size=24
        )
        
        service = SubtitleService(config)
        print(f"✅ 字幕服务初始化成功")
        print(f"   模型: {config.model}")
        print(f"   语言: {config.language}")
        print(f"   字体大小: {config.font_size}")
        
        return service
    except Exception as e:
        print(f"❌ 字幕服务初始化失败: {e}")
        return None


def test_subtitle_generation(service: SubtitleService):
    """测试字幕生成（使用项目音频）"""
    print("\n" + "="*60)
    print("测试 3: 字幕生成测试")
    print("="*60)
    
    # 使用示例音频文件
    audio_file = Path("examples/fixtures/2025-10-24-15:15:15.mp3")
    output_dir = Path("examples/output/subtitle_test")
    
    if not audio_file.exists():
        print(f"❌ 音频文件不存在: {audio_file}")
        return False
    
    print(f"音频文件: {audio_file.name}")
    print(f"输出目录: {output_dir}")
    print("\n⚠️  注意: 这是一个10分钟的音频文件")
    print("   使用 tiny 模型预计需要 1-2 分钟")
    print("   生成的字幕可能不够准确（建议使用 base 或 small 模型）")
    
    # 询问是否继续
    try:
        response = input("\n是否继续测试字幕生成？[y/N]: ").strip().lower()
        if response != 'y':
            print("跳过字幕生成测试")
            return False
    except:
        print("\n跳过字幕生成测试")
        return False
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("\n🎤 开始生成字幕...")
        print("   (这可能需要 1-2 分钟，请耐心等待)")
        
        # 生成 SRT 字幕（同时也会生成 ASS 格式）
        srt_file = service.generate_subtitles(
            audio_file=audio_file,
            output_dir=output_dir
        )
        
        if srt_file and srt_file.exists():
            print(f"\n✅ SRT 字幕生成成功!")
            print(f"   文件: {srt_file}")
            print(f"   大小: {srt_file.stat().st_size / 1024:.1f} KB")
            
            # 显示前几行字幕
            print("\n📝 字幕预览（前10行）:")
            print("-" * 60)
            with open(srt_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:10]
                print(''.join(lines))
            print("-" * 60)
            
            return True
        else:
            print(f"❌ 字幕生成失败")
            return False
            
    except Exception as e:
        print(f"❌ 字幕生成出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("🎬 字幕功能快速测试")
    print("="*60)
    print("\n使用 Whisper AI 进行语音识别")
    print("测试环境: Python 3.13 + Whisper")
    
    # 测试 1: Whisper 可用性
    if not test_whisper_availability():
        print("\n❌ 测试失败: Whisper 不可用")
        return 1
    
    # 测试 2: 字幕服务
    service = test_subtitle_service()
    if not service:
        print("\n❌ 测试失败: 字幕服务初始化失败")
        return 1
    
    # 测试 3: 字幕生成（可选）
    test_subtitle_generation(service)
    
    print("\n" + "="*60)
    print("✅ 字幕功能测试完成")
    print("="*60)
    print("\n提示:")
    print("  - tiny 模型: 速度快，准确度低")
    print("  - base 模型: 平衡速度和准确度 ⭐")
    print("  - small/medium 模型: 准确度高，速度较慢")
    print("\n更多信息请参考: docs/字幕功能文档.md")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
