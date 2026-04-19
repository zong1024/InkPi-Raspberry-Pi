# InkPi Overleaf 工程

这是 InkPi 项目的论文工程目录，默认用于 Overleaf 或本地 `XeLaTeX` 编译。

## 文件说明

- `main.tex`：论文主文件
- `figures/system-flow.png`：当前系统总流程图
- `figures/qt-home.png`：Qt 首页截图
- `figures/qt-result.png`：Qt 结果页截图

## 编译方式

请使用 `XeLaTeX` 编译。

本地编译示例：

```bash
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

## 当前论文口径

当前论文已经同步到项目最新状态：

- 正式支持 `楷书 + 行书` 单字
- OCR 与预处理共享
- 用户手动选择书体
- ONNX 双模型按 `script` 路由
- 新的五维正式评审标准来自官方 / 协会 / 展赛来源
- `total_score` 仍是当前正式主分
- `rubric_preview_total` 只用于内部验证，不对外展示
- 树莓派端负责正式交互
- 运维后台负责状态监控
- 小程序负责历史、统计、建议与依据展示
- 训练在本机 V100 完成，部署仅分发 ONNX 产物

## 配套产物

仓库外同步产物：

- `C:\Users\zongrui\Desktop\InkPi-paper.pdf`

仓库内上传包：

- `paper/inkpi-overleaf.zip`
