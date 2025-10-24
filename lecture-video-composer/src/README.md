# 源代码目录

本目录包含演讲视频合成系统的所有源代码。

## 📁 目录结构

```
src/
├── core/              # 核心业务逻辑
│   ├── timeline/      # 时间轴同步引擎
│   ├── player/        # 播放管理器
│   └── exporter/      # 导出管理器
├── ui/                # 用户界面组件
│   ├── components/    # UI组件
│   ├── views/         # 页面视图
│   └── styles/        # 样式文件
├── services/          # 业务服务层
│   ├── audio/         # 音频服务
│   ├── image/         # 图片服务
│   └── metadata/      # 元数据服务
├── utils/             # 工具函数
│   ├── parser/        # 解析工具
│   ├── validator/     # 验证工具
│   └── helpers/       # 辅助函数
├── config/            # 配置文件
├── types/             # TypeScript类型定义
└── index.js           # 入口文件
```

## 🔧 核心模块

### core/ - 核心业务逻辑
包含系统的核心功能实现，包括时间轴同步、播放控制和视频导出等。

[详细文档](./core/README.md)

### ui/ - 用户界面
包含所有UI组件和视图，负责用户交互和界面渲染。

[详细文档](./ui/README.md)

### services/ - 业务服务
提供音频、图片和元数据等数据服务，封装数据访问逻辑。

[详细文档](./services/README.md)

### utils/ - 工具函数
通用的工具函数和辅助方法，可复用的功能模块。

[详细文档](./utils/README.md)

## 📝 编码规范

### 命名规范
- 文件名：小写字母，单词间用短横线连接（kebab-case）
- 类名：大驼峰命名法（PascalCase）
- 变量/函数：小驼峰命名法（camelCase）
- 常量：全大写，单词间用下划线连接（UPPER_CASE）

### 代码风格
- 使用 2 空格缩进
- 字符串统一使用单引号
- 语句末尾添加分号
- 使用 ES6+ 语法特性

### 注释规范
```javascript
/**
 * 函数说明
 * @param {Type} paramName - 参数说明
 * @returns {Type} 返回值说明
 */
function exampleFunction(paramName) {
  // 实现逻辑
}
```

## 🧪 测试

每个模块都应包含对应的测试文件：
- 单元测试：`*.test.js`
- 集成测试：`*.spec.js`

运行测试：
```bash
npm test                # 运行所有测试
npm test -- --watch     # 监视模式
npm run test:coverage   # 生成覆盖率报告
```

## 🔄 开发流程

1. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **编写代码**
   - 遵循编码规范
   - 添加必要的注释
   - 编写单元测试

3. **提交代码**
   ```bash
   git add .
   git commit -m "feat: add your feature"
   ```

4. **推送并创建PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📦 依赖管理

### 生产依赖
在 `package.json` 中的 `dependencies`

### 开发依赖
在 `package.json` 中的 `devDependencies`

添加新依赖时：
```bash
npm install package-name          # 生产依赖
npm install -D package-name       # 开发依赖
```

## 🐛 调试

### 浏览器调试
- 使用 Chrome DevTools
- 在代码中添加 `debugger` 断点
- 使用 `console.log()` 输出调试信息

### VS Code调试
配置文件位于 `.vscode/launch.json`

## 📚 相关文档

- [技术架构文档](../docs/architecture/README.md)
- [API文档](../docs/api/README.md)
- [开发指南](../docs/development/README.md)

---

**维护者**: Sunflower Team
