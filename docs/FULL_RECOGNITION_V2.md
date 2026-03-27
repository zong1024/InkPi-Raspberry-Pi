# Full Recognition V2

这份文档描述 InkPi 的“完全体识别”隔离开发线，也就是当前 `codex/full-recognition-v2` 分支的目标状态。

## 目标

把系统从“固定模板字评测器”升级成：

- 自动 OCR 优先的全字识别器
- 对已建模板字进行模板评分
- 对无模板但已识别字符进行通用评分
- 对 OCR 不稳定的场景进行明确拒识，而不是乱猜

## 为什么旧逻辑不够

早期版本更像固定字表评测器：

- 封闭字库
- 手调阈值开集拒识
- 很多场景依赖手动锁字
- 一旦超出模板库，容易落回“当前不支持字库”的旧提示

这对比赛 Demo 有价值，但不适合作为“全字识别”方案。

## 当前新链路

### 1. 主体字提取

复用已有 ROI 提取和几何分析逻辑，先把图片里的单字主体抽出来。

### 2. OCR 候选生成

新链路不再让本地模板库自己硬猜所有字，而是先由 OCR 提供 `top-k` 候选。

当前已接入两种候选提供器：

- 本地 `PaddleOcrCandidateProvider`
- 远端 `HttpOcrCandidateProvider`

当前实际更稳定的路线是：

- 树莓派端调用云端 OCR 候选接口
- 服务器端运行 PaddleOCR

### 3. 本地重排

拿到 OCR 候选后，再结合本地能力做重排：

- Siamese 结构相似度
- 几何签名
- 轮廓与拓扑证据
- 本地模板对齐能力

### 4. 状态决策

系统最终不再只给一个“猜中的字”，而是给明确状态：

- `matched`
  - 识别稳定
  - 有本地模板
  - 可以进入模板评分
- `untemplated`
  - 识别稳定
  - 暂无本地模板
  - 进入通用评分
- `ambiguous`
  - OCR 候选接近
  - 当前不能稳定确认字符
- `unsupported`
  - 当前画面像毛笔字
  - 但 OCR 证据不足，不能稳定识别
- `rejected`
  - 当前画面本身就不符合单字评测条件

## 当前已经落地的行为

### 自动 OCR 已经是主流程

这条分支里，产品逻辑已经改成：

1. 默认自动 OCR
2. 手动锁字只是可选兜底
3. 不再把“先选字”当作主流程

### 模板外字符不再直接报“不支持字库”

当前链路已经支持：

- 识别出字符
- 若本地有模板，走模板评分
- 若本地无模板，走通用评分

也就是说，“认出来了但还没模板”的字符现在可以继续评，不会直接被挡掉。

### 远端 OCR 服务已跑通

当前实现中，树莓派可以通过云端接口拿 OCR 候选：

- 接口：`/api/device/full-recognition/candidates`
- 服务端：`cloud_api/app.py`
- 身份校验：`X-Device-Key`

## 已验证结果

这条分支已经做过真实图验证：

- `神`
  - 可识别
  - 有模板时走模板评分
- `三`
  - 可识别
  - 无模板时走通用评分

这说明系统已经从“只能认少量模板字”进入了：

- 能先识别字符
- 再决定评分方式

## 代码入口

核心文件：

- [full_recognition_v2/pipeline.py](C:/Users/zongrui/Documents/2/full_recognition_v2/pipeline.py)
- [full_recognition_v2/service.py](C:/Users/zongrui/Documents/2/full_recognition_v2/service.py)
- [full_recognition_v2/http_provider.py](C:/Users/zongrui/Documents/2/full_recognition_v2/http_provider.py)
- [full_recognition_v2/paddle_provider.py](C:/Users/zongrui/Documents/2/full_recognition_v2/paddle_provider.py)
- [services/recognition_flow_service.py](C:/Users/zongrui/Documents/2/services/recognition_flow_service.py)
- [services/evaluation_service.py](C:/Users/zongrui/Documents/2/services/evaluation_service.py)
- [cloud_api/app.py](C:/Users/zongrui/Documents/2/cloud_api/app.py)

## 当前边界

这条线已经能做“全字识别优先”，但还不是最终完全体：

- 不是每个字都有本地模板
- 通用评分还不如模板评分细
- OCR 与本地重排的融合阈值仍在继续校准

所以当前最准确的说法是：

- 这条线已经具备“全字识别 + 模板/通用双评分”的基本能力
- 还在持续提升“更稳、更准、更少拒识”

## 开发原则

这条线必须保持隔离开发：

- 不直接干扰 `master` 稳定演示版
- 优先在隔离分支验证效果
- 能证明稳定后再考虑回合并主线
