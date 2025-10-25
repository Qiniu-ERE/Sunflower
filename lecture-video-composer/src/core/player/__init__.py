"""
Player Module
播放器模块 - 实时播放演讲录音和照片同步

v2.2 增强功能:
- 倍速播放支持 (0.5x - 2.0x)
- 过渡动画效果 (淡入淡出、交叉淡化、滑动)
- 过渡帧生成API
"""

from .playback_controller import PlaybackController, PlaybackConfig, PlaybackState
from .photo_display import PhotoDisplayManager, DisplayConfig, PhotoItem, TransitionType
from .sync_coordinator import SyncCoordinator, SyncConfig

__all__ = [
    # 播放控制
    'PlaybackController',
    'PlaybackConfig',
    'PlaybackState',
    
    # 照片显示
    'PhotoDisplayManager',
    'DisplayConfig',
    'PhotoItem',
    'TransitionType',
    
    # 同步协调
    'SyncCoordinator',
    'SyncConfig'
]

__version__ = '2.2.0'
