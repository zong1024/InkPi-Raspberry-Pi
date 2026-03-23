"""
InkPi 书法评测系统 - 孪生网络模型

基于 MobileNetV3-Small 的轻量级孪生网络
适用于树莓派等嵌入式设备
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


class SiameseNet(nn.Module):
    """
    孪生网络模型 - 用于书法相似度评测
    
    输入: 两张灰度图像 (模板和待评测图像)
    输出: 两个 128 维特征向量 (L2 归一化)
    
    使用方法:
        model = SiameseNet(pretrained=True)
        feat1, feat2 = model(img1, img2)
        similarity = (feat1 * feat2).sum(dim=1)  # 余弦相似度
    """
    
    def __init__(self, pretrained: bool = False, embedding_dim: int = 128):
        """
        初始化孪生网络
        
        Args:
            pretrained: 是否使用 ImageNet 预训练权重
            embedding_dim: 特征向量维度
        """
        super().__init__()
        
        # 加载 MobileNetV3-Small 作为 backbone
        if pretrained:
            weights = MobileNet_V3_Small_Weights.DEFAULT
            backbone = mobilenet_v3_small(weights=weights)
        else:
            backbone = mobilenet_v3_small(weights=None)
        
        # 修改第一层: 3通道 -> 1通道 (灰度图)
        old_conv = backbone.features[0][0]
        new_conv = nn.Conv2d(
            in_channels=1,
            out_channels=old_conv.out_channels,
            kernel_size=old_conv.kernel_size,
            stride=old_conv.stride,
            padding=old_conv.padding,
            bias=False,
        )
        
        # 如果使用预训练权重，对通道维度取平均
        if pretrained:
            with torch.no_grad():
                new_conv.weight.copy_(old_conv.weight.mean(dim=1, keepdim=True))
        
        backbone.features[0][0] = new_conv
        
        # 修改分类头为 embedding 层
        backbone.classifier = nn.Sequential(
            nn.Linear(576, 256),
            nn.Hardswish(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(256, embedding_dim),
        )
        
        self.backbone = backbone
        self.embedding_dim = embedding_dim
    
    def forward_one(self, x: torch.Tensor) -> torch.Tensor:
        """
        提取单张图像的特征
        
        Args:
            x: 输入图像 [B, 1, H, W]
            
        Returns:
            L2 归一化的特征向量 [B, embedding_dim]
        """
        feat = self.backbone(x)
        return F.normalize(feat, p=2, dim=1)
    
    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> tuple:
        """
        提取两张图像的特征
        
        Args:
            x1: 模板图像 [B, 1, H, W]
            x2: 待评测图像 [B, 1, H, W]
            
        Returns:
            (feat1, feat2): 两个 L2 归一化的特征向量
        """
        return self.forward_one(x1), self.forward_one(x2)
    
    @torch.no_grad()
    def compute_similarity(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        """
        计算两张图像的余弦相似度
        
        Args:
            x1: 模板图像 [B, 1, H, W]
            x2: 待评测图像 [B, 1, H, W]
            
        Returns:
            相似度分数 [B], 范围 [-1, 1]
        """
        feat1, feat2 = self.forward(x1, x2)
        return (feat1 * feat2).sum(dim=1)


def load_model(weights_path: str, device: str = "cpu", embedding_dim: int = 128) -> SiameseNet:
    """
    加载预训练模型
    
    Args:
        weights_path: 模型权重路径
        device: 运行设备
        embedding_dim: 特征维度
        
    Returns:
        加载好的模型
    """
    model = SiameseNet(pretrained=False, embedding_dim=embedding_dim)
    
    checkpoint = torch.load(weights_path, map_location=device)
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)
    
    model.to(device)
    model.eval()
    
    return model