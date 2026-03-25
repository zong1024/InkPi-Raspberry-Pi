# 小程序与云端结果同步

## 目标

- 树莓派在本地完成评测后，把结果上传到云端 API
- 微信小程序登录后，实时查看最新历史结果

## 目录

- `cloud_api/app.py`
  - Flask 云端 API
- `cloud_api/storage.py`
  - 登录账号、会话、评测结果 SQLite 存储
- `services/cloud_sync_service.py`
  - 树莓派端异步上传结果
- `miniapp/`
  - 微信小程序工程

## 启动云端 API

```bash
set INKPI_CLOUD_DEVICE_KEY=inkpi-demo-device-key
python -m cloud_api.app
```

默认监听 `http://127.0.0.1:5001`。

默认演示账号：

- 用户名：`demo`
- 密码：`demo123456`

可通过环境变量覆盖：

- `INKPI_CLOUD_DEMO_USER`
- `INKPI_CLOUD_DEMO_PASSWORD`
- `INKPI_CLOUD_DEMO_DISPLAY_NAME`

## 树莓派端开启上传

树莓派应用默认只在设置了后端地址时才会真正上传：

```bash
export INKPI_CLOUD_BACKEND_URL=http://<your-server>:5001
export INKPI_CLOUD_DEVICE_KEY=inkpi-demo-device-key
python main.py
```

结果仍会先落本地 SQLite，再异步上传，不会阻塞现场评测。

如果你已经启用了 kiosk 自启动，推荐直接复制一份配置文件：

```bash
cp scripts/cloud.env.example .inkpi/cloud.env
```

之后重启应用即可自动带上云端地址和设备密钥。

## 微信小程序

1. 用微信开发者工具打开 `miniapp/`
2. 在 `miniapp/config.js` 中把 `API_BASE_URL` 改成云端 API 地址
3. 开发调试时可在开发者工具里关闭“校验合法域名”

页面包括：

- `pages/login`
- `pages/history`
- `pages/result`

历史页默认每 `10` 秒轮询一次，支持下拉刷新。
