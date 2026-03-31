# InkPi

InkPi 是一个面向树莓派演示场景的书法自动评测系统。当前这条分支已经切到新主线：

`预处理 -> 本地官方 OCR -> 单个 ONNX 评分模型 -> 本地结果/云端同步`

## 当前主链路

- 不再使用模板库做评分主链
- 不再使用 Siamese 双图比较评分
- 不再保留手动锁定评测字作为主流程
- 不再区分“综合评分 / 兜底评分”双模式

当前运行时只输出：

- `character`
- `ocr_confidence`
- `total_score`
- `quality_level`
- `quality_confidence`
- `feedback`

## 目录

- [config](C:/Users/zongrui/Documents/2/config)
- [services](C:/Users/zongrui/Documents/2/services)
- [views](C:/Users/zongrui/Documents/2/views)
- [web_ui](C:/Users/zongrui/Documents/2/web_ui)
- [cloud_api](C:/Users/zongrui/Documents/2/cloud_api)
- [training](C:/Users/zongrui/Documents/2/training)

## 本地运行

PyQt 桌面端：

```bash
python main.py
```

WebUI：

```bash
python -m web_ui.app
```

默认地址：

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 测试

```bash
python test_all.py
python test_web_ui.py
python test_cloud_api.py
```

## OCR 与评分模型

- OCR：当前使用官方 PaddleOCR 本地识别
- 评分：当前使用单图 ONNX 模型 [models/quality_scorer.onnx](C:/Users/zongrui/Documents/2/models/quality_scorer.onnx)

最新本地质量评分模型训练指标见：

- [models/quality_scorer.metrics.json](C:/Users/zongrui/Documents/2/models/quality_scorer.metrics.json)

其中验证集三档均值已经拉开：

- `bad`: `57.72`
- `medium`: `74.37`
- `good`: `91.81`

## 训练

当前训练主线见：

- [training/README.md](C:/Users/zongrui/Documents/2/training/README.md)

主要脚本：

- [training/build_quality_manifest.py](C:/Users/zongrui/Documents/2/training/build_quality_manifest.py)
- [training/train_quality_scorer.py](C:/Users/zongrui/Documents/2/training/train_quality_scorer.py)
- [training/train_quality_scorer.sh](C:/Users/zongrui/Documents/2/training/train_quality_scorer.sh)

## 云端与小程序

- 云端 API：[cloud_api/app.py](C:/Users/zongrui/Documents/2/cloud_api/app.py)
- 微信小程序：[miniapp](C:/Users/zongrui/Documents/2/miniapp)

树莓派评测完成后会写入本地数据库，再异步上传到云端，供小程序查看历史结果。
