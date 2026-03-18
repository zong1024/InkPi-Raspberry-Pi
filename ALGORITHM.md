# InkPi 算法深度解析

> 本文档包含 InkPi 系统的所有数学原理、公式推导和技术细节。主 README 的大家都能懂的版本在这里：[README.md](README.md)

## 目录

1. [图像预处理算法](#图像预处理算法)
2. [特征提取与量化](#特征提取与量化)
3. [孪生网络架构](#孪生网络架构)
4. [融合评分器](#融合评分器)
5. [参考文献](#参考文献)

---

## 图像预处理算法

### 透视校正（Perspective Correction）

#### 1. Canny边缘检测

灰度化 + 高斯滤波后，使用Canny算子检测图像边界：

$$\nabla I = \sqrt{(\frac{\partial I}{\partial x})^2 + (\frac{\partial I}{\partial y})^2}$$

动态阈值设定为 [50, 150]，以适应不同光照条件。

#### 2. 概率霍夫变换（Probabilistic Hough Transform）

识别纸张四角的边界线段：

$$H(\rho, \theta) = \sum_{x,y} I(x,y) \cdot \delta(\rho - x\cos\theta - y\sin\theta)$$

其中 $\rho = x\cos\theta + y\sin\theta$ 为点到原点的距离。

#### 3. 透视变换矩阵

将四个角点映射为标准正视图的四个顶点 $(0,0), (W,0), (W,H), (0,H)$：

$$M = \text{getPerspectiveTransform}(src\_pts, dst\_pts)$$

变换后的图像：

$$I'(x',y') = I(M^{-1} \cdot [x', y', 1]^T)$$

### 基于HSV的红格滤除

#### HSV颜色分割

在HSV色彩空间中，红色分布在两个色相范围：

- **低频红色**：$H \in [0°, 10°]$
- **高频红色**：$H \in [170°, 180°]$

生成掩码：

$$Mask_{red} = Mask_1 \cup Mask_2$$

#### 形态学闭运算

为防止红色网格与黑色笔画交叠处的墨迹被误删，应用形态学闭运算：

$$I_{closed} = \text{dilate}(\text{erode}(I, K), K)$$

其中 $K$ 为结构化元素（通常为 $3 \times 3$ 或 $5 \times 5$ 的方形）。

### 自适应二值化

使用高斯自适应二值化替代全局大津法，以应对光照梯度：

$$B(x,y) = \begin{cases} 0 & \text{if } I(x,y) > T(x,y) \\ 1 & \text{otherwise} \end{cases}$$

其中 $T(x,y)$ 为局部均值减去常数 $C$：

$$T(x,y) = \text{mean}(I \text{ in neighborhood of } (x,y)) - C$$

参数 $C=2$，块大小为 $11 \times 11$。

### 降噪与锐化

**中值滤波**（去除椒盐噪声）：

$$I_{median}(x,y) = \text{median}(I(x,y) \text{ in } 3 \times 3 \text{ window})$$

**无损锐化**（增强边缘）：

$$I_{sharp} = I + \lambda \cdot (I - \text{GaussianBlur}(I))$$

参数 $\lambda = 0.5$（避免过度锐化导致伪影）。

---

## 特征提取与量化

### 重心平衡（Center of Gravity）

对于二值化图像 $B(x,y)$（黑色像素为1），重心坐标定义为：

$$C_x = \frac{\sum_{x=1}^{W} \sum_{y=1}^{H} x \cdot B(x,y)}{\sum_{x=1}^{W} \sum_{y=1}^{H} B(x,y)}$$

$$C_y = \frac{\sum_{x=1}^{W} \sum_{y=1}^{H} y \cdot B(x,y)}{\sum_{x=1}^{W} \sum_{y=1}^{H} B(x,y)}$$

**平衡评分**：计算重心与九宫格中心的距离，归一化到 [60, 100]：

$$\text{Balance} = 100 - 20 \cdot \frac{||C - C_{center}||}{D_{max}}$$

其中 $D_{max}$ 为图像对角线长度的1/4。

### 外接凸包矩形度（Rectangularity）

计算字形的凸包及其最小外接矩形：

$$R = \frac{P_{hull}}{P_{rect}}$$

其中 $P_{hull}$ 为凸包周长，$P_{rect}$ 为最小外接矩形周长。

**矩形度评分**：

$$\text{Rectangularity} = 100 - 30 \cdot (1 - R)$$

### 留白与布白（Whitespace Distribution）

将图像分成 $N \times N$ 的弹性网格（$N=4$ 或 $N=8$），计算各区域的留白百分比：

$$WS_i = \frac{\text{white\_pixels}_i}{\text{total\_pixels}_i}$$

计算留白方差：

$$\sigma^2_{WS} = \frac{1}{N^2} \sum_{i=1}^{N^2} (WS_i - \overline{WS})^2$$

**布白评分**（方差越小越好）：

$$\text{Whitespace} = \max(60, 100 - 100 \cdot \sigma^2_{WS})$$

### 骨架提取（Morphological Skeletonization）

使用Zhang-Suen细化算法提取单像素宽度的字形骨架，精度可达98%以上：

$$S = \text{skeleton}(B)$$

骨架用于：
1. 笔画连通性分析（是否断笔）
2. 笔画流畅度评估（拐点数量、曲率）
3. 笔势节奏检测（骨架段长度统计）

### 笔画宽度分析（Stroke Width）

在原二值图像中，沿着骨架的垂直方向测量笔画宽度：

$$W_{stroke}(s) = \text{distance\_to\_edge\_perpendicular}(s)$$

计算笔画宽度的统计特征：
- 平均宽度：$\mu_W = \frac{1}{|S|} \sum_{s \in S} W_{stroke}(s)$
- 宽度标准差：$\sigma_W = \sqrt{\frac{1}{|S|} \sum_{s \in S} (W_{stroke}(s) - \mu_W)^2}$

**笔画评分**（宽度均匀性）：

$$\text{Stroke} = \max(60, 100 - 20 \cdot \frac{\sigma_W}{\mu_W})$$

---

## 孪生网络架构

### 网络结构

**骨干网络**：MobileNetV3-Small，修改 input layer：

```
Input:  [B, 1, 224, 224]  (灰度图)
        ↓
Conv2d(1 → 16, k=3, s=2, p=1)   [修改]
BatchNorm + Hardswish
        ↓
MobileNetV3-Small blocks (inverted residuals)
        ↓
Adaptive Pooling → [B, 576]
ClassifierHead:
  Linear(576 → 256) + Hardswish + Dropout
  Linear(256 → 128)
        ↓
L2-Normalize → [B, 128]  (特征向量)
```

### 损失函数

使用Cosine Embedding Loss：

$$\mathcal{L} = \frac{1}{2} \sum_{i=1}^{B} \begin{cases}
(1 - \cos(f_1^i, f_2^i))^2 & \text{if } y_i = 1 \\
\max(0, \cos(f_1^i, f_2^i) - m)^2 & \text{if } y_i = -1
\end{cases}$$

其中 $m = 0.6$（margin），$\cos$ 为余弦相似度。

### 特征匹配

给定用户写的字 $u$ 和标准字帖 $t$，计算余弦距离：

$$d(u, t) = 1 - \cos(\phi(u), \phi(t))$$

其中 $\phi(\cdot)$ 为网络特征提取函数。

**结构评分**：

$$\text{Structure} = 100 \cdot (1 - d(u, t)) \quad \text{(if } d < 0.3 \text{)}$$

否则按照OpenCV特征退级。

### 平衡评分融合

孪生网络给出的相似度 + OpenCV的重心偏差，加权融合：

$$\text{Balance}_{final} = 0.4 \cdot \text{Balance}_{opencv} + 0.6 \cdot \text{Balance}_{siamese}$$

---

## 融合评分器

### 四维评分融合

最终四维评分通过加权平均得出：

$$Score_i = g_i(\mathcal{F}, \phi)$$

其中 $\mathcal{F}$ 为OpenCV特征向量，$\phi$ 为孪生网络特征。

### 总分计算

$$Score_{total} = \frac{1}{4} \sum_{i=1}^{4} Score_i$$

分数映射到 [60, 100] 区间，确保用户始终收到正反馈。

### 反馈生成

根据各维度分数的不足，从逻辑决策树生成自然语言反馈。例如：

- 若 $C_x < 0.4W$（重心严重左倾）：生成"结构重心严重左倾，请注意右侧笔画的伸展"
- 若 $\sigma_W / \mu_W > 0.4$（笔画宽度太不均匀）：生成"笔画粗细变化过大，建议统一力度"

---

## 参考文献

1. **Siamese Networks for One-shot Learning** - Koch, Zemel, Salakhutdinov (2015)
   - https://arxiv.org/abs/1503.03585

2. **Aesthetic Visual Quality Evaluation of Chinese Handwritings** - IJCAI 2021
   - 对书法美学定量化的开创性工作

3. **Intelligent Evaluation of Chinese Hard-Pen Calligraphy Using a Siamese Transformer Network** - MDPI Sensors 2024
   - 硬笔书法评测的transformer改进

4. **Fully Convolutional Network Based Skeletonization for Handwritten Chinese Characters** - AAAI 2020
   - 骨架提取算法参考

5. **Fine Segmentation of Chinese Character Strokes Based on Coordinate Awareness and Enhanced BiFPN** - ResearchGate
   - 笔画分割技术

6. **Shape Analysis and Classification of Euclidean Objects Using the Medial Axis Transform** - IEEE 1999
   - 形态学细化理论基础

---

**更新日期**：2026年3月
