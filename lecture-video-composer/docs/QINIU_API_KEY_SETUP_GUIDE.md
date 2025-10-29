# 七牛云API密钥获取指南

## 步骤1: 注册七牛云账号

1. **访问七牛云官网**: https://www.qiniu.com/
2. **点击注册**: 在页面右上角点击"注册"按钮
3. **填写注册信息**: 使用手机号或邮箱注册
4. **完成实名认证**: 按照提示完成企业或个人实名认证

## 步骤2: 开通AI Token API服务

1. **登录七牛云控制台**: https://portal.qiniu.com/
2. **导航到AI服务**: 在左侧菜单中寻找"AI服务"或"人工智能"
3. **找到AI Token API**: 点击进入AI Token API服务页面
4. **开通服务**: 点击"立即开通"或"申请开通"
5. **阅读并同意协议**: 查看服务协议并同意开通

## 步骤3: 获取API密钥

1. **进入API密钥管理**:
   - 在控制台左侧菜单寻找"密钥管理"或"Access Key"
   - 或者直接访问: https://portal.qiniu.com/user/key

2. **创建新的Access Key**:
   - 点击"创建密钥"或"新建Access Key"
   - 选择"AK/SK对"类型
   - 填写描述（可选，如：语音识别服务）
   - 复制生成的Access Key和Secret Key

3. **或者使用现有密钥**:
   - 如果你已经有Access Key/Secret Key对，可以直接使用

## 步骤4: 转换为AI Token

七牛云AI Token API使用Bearer Token认证，需要将AK/SK转换为Token：

### 方法1: 使用七牛云SDK自动转换
系统会自动处理AK/SK到Token的转换，你只需要在`.env`文件中设置正确的密钥即可。

### 方法2: 手动获取Token（备用方案）
如果自动转换不工作，可以手动获取Token：

```bash
# 安装七牛云Python SDK
pip install qiniu

# 使用以下Python代码获取Token
import qiniu
from qiniu import Auth

# 替换为你的AK和SK
access_key = "你的AccessKey"
secret_key = "你的SecretKey"

# 创建认证对象
q = Auth(access_key, secret_key)

# 生成管理Token（用于API调用）
token = q.token_of_request("https://ai.qiniuapi.com/v1/asr")
print(f"Token: {token}")
```

## 步骤5: 配置系统

### 方式A: 使用AK/SK配置（推荐）
编辑 `.env` 文件：
```env
QINIU_ACCESS_KEY=你的AccessKey
QINIU_SECRET_KEY=你的SecretKey
SUBTITLE_SERVICE=qiniu
```

### 方式B: 直接使用Token（如果手动获取）
```env
QINIU_AI_API_KEY=你的BearerToken
SUBTITLE_SERVICE=qiniu
```

## 验证配置

1. **保存**.env文件**
2. **测试配置**:
```bash
cd lecture-video-composer/src/services/subtitle
python subtitle_factory.py
```

成功的输出应该是：
```
测试七牛云ASR服务...
✅ 七牛云ASR服务可用
   服务实例: <qiniu_asr_service.QiniuASRService object at 0x...>
```

## 常见问题

### Q: 找不到AI Token API服务？
A: 可能需要联系七牛云客服开通AI服务权限，或者检查账户类型（可能需要企业认证）。

### Q: AK/SK无法认证？
A: 
1. 确认AK/SK没有多余的空格
2. 检查AK/SK是否已启用
3. 确认账户有足够的余额或信用额度

### Q: 仍然提示"bad token"？
A: 
1. 尝试手动获取Token（使用步骤4的方法2）
2. 检查网络连接和防火墙设置
3. 确认API服务已正确开通

### Q: 想使用免费方案？
A: 七牛云通常提供一定的免费额度，但需要先开通服务。查看官方定价页面了解详情。

## 费用说明

- AI Token API通常按调用次数或时长计费
- 新用户可能有免费额度
- 建议先测试小额使用，了解具体费用
- 查看官方定价: https://www.qiniu.com/prices/ai-token

## 备用方案

如果七牛云服务不适合，可以考虑：
1. **使用Whisper本地识别**: 修改`.env`中的`SUBTITLE_SERVICE=whisper`
2. **其他云服务**: 如阿里云、腾讯云的语音识别服务（需要相应修改代码）

## 技术支持

- 七牛云官方客服: 400-808-9176
- 技术文档: https://developer.qiniu.com/aitokenapi/12981/asr-tts-ocr-api
- 控制台: https://portal.qiniu.com/

---

完成以上步骤后，你应该能够成功使用七牛云ASR服务生成字幕了！
