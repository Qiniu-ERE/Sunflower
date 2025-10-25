#!/usr/bin/env python3
"""
测试播放器增强功能
- 倍速播放
- 过渡动画效果
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from core.player import (
    PlaybackController, PlaybackConfig,
    PhotoDisplayManager, DisplayConfig, TransitionType,
    SyncCoordinator, SyncConfig
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_playback_speed():
    """测试倍速播放功能"""
    print("\n" + "="*60)
    print("测试 1: 倍速播放功能")
    print("="*60)
    
    # 创建播放控制器
    config = PlaybackConfig(volume=0.8, speed=1.0)
    controller = PlaybackController(config)
    
    # 测试不同速度
    speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    
    print("\n支持的播放速度:")
    for speed in speeds:
        result = controller.set_speed(speed)
        current = controller.get_speed()
        status = "✓" if result else "✗"
        print(f"  {status} {speed:.2f}x - 当前速度: {current:.2f}x")
    
    # 测试循环切换速度
    print("\n测试循环切换速度:")
    for i in range(len(speeds) + 2):
        new_speed = controller.cycle_speed(speeds)
        print(f"  第{i+1}次切换 -> {new_speed:.2f}x")
    
    # 测试无效速度
    print("\n测试边界情况:")
    invalid_speeds = [0.3, 2.5, -1.0, 100.0]
    for speed in invalid_speeds:
        result = controller.set_speed(speed)
        status = "✗ 正确拒绝" if not result else "✓ 意外接受"
        print(f"  {status}: {speed:.2f}x")
    
    controller.cleanup()
    print("\n✓ 倍速播放测试完成")


def test_transition_effects():
    """测试过渡动画效果"""
    print("\n" + "="*60)
    print("测试 2: 过渡动画效果")
    print("="*60)
    
    # 创建照片显示管理器
    transitions = [
        TransitionType.NONE,
        TransitionType.FADE,
        TransitionType.CROSSFADE,
        TransitionType.SLIDE
    ]
    
    for transition in transitions:
        config = DisplayConfig(
            transition_type=transition,
            transition_duration=0.5,
            transition_fps=30,
            enable_transitions=True
        )
        
        manager = PhotoDisplayManager(config)
        
        print(f"\n过渡效果: {transition.value}")
        print(f"  - 时长: {config.transition_duration}s")
        print(f"  - 帧率: {config.transition_fps} fps")
        print(f"  - 预期帧数: {int(config.transition_duration * config.transition_fps)}")
        print(f"  - 启用: {'是' if config.enable_transitions else '否'}")
        
        manager.cleanup()
    
    print("\n✓ 过渡效果测试完成")


def test_transition_frame_generation(photos_dir: Path):
    """测试过渡帧生成"""
    print("\n" + "="*60)
    print("测试 3: 过渡帧生成")
    print("="*60)
    
    if not photos_dir.exists():
        print(f"⚠ 照片目录不存在: {photos_dir}")
        return
    
    # 获取前两张照片
    photos = sorted(photos_dir.glob('*.jpg'))[:2]
    if len(photos) < 2:
        print(f"⚠ 需要至少2张照片进行测试，当前只有 {len(photos)} 张")
        return
    
    print(f"\n使用照片:")
    print(f"  1. {photos[0].name}")
    print(f"  2. {photos[1].name}")
    
    # 测试不同过渡效果
    for transition_type in [TransitionType.CROSSFADE, TransitionType.FADE]:
        config = DisplayConfig(
            transition_type=transition_type,
            transition_duration=1.0,
            transition_fps=10,  # 降低帧率以便测试
            window_size=(800, 600)
        )
        
        manager = PhotoDisplayManager(config)
        
        # 创建时间轴
        timeline_items = [
            {'photo': photos[0].name, 'duration': 5.0},
            {'photo': photos[1].name, 'duration': 5.0}
        ]
        
        manager.load_timeline(timeline_items, photos_dir)
        
        # 确保照片已加载
        time.sleep(0.5)
        
        # 获取照片项
        photo1 = manager._photos[0] if len(manager._photos) > 0 else None
        photo2 = manager._photos[1] if len(manager._photos) > 1 else None
        
        if photo1 and photo2 and photo1.image and photo2.image:
            print(f"\n生成 {transition_type.value} 过渡帧:")
            frames = manager.generate_transition_frames(photo1, photo2)
            print(f"  ✓ 生成了 {len(frames)} 帧")
            print(f"  - 每帧尺寸: {frames[0].size if frames else 'N/A'}")
            print(f"  - 总时长: {config.transition_duration}s @ {config.transition_fps}fps")
        else:
            print(f"  ⚠ 照片加载失败")
        
        manager.cleanup()
    
    print("\n✓ 过渡帧生成测试完成")


def test_integrated_features(audio_file: Path, photos_dir: Path):
    """测试集成功能"""
    print("\n" + "="*60)
    print("测试 4: 集成功能测试")
    print("="*60)
    
    if not audio_file.exists():
        print(f"⚠ 音频文件不存在: {audio_file}")
        return
    
    if not photos_dir.exists():
        print(f"⚠ 照片目录不存在: {photos_dir}")
        return
    
    # 创建配置
    playback_config = PlaybackConfig(
        volume=0.7,
        speed=1.5,  # 1.5倍速
        speed_change_smooth=True
    )
    
    display_config = DisplayConfig(
        window_size=(1280, 720),
        transition_type=TransitionType.CROSSFADE,
        transition_duration=0.8,
        transition_fps=30,
        preload_count=3,
        enable_transitions=True
    )
    
    sync_config = SyncConfig(
        update_interval=0.05,
        auto_correction=True
    )
    
    # 创建协调器
    coordinator = SyncCoordinator(
        playback_config=playback_config,
        display_config=display_config,
        sync_config=sync_config
    )
    
    print(f"\n配置:")
    print(f"  播放速度: {playback_config.speed}x")
    print(f"  过渡效果: {display_config.transition_type.value}")
    print(f"  过渡时长: {display_config.transition_duration}s")
    print(f"  预加载数量: {display_config.preload_count}")
    
    # 创建简单时间轴
    photos = sorted(photos_dir.glob('*.jpg'))[:5]
    timeline_items = [
        {'photo': photo.name, 'duration': 10.0}
        for photo in photos
    ]
    
    print(f"\n加载 {len(timeline_items)} 张照片...")
    
    # 加载
    success = coordinator.load(
        audio_file=audio_file,
        timeline_items=timeline_items,
        photos_dir=photos_dir
    )
    
    if success:
        print("✓ 加载成功")
        
        # 添加进度回调
        def on_sync_update(position: float, photo):
            photo_name = photo.path.name if photo else "None"
            speed = coordinator.playback.get_speed()
            print(f"\r[{position:6.2f}s @ {speed:.1f}x] {photo_name}", end='', flush=True)
        
        coordinator.add_sync_callback(on_sync_update)
        
        print("\n\n开始模拟播放（5秒）...")
        coordinator.play()
        
        # 模拟播放5秒
        time.sleep(2)
        
        # 测试速度切换
        print("\n\n切换到2倍速...")
        coordinator.playback_controller.set_speed(2.0)
        time.sleep(2)
        
        # 停止
        print("\n\n停止播放")
        coordinator.stop()
        
        print("\n✓ 集成测试完成")
    else:
        print("✗ 加载失败")
    
    coordinator.cleanup()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试播放器增强功能')
    parser.add_argument(
        '--audio',
        type=Path,
        default=Path('examples/fixtures/2025-10-24-15:15:15.mp3'),
        help='音频文件路径'
    )
    parser.add_argument(
        '--photos',
        type=Path,
        default=Path('examples/fixtures/sample-photos'),
        help='照片目录路径'
    )
    parser.add_argument(
        '--test',
        choices=['all', 'speed', 'transition', 'frames', 'integrated'],
        default='all',
        help='要运行的测试'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("播放器增强功能测试")
    print("="*60)
    print(f"\n音频文件: {args.audio}")
    print(f"照片目录: {args.photos}")
    
    try:
        if args.test in ['all', 'speed']:
            test_playback_speed()
        
        if args.test in ['all', 'transition']:
            test_transition_effects()
        
        if args.test in ['all', 'frames']:
            test_transition_frame_generation(args.photos)
        
        if args.test in ['all', 'integrated']:
            test_integrated_features(args.audio, args.photos)
        
        print("\n" + "="*60)
        print("✓ 所有测试完成")
        print("="*60 + "\n")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n中断测试")
        return 1
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
