"""
Subtitle Service Factory
字幕服务工厂 - 根据配置创建合适的字幕服务
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SubtitleServiceFactory:
    """字幕服务工厂"""
    
    @staticmethod
    def create_service(service_type: str = None):
        """
        创建字幕服务实例
        
        Args:
            service_type: 服务类型 ('qiniu' 或 'whisper')
                         如果为None，则从环境变量SUBTITLE_SERVICE读取
        
        Returns:
            字幕服务实例
        """
        # 如果未指定服务类型，从环境变量读取
        if service_type is None:
            service_type = os.getenv('SUBTITLE_SERVICE', 'qiniu').lower()
        
        logger.info(f"创建字幕服务: {service_type}")
        
        if service_type == 'qiniu':
            return SubtitleServiceFactory._create_qiniu_service()
        elif service_type == 'whisper':
            return SubtitleServiceFactory._create_whisper_service()
        else:
            logger.warning(f"未知的字幕服务类型: {service_type}，使用默认(qiniu)")
            return SubtitleServiceFactory._create_qiniu_service()
    
    @staticmethod
    def _create_qiniu_service():
        """创建七牛云ASR服务"""
        try:
            from .qiniu_asr_service import QiniuASRService
            
            # 从环境变量获取认证信息（优先AK/SK，其次Token）
            access_key = os.getenv('QINIU_ACCESS_KEY')
            secret_key = os.getenv('QINIU_SECRET_KEY')
            api_key = os.getenv('QINIU_AI_API_KEY')
            
            # 优先使用AK/SK认证
            if access_key and secret_key:
                service = QiniuASRService(
                    access_key=access_key, 
                    secret_key=secret_key
                )
                logger.info("使用AK/SK认证创建七牛云ASR服务")
            elif api_key:
                service = QiniuASRService(api_key=api_key)
                logger.info("使用Token认证创建七牛云ASR服务")
            else:
                logger.warning(
                    "七牛云认证信息未设置！\n"
                    "请设置以下任一方式：\n"
                    "1. 设置 QINIU_ACCESS_KEY 和 QINIU_SECRET_KEY (AK/SK认证)\n"
                    "2. 设置 QINIU_AI_API_KEY (Token认证)\n"
                    "请在 .env 文件中设置或在环境变量中设置"
                )
                service = QiniuASRService()  # 创建无认证实例用于错误提示
            
            logger.info("七牛云ASR服务创建成功")
            return service
            
        except ImportError as e:
            logger.error(f"无法导入七牛云ASR服务: {e}")
            raise
    
    @staticmethod
    def _create_whisper_service():
        """创建Whisper服务"""
        try:
            from .subtitle_service import SubtitleService, SubtitleConfig
            
            # 从环境变量获取模型配置
            model = os.getenv('WHISPER_MODEL', 'base')
            
            config = SubtitleConfig(
                model=model,
                language='zh'
            )
            
            service = SubtitleService(config=config)
            logger.info(f"Whisper服务创建成功 (模型: {model})")
            return service
            
        except ImportError as e:
            logger.error(f"无法导入Whisper服务: {e}")
            raise
    
    @staticmethod
    def is_service_available(service_type: str = None) -> bool:
        """
        检查指定的字幕服务是否可用
        
        Args:
            service_type: 服务类型 ('qiniu' 或 'whisper')
        
        Returns:
            服务是否可用
        """
        if service_type is None:
            service_type = os.getenv('SUBTITLE_SERVICE', 'qiniu').lower()
        
        try:
            service = SubtitleServiceFactory.create_service(service_type)
            
            # 检查七牛云服务的认证信息
            if service_type == 'qiniu':
                if hasattr(service, '_has_valid_auth'):
                    # 使用新的认证检查方法
                    if service._has_valid_auth():
                        return True
                    else:
                        logger.warning("七牛云认证信息未设置或无效")
                        return False
                else:
                    # 兼容旧版本的检查方法
                    api_key = os.getenv('QINIU_AI_API_KEY')
                    access_key = os.getenv('QINIU_ACCESS_KEY')
                    secret_key = os.getenv('QINIU_SECRET_KEY')
                    
                    if (api_key and api_key.strip()) or (access_key and secret_key):
                        return True
                    else:
                        logger.warning("七牛云API密钥未设置")
                        return False
            
            # 检查Whisper服务
            elif service_type == 'whisper':
                if hasattr(service, 'whisper') and service.whisper:
                    return True
                else:
                    logger.warning("Whisper未安装")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查字幕服务可用性失败: {e}")
            return False


def get_subtitle_service():
    """
    获取字幕服务实例（便捷函数）
    
    Returns:
        字幕服务实例
    """
    return SubtitleServiceFactory.create_service()


# 测试代码
if __name__ == '__main__':
    import sys
    
    # 测试七牛云服务
    print("测试七牛云ASR服务...")
    if SubtitleServiceFactory.is_service_available('qiniu'):
        print("✅ 七牛云ASR服务可用")
        service = SubtitleServiceFactory.create_service('qiniu')
        print(f"   服务实例: {service}")
    else:
        print("❌ 七牛云ASR服务不可用")
    
    print()
    
    # 测试Whisper服务
    print("测试Whisper服务...")
    if SubtitleServiceFactory.is_service_available('whisper'):
        print("✅ Whisper服务可用")
        service = SubtitleServiceFactory.create_service('whisper')
        print(f"   服务实例: {service}")
    else:
        print("❌ Whisper服务不可用")
    
    print()
    
    # 测试默认服务
    print("测试默认服务...")
    try:
        service = get_subtitle_service()
        print(f"✅ 默认服务创建成功: {type(service).__name__}")
    except Exception as e:
        print(f"❌ 默认服务创建失败: {e}")
