#!/usr/bin/env python3
"""
v2.0 功能测试脚本
测试720p视频输出和字幕生成功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.lecture_composer import LectureComposer
from services.video.video_exporter import VideoExportConfig


def test_720p_video_export():
    """测试720p视频导出（默认配置）"""
    print("\n" + "=" * 70)
    print("测试 1: 720p视频导出（默认配置）")
    print("=" * 70)
    
    # 准备测试数据
    audio_file = project_root / "examples/fixtures/2025-10-24-15:15:15.mp3"
    photos_dir = project_root / "examples/fixtures/sample-photos"
    output_dir = project_root / "examples/output/v2_test"
    
    if not audio_file.exists():
        print(f"❌ 音频文件不存在: {audio_file}")
        return False
    
    if not photos_dir.exists():
        print(f"❌ 照片目录不存在: {photos_dir}")
        return False
    
    # 获取照片文件
    photo_files = sorted(photos_dir.glob("*.jpg"))
    if not photo_files:
        print(f"❌ 照片目录为空: {photos_dir}")
        return False
    
    print(f"✓ 音频文件: {audio_file.name}")
    print(f"✓ 照片数量: {len(photo_files)}")
    print(f"✓ 输出目录: {output_dir}")
    
    try:
        # 创建合成器
        print("\n正在创建演讲合成器...")
        composer = LectureComposer(
            audio_file=audio_file,
            photo_files=photo_files,
            output_dir=output_dir
        )
        
        # 处理项目
        print("正在处理项目...")
        composer.process(title="v2.0功能测试", save=True)
        
        # 导出720p视频（无字幕）
        print("\n正在导出720p视频（无字幕）...")
        config_720p = VideoExportConfig(
            resolution="1280x720",
            enable_subtitles=False  # 先不生成字幕，节省时间
        )
        
        video_file_720p = composer.export_video(
            output_file=output_dir / "video_720p.mp4",
            config=config_720p
        )
        
        print(f"\n✅ 720p视频导出成功!")
        print(f"   文件: {video_file_720p}")
        print(f"   分辨率: 1280x720")
        
        # 获取视频信息
        from services.video.video_exporter import VideoExporter
        exporter = VideoExporter()
        info = exporter.get_video_info(video_file_720p)
        
        print(f"\n📊 视频信息:")
        print(f"   时长: {info['duration']:.1f}秒")
        print(f"   大小: {info['size'] / 1024 / 1024:.1f}MB")
        print(f"   比特率: {info['bitrate'] / 1000:.0f}kbps")
        print(f"   分辨率: {info['video']['width']}x{info['video']['height']}")
        print(f"   帧率: {info['video']['fps']:.1f}fps")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_subtitle_generation():
    """测试字幕生成功能"""
    print("\n" + "=" * 70)
    print("测试 2: 字幕生成功能")
    print("=" * 70)
    
    audio_file = project_root / "examples/fixtures/2025-10-24-15:15:15.mp3"
    output_dir = project_root / "examples/output/v2_test/subtitles"
    
    if not audio_file.exists():
        print(f"❌ 音频文件不存在: {audio_file}")
        return False
    
    print(f"✓ 音频文件: {audio_file.name}")
    print(f"✓ 输出目录: {output_dir}")
    
    try:
        from services.subtitle.subtitle_service import SubtitleService, SubtitleConfig
        
        # 检查Whisper是否可用
        print("\n正在检查Whisper安装...")
        config = SubtitleConfig(model="base", language="zh")
        service = SubtitleService(config)
        
        if service.whisper is None:
            print("❌ Whisper未安装，跳过字幕测试")
            print("   请运行: pip install openai-whisper")
            return False
        
        print("✓ Whisper已安装")
        
        # 生成字幕
        print("\n正在生成字幕（这可能需要几分钟）...")
        print("提示: 首次运行会下载Whisper模型，请耐心等待...")
        
        subtitle_file = service.generate_subtitles(audio_file, output_dir)
        
        if subtitle_file:
            print(f"\n✅ 字幕生成成功!")
            print(f"   SRT文件: {subtitle_file}")
            print(f"   ASS文件: {subtitle_file.with_suffix('.ass')}")
            
            # 显示字幕预览
            print("\n📝 字幕内容预览:")
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 显示前3个字幕片段
                preview_lines = lines[:min(15, len(lines))]
                print("".join(preview_lines))
                if len(lines) > 15:
                    print("...")
            
            return True
        else:
            print("❌ 字幕生成失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_video_with_subtitles():
    """测试带字幕的视频导出"""
    print("\n" + "=" * 70)
    print("测试 3: 720p视频导出（带字幕）")
    print("=" * 70)
    
    audio_file = project_root / "examples/fixtures/2025-10-24-15:15:15.mp3"
    photos_dir = project_root / "examples/fixtures/sample-photos"
    output_dir = project_root / "examples/output/v2_test"
    
    # 检查Whisper是否可用
    try:
        from services.subtitle.subtitle_service import SubtitleService
        service = SubtitleService()
        if service.whisper is None:
            print("❌ Whisper未安装，跳过字幕视频测试")
            print("   请运行: pip install openai-whisper")
            return False
    except ImportError:
        print("❌ 字幕服务不可用，跳过测试")
        return False
    
    try:
        photo_files = sorted(photos_dir.glob("*.jpg"))
        
        print(f"✓ 音频文件: {audio_file.name}")
        print(f"✓ 照片数量: {len(photo_files)}")
        print(f"✓ 输出目录: {output_dir}")
        
        # 创建合成器
        print("\n正在创建演讲合成器...")
        composer = LectureComposer(
            audio_file=audio_file,
            photo_files=photo_files,
            output_dir=output_dir
        )
        
        # 处理项目
        print("正在处理项目...")
        composer.process(title="v2.0字幕测试", save=True)
        
        # 导出带字幕的视频
        print("\n正在导出720p视频（带字幕）...")
        print("注意: 这个过程包含字幕生成和嵌入，可能需要5-10分钟...")
        
        config_with_subtitles = VideoExportConfig(
            resolution="1280x720",
            enable_subtitles=True  # 启用字幕
        )
        
        video_file = composer.export_video(
            output_file=output_dir / "video_720p_with_subtitles.mp4",
            config=config_with_subtitles
        )
        
        print(f"\n✅ 带字幕视频导出成功!")
        print(f"   文件: {video_file}")
        
        # 获取视频信息
        from services.video.video_exporter import VideoExporter
        exporter = VideoExporter()
        info = exporter.get_video_info(video_file)
        
        print(f"\n📊 视频信息:")
        print(f"   时长: {info['duration']:.1f}秒")
        print(f"   大小: {info['size'] / 1024 / 1024:.1f}MB")
        print(f"   分辨率: {info['video']['width']}x{info['video']['height']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_comparison_1080p_vs_720p():
    """对比测试：1080p vs 720p"""
    print("\n" + "=" * 70)
    print("测试 4: 分辨率对比（1080p vs 720p）")
    print("=" * 70)
    
    audio_file = project_root / "examples/fixtures/2025-10-24-15:15:15.mp3"
    photos_dir = project_root / "examples/fixtures/sample-photos"
    output_dir = project_root / "examples/output/v2_test"
    
    try:
        photo_files = sorted(photos_dir.glob("*.jpg"))
        
        composer = LectureComposer(
            audio_file=audio_file,
            photo_files=photo_files,
            output_dir=output_dir
        )
        composer.process(title="分辨率对比测试", save=True)
        
        # 导出1080p
        print("\n正在导出1080p视频...")
        config_1080p = VideoExportConfig(
            resolution="1920x1080",
            video_bitrate="5000k",
            enable_subtitles=False
        )
        video_1080p = composer.export_video(
            output_file=output_dir / "video_1080p.mp4",
            config=config_1080p
        )
        
        # 导出720p
        print("\n正在导出720p视频...")
        config_720p = VideoExportConfig(
            resolution="1280x720",
            video_bitrate="3000k",
            enable_subtitles=False
        )
        video_720p = composer.export_video(
            output_file=output_dir / "video_720p_compare.mp4",
            config=config_720p
        )
        
        # 对比信息
        from services.video.video_exporter import VideoExporter
        exporter = VideoExporter()
        
        info_1080p = exporter.get_video_info(video_1080p)
        info_720p = exporter.get_video_info(video_720p)
        
        print("\n📊 对比结果:")
        print("\n1080p:")
        print(f"   分辨率: {info_1080p['video']['width']}x{info_1080p['video']['height']}")
        print(f"   文件大小: {info_1080p['size'] / 1024 / 1024:.1f}MB")
        print(f"   比特率: {info_1080p['bitrate'] / 1000:.0f}kbps")
        
        print("\n720p:")
        print(f"   分辨率: {info_720p['video']['width']}x{info_720p['video']['height']}")
        print(f"   文件大小: {info_720p['size'] / 1024 / 1024:.1f}MB")
        print(f"   比特率: {info_720p['bitrate'] / 1000:.0f}kbps")
        
        size_reduction = (1 - info_720p['size'] / info_1080p['size']) * 100
        print(f"\n💡 720p文件大小减少: {size_reduction:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("🎬 演讲视频合成系统 v2.0 功能测试")
    print("=" * 70)
    
    results = []
    
    # 测试1: 720p视频导出
    results.append(("720p视频导出", test_720p_video_export()))
    
    # 测试2: 字幕生成
    results.append(("字幕生成", test_subtitle_generation()))
    
    # 测试3: 带字幕视频（可选，耗时较长）
    print("\n" + "=" * 70)
    response = input("是否测试带字幕的视频导出？（需要5-10分钟）[y/N]: ")
    if response.lower() == 'y':
        results.append(("带字幕视频", test_video_with_subtitles()))
    
    # 测试4: 分辨率对比
    print("\n" + "=" * 70)
    response = input("是否对比1080p vs 720p？（需要额外时间）[y/N]: ")
    if response.lower() == 'y':
        results.append(("分辨率对比", test_comparison_1080p_vs_720p()))
    
    # 输出测试总结
    print("\n" + "=" * 70)
    print("📊 测试总结")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请查看上面的详细信息")
    
    print("=" * 70)
    
    # 输出查看结果的建议
    output_dir = project_root / "examples/output/v2_test"
    print(f"\n📁 输出文件位置: {output_dir}")
    print("\n💡 如何查看结果:")
    print("   1. 打开输出目录查看生成的视频文件")
    print("   2. 使用VLC或其他播放器播放视频")
    print("   3. 检查字幕是否正确显示")
    print("   4. 对比不同分辨率的文件大小和质量")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
