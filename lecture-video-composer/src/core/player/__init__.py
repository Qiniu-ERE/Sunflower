"""
Player Module
播放器模块 - 实时播放演讲录音和照片同步
"""

from .playback_controller import PlaybackController, PlaybackConfig, PlaybackState
from .photo_display import PhotoDisplayManager, DisplayConfig, PhotoItem, TransitionType
from .sync_coordinator import SyncCoordinator, SyncConfig

__all__ = [
    'PlaybackController',
    'PlaybackConfig',
    'PlaybackState',
    'PhotoDisplayManager',
    'DisplayConfig',
    'PhotoItem',
    'TransitionType',
    'SyncCoordinator',
    'SyncConfig'
]
