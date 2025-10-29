#!/usr/bin/env python3
"""
测试照片上传自动重命名功能
"""
import requests
import os
from pathlib import Path

# 配置
BASE_URL = "http://localhost:5000"
SESSION_ID = "997c9be9-832d-413c-9a07-63290a744a6b"

# 测试文件路径
TEST_PHOTOS = [
    "examples/fixtures/sample-photos/2025-10-24-15:15:15.jpg",
    "examples/fixtures/sample-photos/2025-10-24-15:15:55.jpg",
]

def test_photo_upload():
    """测试照片上传"""
    print("=" * 60)
    print("测试照片上传自动重命名功能")
    print("=" * 60)
    
    # 准备上传文件
    files = []
    for photo_path in TEST_PHOTOS:
        if os.path.exists(photo_path):
            # 使用任意文件名（模拟用户上传）
            original_name = Path(photo_path).name
            test_name = f"test_photo_{len(files) + 1}.jpg"
            files.append(
                ('files', (test_name, open(photo_path, 'rb'), 'image/jpeg'))
            )
            print(f"准备上传: {test_name} (原文件: {original_name})")
    
    if not files:
        print("错误: 没有找到测试文件")
        return
    
    # 上传照片
    print("\n上传照片...")
    response = requests.post(
        f"{BASE_URL}/api/file/upload/photos",
        files=files,
        data={'session_id': SESSION_ID}
    )
    
    # 关闭文件
    for _, (_, file_obj, _) in files:
        file_obj.close()
    
    # 检查响应
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 上传成功!")
        print(f"成功上传 {result['data']['count']} 个文件")
        
        print("\n上传的文件:")
        for file_info in result['data']['uploaded']:
            print(f"  原文件名: {file_info['filename']}")
            print(f"  新文件名: {file_info['saved_name']}")
            print(f"  文件大小: {file_info['size'] / 1024:.1f} KB")
            print()
    else:
        print(f"\n❌ 上传失败: {response.status_code}")
        print(response.text)

if __name__ == '__main__':
    test_photo_upload()
