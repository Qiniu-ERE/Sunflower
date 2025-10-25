#!/usr/bin/env python3
"""
Lecture Player Example
演讲播放器示例 - 实时播放演讲录音和照片同步
"""

import sys
import json
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from core.player import SyncCoordinator, PlaybackConfig, DisplayConfig, SyncConfig

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='播放演讲录音和照片同步',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 播放演讲（使用metadata.json中的时间轴）
  python play_lecture.py ../fixtures/2025-10-24-15:15:15.mp3 ../fixtures/sample-photos/
  
  # 指定时间轴文件
  python play_lecture.py audio.mp3 photos/ --timeline timeline.json
  
  # 调整音量
  python play_lecture.py audio.mp3 photos/ --volume 0.5
        '''
    )
    
    parser.add_argument('audio_file', type=Path, help='音频文件路径')
    parser.add_argument('photos_dir', type=Path, help='照片目录')
    parser.add_argument('--timeline', type=Path, help='时间轴JSON文件（可选）')
    parser.add_argument('--volume', type=float, default=1.0, help='音量 (0.0-1.0)')
    parser.add_argument('--window-size', type=str, default='1280x720', help='窗口大小 (WIDTHxHEIGHT)')
    
    args = parser.parse_args()
    
    try:
        # 验证输入
        if not args.audio_file.exists():
            print(f"错误: 音频文件不存在: {args.audio_file}")
            return 1
        
        if not args.photos_dir.exists():
            print(f"错误: 照片目录不存在: {args.photos_dir}")
            return 1
        
        # 解析窗口大小
        try:
            width, height = map(int, args.window_size.split('x'))
            window_size = (width, height)
        except:
            print(f"错误: 无效的窗口大小: {args.window_size}")
            return 1
        
        # 加载时间轴
        timeline_items = []
        
        if args.timeline and args.timeline.exists():
            # 从指定文件加载
            logger.info(f"Loading timeline from: {args.timeline}")
            with open(args.timeline, 'r', encoding='utf-8') as f:
                data = json.load(f)
                timeline_items = data.get('timeline', [])
        else:
            # 尝试从照片目录的metadata.json加载
            metadata_file = args.photos_dir.parent / 'metadata.json'
            if metadata_file.exists():
                logger.info(f"Loading timeline from: {metadata_file}")
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    timeline_items = data.get('timeline', [])
            else:
                # 创建简单的均匀时间轴
                logger.warning("No timeline file found, creating uniform timeline")
                photos = sorted(args.photos_dir.glob('*.jpg'))
                if not photos:
                    print(f"错误: 照片目录中没有找到照片: {args.photos_dir}")
                    return 1
                
                # 假设每张照片显示30秒
                timeline_items = [
                    {'photo': photo.name, 'duration': 30.0}
                    for photo in photos
                ]
        
        if not timeline_items:
            print("错误: 没有时间轴数据")
            return 1
        
        print(f"\n{'='*60}")
        print(f"  演讲播放器")
        print(f"{'='*60}")
        print(f"音频文件: {args.audio_file.name}")
        print(f"照片目录: {args.photos_dir}")
        print(f"照片数量: {len(timeline_items)}")
        print(f"窗口大小: {window_size[0]}x{window_size[1]}")
        print(f"音量: {args.volume:.1f}")
        print(f"{'='*60}\n")
        
        # 创建配置
        playback_config = PlaybackConfig(volume=args.volume)
        display_config = DisplayConfig(window_size=window_size)
        sync_config = SyncConfig()
        
        # 创建协调器
        coordinator = SyncCoordinator(
            playback_config=playback_config,
            display_config=display_config,
            sync_config=sync_config
        )
        
        # 添加同步回调
        def on_sync_update(position, photo):
            # 显示进度
            duration = coordinator.get_duration()
            progress = (position / duration * 100) if duration > 0 else 0
            photo_name = photo.path.name if photo else "无"
            
            # 格式化时间
            pos_min, pos_sec = divmod(int(position), 60)
            dur_min, dur_sec = divmod(int(duration), 60)
            
            print(f"\r[{pos_min:02d}:{pos_sec:02d}/{dur_min:02d}:{dur_sec:02d}] "
                  f"进度: {progress:5.1f}% | 照片: {photo_name:<40}",
                  end='', flush=True)
        
        coordinator.add_sync_callback(on_sync_update)
        
        # 添加错误回调
        def on_error(error):
            print(f"\n错误: {error}")
        
        coordinator.add_error_callback(on_error)
        
        # 加载内容
        print("正在加载...")
        if not coordinator.load(args.audio_file, timeline_items, args.photos_dir):
            print("加载失败")
            return 1
        
        duration = coordinator.get_duration()
        dur_min, dur_sec = divmod(int(duration), 60)
        print(f"总时长: {dur_min:02d}:{dur_sec:02d}")
        print(f"\n开始播放...\n")
        print("控制:")
        print("  Ctrl+C - 停止播放")
        print()
        
        # 开始播放
        if not coordinator.play():
            print("播放失败")
            return 1
        
        # 等待播放完成
        try:
            import time
            while coordinator.is_playing():
                time.sleep(0.1)
            
            print("\n\n播放完成!")
            
        except KeyboardInterrupt:
            print("\n\n正在停止...")
            coordinator.stop()
        
        # 清理
        coordinator.cleanup()
        print("已清理资源\n")
        
        return 0
        
    except Exception as e:
        print(f"\n错误: {e}")
        logger.exception("播放失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
