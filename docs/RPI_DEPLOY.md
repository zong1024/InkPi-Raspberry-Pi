# InkPi 树莓派部署教程

本文档用于把 InkPi 部署到树莓派，并固定启动 Qt 桌面界面，不启动 WebUI。部署脚本会检查本地 OCR 和 ONNX 评分模型是否可用；任一模型不可用都会中止，避免设备启动后才发现无法评测。

## 推荐环境

- Raspberry Pi OS 64-bit，建议 Bookworm 或 Bullseye
- Python 3.9+
- 已接入网络
- 摄像头已连接，CSI 摄像头建议先在 `raspi-config` 里启用
- 项目内存在 `models/quality_scorer.onnx`

## 一键部署

在树莓派终端执行：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | bash
```

这个命令默认会：

- 克隆或更新仓库到 `~/InkPi-Raspberry-Pi`
- 安装 Qt、OpenCV、ONNX Runtime、PaddleOCR、摄像头和 kiosk 依赖
- 创建 `venv`
- 固定 `INKPI_UI_MODE=qt`
- 默认识别模式设为 `kaishu`
- 清理旧版 InkPi 开机自启动入口，避免老 WebUI / 老 Qt 和新版 Qt 抢显示、抢端口、抢摄像头
- 安装 tty1 开机自启动
- 校验 `PaddleOCR` 和 `models/quality_scorer.onnx`

部署完成后重启：

```bash
sudo reboot
```

## 常用参数

切换行书模式：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env CALLIGRAPHY_STYLE=xingshu bash
```

不安装开机自启动，只部署环境：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env INSTALL_KIOSK=0 bash
```

部署后立刻启动 Qt：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env START_APP=1 bash
```

使用指定分支：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env INKPI_BRANCH=master bash
```

使用本地新 ONNX 模型：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env MODEL_SOURCE=/home/pi/quality_scorer.onnx bash
```

如果 PaddlePaddle 默认包安装失败，可以指定版本或 wheel：

```bash
curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env PADDLEPADDLE_PACKAGE='paddlepaddle==3.2.2' bash
```

## 手动启动

部署完成后，不等重启也可以手动启动 Qt：

```bash
cd ~/InkPi-Raspberry-Pi
scripts/inkpi-launch.sh
```

或者直接进虚拟环境：

```bash
cd ~/InkPi-Raspberry-Pi
source venv/bin/activate
python main.py
```

## 字体识别模式

当前运行时只开放两种识别栏目：

- `kaishu`：楷书
- `xingshu`：行书

一键脚本会写入：

```text
~/InkPi-Raspberry-Pi/.inkpi/runtime_settings.json
~/InkPi-Raspberry-Pi/.inkpi/cloud.env
```

也可以在 Qt 设置页里切换楷书 / 行书。

## 部署后检查

确认 ONNX 模型存在：

```bash
ls -lh ~/InkPi-Raspberry-Pi/models/quality_scorer.onnx
```

确认 OCR 和评分服务能加载：

```bash
cd ~/InkPi-Raspberry-Pi
source venv/bin/activate
python - <<'PY'
from services.local_ocr_service import local_ocr_service
from services.quality_scorer_service import quality_scorer_service

print("OCR:", local_ocr_service.available)
print("ONNX:", quality_scorer_service.available)
PY
```

两项都应该输出 `True`。

## 常见问题

如果启动了 WebUI 而不是 Qt，检查：

```bash
grep INKPI_UI_MODE ~/InkPi-Raspberry-Pi/.inkpi/cloud.env
```

应为：

```env
export INKPI_UI_MODE='qt'
```

如果 OCR 加载失败，优先看 PaddlePaddle 是否安装成功：

```bash
cd ~/InkPi-Raspberry-Pi
source venv/bin/activate
python - <<'PY'
import paddle
from paddleocr import PaddleOCR
print("paddle:", paddle.__version__)
print("paddleocr import ok")
PY
```

如果摄像头不可用，先检查系统是否能看到摄像头：

```bash
libcamera-hello --list-cameras
```

如果开机没有进入 InkPi，确认是在树莓派本机 `tty1` 登录，或直接重启：

```bash
sudo reboot
```

如果树莓派上已经跑过老版本自启动，可以单独清理一次：

```bash
cd ~/InkPi-Raspberry-Pi
bash scripts/cleanup_rpi_autostart.sh
INSTALL_KIOSK=1 ./deploy_rpi.sh
sudo reboot
```
