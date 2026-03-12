# InkPi 墨韵评测 - 微信小程序

微信小程序端，与树莓派书法评测系统联动，查看评测历史和详细报告。

## 📁 项目结构

```
miniprogram/
├── app.js                 # 小程序入口
├── app.json               # 全局配置
├── app.wxss               # 全局样式
├── project.config.json    # 项目配置
├── sitemap.json           # 站点地图
├── pages/
│   ├── index/             # 登录页
│   ├── history/           # 历史记录页
│   ├── detail/            # 评测详情页
│   └── profile/           # 个人中心页
├── cloudfunctions/        # 云函数
│   ├── login/             # 登录
│   ├── getHistory/        # 获取历史
│   ├── getDetail/         # 获取详情
│   ├── getStats/          # 获取统计
│   └── uploadResult/      # 上传结果
└── images/                # 图标资源（需自行添加）
```

## 🚀 快速开始

### 1. 配置云开发环境

1. 在微信开发者工具中打开项目
2. 点击「云开发」按钮，创建云开发环境
3. 记录云开发环境ID

### 2. 修改配置

**app.js** - 修改云开发环境ID：
```javascript
wx.cloud.init({
  env: 'your-env-id', // 替换为您的云开发环境ID
  traceUser: true,
});
```

**project.config.json** - 修改AppID：
```json
{
  "appid": "您的小程序AppID"
}
```

### 3. 部署云函数

1. 在微信开发者工具中，右键每个云函数目录
2. 选择「上传并部署：云端安装依赖」
3. 等待部署完成

### 4. 创建数据库集合

在云开发控制台创建以下集合：
- `users` - 用户信息
- `evaluations` - 评测记录

### 5. 图标说明

小程序已使用文字/emoji替代图标，无需额外添加图片资源：
- Logo: 使用汉字"墨"
- 头像: 使用用户昵称首字
- 空状态: 使用emoji 📋
- tabBar: 纯文字导航

## 🔗 树莓派联动

树莓派端通过 `cloud_upload_service.py` 上传评测结果：

```python
from services.cloud_upload_service import CloudUploadService

# 创建服务
service = CloudUploadService(env_id="your-env-id")

# 上传评测结果
result = service.upload_evaluation_result(
    openid="user_openid",           # 用户openid
    total_score=85,                  # 总分
    detail_scores={
        "structure": 83,
        "stroke": 78,
        "balance": 91,
        "rhythm": 88
    },
    feedback="太棒了！您的书法水平很高！",
    image_path="/path/to/image.jpg",
    title="九成宫醴泉铭 · 每日评测"
)
```

## 📱 页面功能

| 页面 | 路径 | 功能 |
|------|------|------|
| 登录页 | /pages/index/index | 用户名密码登录/注册 |
| 历史记录 | /pages/history/history | 评测历史列表 |
| 评测详情 | /pages/detail/detail | 四维评分、雷达图、反馈 |
| 个人中心 | /pages/profile/profile | 用户信息、设备绑定 |

## 🎨 设计风格

- **主色调**: `#e03229`（中国红）
- **背景色**: `#f8f6f6`（宣纸色）
- **设计理念**: 传统书法 + 现代简约

## 📋 云函数说明

| 云函数 | 用途 | 调用方 |
|--------|------|--------|
| login | 获取用户openid | 小程序 |
| getHistory | 获取评测历史 | 小程序 |
| getDetail | 获取评测详情 | 小程序 |
| getStats | 获取统计数据 | 小程序 |
| uploadResult | 上传评测结果 | 树莓派 |

## ⚠️ 注意事项

1. 需要在云开发控制台开启云函数HTTP访问
2. 树莓派需要能够访问外网
3. 用户openid需要在树莓派端配置

## 📄 License

MIT License © 2026 ZongRui