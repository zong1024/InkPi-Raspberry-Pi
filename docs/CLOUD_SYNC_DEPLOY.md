# InkPi 云端同步部署

目标链路：

```text
树莓派 Qt 评测端 -> 公网 cloud_api -> 微信小程序历史记录
```

树莓派负责拍照、OCR、ONNX 评分和本地保存；公网服务器只保存同步历史，并给微信小程序提供登录、历史列表和详情接口。

## 服务器

当前公网服务器：

```text
202.60.232.93
```

为避免影响已有 blog 服务，InkPi 后端默认只使用独立端口：

```text
23334
```

部署脚本不会修改 nginx、caddy、apache、80 或 443 端口。

## 部署云端 API

在服务器上执行：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/deploy_cloud_api_server.sh | bash
```

部署后检查：

```bash
curl http://127.0.0.1:23334/api/health
systemctl status inkpi-cloud-api --no-pager
```

## 树莓派同步配置

在树莓派项目目录创建或修改：

```bash
nano ~/InkPi-Raspberry-Pi/.inkpi/cloud.env
```

内容示例：

```env
INKPI_CLOUD_BACKEND_URL=http://202.60.232.93:23334
INKPI_CLOUD_DEVICE_KEY=替换成服务器脚本输出的-device-key
INKPI_CLOUD_DEVICE_NAME=InkPi-Raspberry-Pi
INKPI_UI_MODE=qt
```

然后重启 InkPi Qt 程序。之后每次评测保存时，`services/cloud_sync_service.py` 会自动异步上传历史记录。

## 微信小程序

小程序当前接口地址：

```js
const API_BASE_URL = 'http://202.60.232.93:23334';
```

登录账号和密码由服务器部署脚本输出，也会保存在服务器：

```text
/etc/inkpi-cloud-api.env
```

## 正式版注意

微信小程序正式发布通常要求 HTTPS 域名并配置 request 合法域名。`http://202.60.232.93:23334` 适合开发版或体验版联调。正式上线时建议单独绑定子域名，例如 `inkpi.zongtech.xyz`，再反代到 `127.0.0.1:23334`。
