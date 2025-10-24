"""
测试视频导出功能
Test Video Export Feature
"""

import sys
from pathlib import Path

# 添加项目路径到系统路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from core.lecture_composer import LectureComposer
from services.video.video_exporter import VideoExporter, VideoExportConfig


def test_ffmpeg_check():
    """测试 FFmpeg 是否正确安装"""
    print("\n" + "=" * 60)
    print("测试 1: 检查 FFmpeg 安装")
    print("=" * 60)
    
    try:
        exporter = VideoExporter()
        print("✅ FFmpeg 已正确安装并可用")
        return True
    except RuntimeError as e:
        print(f"❌ FFmpeg 检查失败: {e}")
        return False


def test_video_export_config():
    """测试视频导出配置"""
    print("\n" + "=" * 60)
    print("测试 2: 视频导出配置")
    print("=" * 60)
    
    # 默认配置
    config1 = VideoExportConfig()
    print(f"\n默认配置:")
    print(f"  分辨率: {config1.resolution}")
    print(f"  帧率: {config1.fps}")
    print(f"  视频编码器: {config1.video_codec}")
    print(f"  音频编码器: {config1.audio_codec}")
    print(f"  视频比特率: {config1.video_bitrate}")
    print(f"  音频比特率: {config1.audio_bitrate}")
    print(f"  编码预设: {config1.preset}")
    print(f"  质量因子(CRF): {config1.crf}")
    
    # 自定义配置
    config2 = VideoExportConfig(
        resolution="1280x720",
        fps=24,
        video_bitrate="3000k",
        preset="fast",
        crf=20
    )
    print(f"\n自定义配置 (720p, 24fps, 快速编码):")
    print(f"  分辨率: {config2.resolution}")
    print(f"  帧率: {config2.fps}")
    print(f"  视频比特率: {config2.video_bitrate}")
    print(f"  编码预设: {config2.preset}")
    print(f"  质量因子(CRF): {config2.crf}")
    
    # 高质量配置
    config3 = VideoExportConfig(
        resolution="3840x2160",
        fps=60,
        video_bitrate="20000k",
        preset="slow",
        crf=18
    )
    print(f"\n高质量配置 (4K, 60fps, 慢速编码):")
    print(f"  分辨率: {config3.resolution}")
    print(f"  帧率: {config3.fps}")
    print(f"  视频比特率: {config3.video_bitrate}")
    print(f"  编码预设: {config3.preset}")
    print(f"  质量因子(CRF): {config3.crf}")
    
    print("\n✅ 视频导出配置测试完成")
    return True


def test_full_workflow():
    """测试完整的视频导出流程"""
    print("\n" + "=" * 60)
    print("测试 3: 完整视频导出流程")
    print("=" * 60)
    
    # 设置文件路径
    fixtures_dir = project_root / "examples" / "fixtures"
    audio_file = fixtures_dir / "2025-10-24-15:15:15.mp3"
    photos_dir = fixtures_dir / "sample-photos"
    output_dir = project_root / "examples" / "output" / "video_export_test"
    
    # 检查测试文件是否存在
    if not audio_file.exists():
        print(f"❌ 音频文件不存在: {audio_file}")
        print("   请先准备测试音频文件")
        return False
    
    photo_files = sorted(photos_dir.glob("*.jpg"))
    if not photo_files:
        print(f"❌ 照片文件不存在: {photos_dir}")
        print("   请先准备测试照片文件")
        return False
    
    print(f"\n找到音频文件: {audio_file.name}")
    print(f"找到 {len(photo_files)} 张照片")
    
    try:
        # 创建合成器
        print("\n步骤 1: 创建合成器并处理项目...")
        composer = LectureComposer(
            audio_file=audio_file,
            photo_files=photo_files,
            output_dir=output_dir
        )
        
        # 处理项目
        metadata = composer.process(title="视频导出测试", save=True)
        print("✅ 项目处理完成")
        
        # 导出视频 - 默认配置
        print("\n步骤 2: 导出视频 (默认配置: 1080p, 30fps)...")
        video_file = composer.export_video()
        print(f"✅ 视频导出成功: {video_file}")
        
        # 获取视频信息
        print("\n步骤 3: 获取视频信息...")
        exporter = VideoExporter()
        video_info = exporter.get_video_info(video_file)
        
        print(f"\n视频信息:")
        print(f"  文件大小: {video_info['size'] / 1024 / 1024:.2f} MB")
        print(f"  时长: {video_info['duration']:.2f} 秒")
        print(f"  比特率: {video_info['bitrate'] / 1000:.0f} kbps")
        
        if video_info['video']:
            print(f"\n  视频流:")
            print(f"    编码器: {video_info['video']['codec']}")
            print(f"    分辨率: {video_info['video']['width']}x{video_info['video']['height']}")
            print(f"    帧率: {video_info['video']['fps']:.2f} fps")
        
        if video_info['audio']:
            print(f"\n  音频流:")
            print(f"    编码器: {video_info['audio']['codec']}")
            print(f"    采样率: {video_info['audio']['sample_rate']} Hz")
            print(f"    声道数: {video_info['audio']['channels']}")
        
        print("\n✅ 完整流程测试成功!")
        print(f"\n输出目录: {output_dir}")
        print(f"视频文件: {video_file}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_custom_config_export():
    """测试自定义配置的视频导出"""
    print("\n" + "=" * 60)
    print("测试 4: 自定义配置视频导出")
    print("=" * 60)
    
    # 设置文件路径
    fixtures_dir = project_root / "examples" / "fixtures"
    audio_file = fixtures_dir / "2025-10-24-15:15:15.mp3"
    photos_dir = fixtures_dir / "sample-photos"
    output_dir = project_root / "examples" / "output" / "video_export_test"
    
    if not audio_file.exists() or not list(photos_dir.glob("*.jpg")):
        print("⚠️  测试文件不存在，跳过此测试")
        return True
    
    try:
        photo_files = sorted(photos_dir.glob("*.jpg"))
        composer = LectureComposer(
            audio_file=audio_file,
            photo_files=photo_files,
            output_dir=output_dir
        )
        
        # 确保项目已处理
        if composer.timeline is None:
            composer.process(title="自定义配置测试", save=False)
        
        # 720p 配置
        print("\n导出 720p 视频...")
        config_720p = VideoExportConfig(
            resolution="1280x720",
            fps=24,
            video_bitrate="2500k",
            preset="fast"
        )
        video_720p = composer.export_video(
            output_file=output_dir / "video_720p.mp4",
            config=config_720p
        )
        print(f"✅ 720p 视频导出: {video_720p}")
        
        # 获取文件大小
        size_720p = video_720p.stat().st_size / 1024 / 1024
        print(f"   文件大小: {size_720p:.2f} MB")
        
        print("\n✅ 自定义配置测试成功!")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("演讲视频合成系统 - 视频导出功能测试")
    print("Lecture Video Composer - Video Export Feature Test")
    print("=" * 70)
    
    # 运行所有测试
    results = []
    
    results.append(("FFmpeg 检查", test_ffmpeg_check()))
    results.append(("视频导出配置", test_video_export_config()))
    
    # 只有当 FFmpeg 可用时才运行实际导出测试
    if results[0][1]:
        results.append(("完整视频导出流程", test_full_workflow()))
        results.append(("自定义配置导出", test_custom_config_export()))
    
    # 打印测试总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请检查错误信息")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
