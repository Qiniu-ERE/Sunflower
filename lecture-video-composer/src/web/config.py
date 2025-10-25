"""
Web服务器配置文件
"""
import os
from pathlib import Path
from typing import Optional

class Config:
    """基础配置类"""
    
    # 应用基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = False
    TESTING = False
    
    # 项目根目录
    BASE_DIR = Path(__file__).parent.parent.parent.parent
    
    # Web应用目录
    WEB_DIR = Path(__file__).parent
    STATIC_DIR = WEB_DIR / 'static'
    TEMPLATE_DIR = WEB_DIR / 'templates'
    
    # 数据存储目录
    DATA_DIR = BASE_DIR / 'data'
    UPLOAD_DIR = DATA_DIR / 'uploads'
    PROJECTS_DIR = DATA_DIR / 'projects'
    EXPORTS_DIR = DATA_DIR / 'exports'
    TEMP_DIR = DATA_DIR / 'temp'
    
    # 会话配置
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = TEMP_DIR / 'sessions'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = 3600 * 24  # 24小时
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.flac'}
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}
    
    # CORS配置
    CORS_ORIGINS = ['http://localhost:*', 'http://127.0.0.1:*']
    
    # 视频导出配置
    DEFAULT_VIDEO_RESOLUTION = '1920x1080'
    DEFAULT_VIDEO_FPS = 30
    DEFAULT_VIDEO_BITRATE = '5000k'
    
    # 播放器配置
    DEFAULT_TRANSITION_DURATION = 0.5  # 秒
    DEFAULT_VOLUME = 1.0
    PLAYBACK_UPDATE_INTERVAL = 0.05  # 20fps 状态更新
    
    # 任务配置
    MAX_CONCURRENT_EXPORTS = 2
    TASK_CLEANUP_INTERVAL = 3600  # 1小时
    TASK_MAX_AGE = 86400  # 24小时
    
    @classmethod
    def init_app(cls, app):
        """初始化应用配置"""
        # 创建必要的目录
        for dir_path in [
            cls.DATA_DIR,
            cls.UPLOAD_DIR,
            cls.PROJECTS_DIR,
            cls.EXPORTS_DIR,
            cls.TEMP_DIR,
            cls.SESSION_FILE_DIR
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    ENV = 'production'
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # 生产环境额外配置
        import logging
        from logging.handlers import RotatingFileHandler
        
        # 配置日志
        log_dir = cls.DATA_DIR / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Lecture Video Composer startup')


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    
    # 使用临时目录进行测试
    import tempfile
    TEMP_TEST_DIR = Path(tempfile.mkdtemp())
    DATA_DIR = TEMP_TEST_DIR / 'data'
    UPLOAD_DIR = DATA_DIR / 'uploads'
    PROJECTS_DIR = DATA_DIR / 'projects'
    EXPORTS_DIR = DATA_DIR / 'exports'
    TEMP_DIR = DATA_DIR / 'temp'
    SESSION_FILE_DIR = TEMP_DIR / 'sessions'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> Config:
    """获取配置对象"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    return config.get(config_name, config['default'])
