"""
InkPi 书法评测系统 - 字帖管理服务

功能：
1. 管理标准字帖库
2. 根据识别结果匹配合适的字帖
3. 支持多种书体风格（楷书、行书等）
"""
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODELS_DIR


class TemplateManager:
    """
    字帖管理服务
    
    字帖库结构：
    templates/
    ├── 永_楷书_颜真卿.png
    ├── 永_楷书_欧阳询.png
    ├── 永_行书_王羲之.png
    ├── 山_楷书_颜真卿.png
    └── ...
    """
    
    _instance = None
    CHARACTER_ALIASES = {
        "永": "yong",
        "山": "shan",
        "水": "shui",
        "火": "huo",
        "土": "tu",
        "金": "jin",
        "木": "mu",
        "人": "ren",
        "大": "da",
        "小": "xiao",
    }
    STYLE_ALIASES = {
        "楷书": "kaishu",
        "行书": "xingshu",
        "草书": "caoshu",
        "隶书": "lishu",
        "篆书": "zhuanshu",
    }
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, template_dir: str = None):
        self.logger = logging.getLogger(__name__)
        
        # 字帖目录
        if template_dir is None:
            template_dir = str(MODELS_DIR / "templates")
        self.template_dir = Path(template_dir)
        
        # 确保目录存在
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # 字帖缓存
        self._cache: Dict[str, np.ndarray] = {}
        
        # 加载字帖索引
        self._templates: Dict[str, List[Dict]] = {}
        self._load_template_index()
    
    def _load_template_index(self):
        """加载字帖索引"""
        if not self.template_dir.exists():
            self.logger.warning(f"字帖目录不存在: {self.template_dir}")
            return
        
        # 扫描字帖文件
        for file_path in self.template_dir.glob("*.png"):
            filename = file_path.stem  # 去掉扩展名
            parts = filename.split("_")
            
            if len(parts) >= 2:
                char = parts[0]
                style = parts[1] if len(parts) > 1 else "楷书"
                calligrapher = parts[2] if len(parts) > 2 else "标准"
                
                if char not in self._templates:
                    self._templates[char] = []
                
                self._templates[char].append({
                    "path": str(file_path),
                    "char": char,
                    "style": style,
                    "calligrapher": calligrapher
                })
        
        self.logger.info(f"已加载 {len(self._templates)} 个字的字帖索引")
    
    def get_template(
        self, 
        character: str, 
        style: str = "楷书",
        calligrapher: str = None,
        allow_default: bool = True
    ) -> Optional[np.ndarray]:
        """
        获取字帖图像
        
        Args:
            character: 汉字
            style: 书体风格 (楷书/行书/草书/隶书/篆书)
            calligrapher: 书法家（可选）
            
        Returns:
            字帖图像，如果找不到返回 None
        """
        # 构建缓存键
        normalized_char = self.resolve_character_key(character)
        normalized_style = self.resolve_style_key(style)
        cache_key = f"{normalized_char}_{normalized_style}_{calligrapher or 'any'}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 查找字帖
        if normalized_char not in self._templates:
            self.logger.warning(f"未找到字符 '{character}' 的字帖")
            return self._generate_default_template(character) if allow_default else None

        templates = self._templates[normalized_char]
        
        # 按风格筛选
        matched = [
            t for t in templates
            if t["style"] == normalized_style or self.resolve_style_key(t["style"]) == normalized_style
        ]
        
        if not matched:
            # 如果没有指定风格，使用第一个可用的
            matched = templates
        
        # 按书法家筛选
        if calligrapher:
            by_calligrapher = [t for t in matched if t["calligrapher"] == calligrapher]
            if by_calligrapher:
                matched = by_calligrapher
        
        # 选择第一个匹配的
        template_info = matched[0]
        
        # 加载图像
        try:
            image = cv2.imread(template_info["path"], cv2.IMREAD_GRAYSCALE)
            if image is not None:
                self._cache[cache_key] = image
                return image
        except Exception as e:
            self.logger.error(f"加载字帖失败: {e}")
        
        return self._generate_default_template(character) if allow_default else None

    def resolve_character_key(self, character: str) -> str:
        """将中文字符或别名解析为模板库中的键。"""
        if not character:
            return character

        raw = str(character).strip()
        candidates = [
            raw,
            raw.lower(),
            self.CHARACTER_ALIASES.get(raw),
        ]

        for candidate in candidates:
            if candidate and candidate in self._templates:
                return candidate

        return self.CHARACTER_ALIASES.get(raw, raw.lower())

    def resolve_style_key(self, style: str) -> str:
        """将中文书体名解析为模板库中的键。"""
        if not style:
            return "kaishu"

        raw = str(style).strip()
        return self.STYLE_ALIASES.get(raw, raw.lower())

    def to_display_character(self, character_key: str) -> str:
        """将模板键转换为更适合展示的字符。"""
        reverse_aliases = {value: key for key, value in self.CHARACTER_ALIASES.items()}
        return reverse_aliases.get(character_key, character_key)

    def iter_templates(self, style: str = None) -> List[Dict]:
        """遍历模板元数据，支持按风格筛选。"""
        normalized_style = self.resolve_style_key(style) if style else None
        results = []

        for templates in self._templates.values():
            for template in templates:
                if normalized_style is None or self.resolve_style_key(template["style"]) == normalized_style:
                    results.append(template)

        return results
    
    def _generate_default_template(self, character: str) -> Optional[np.ndarray]:
        """
        生成默认字帖（空白占位符）
        
        Args:
            character: 汉字
            
        Returns:
            空白占位图像
        """
        self.logger.warning(f"生成默认占位字帖: {character}")
        
        # 创建 224x224 白色背景
        template = np.ones((224, 224), dtype=np.uint8) * 255
        
        # 在中心绘制字符（使用 OpenCV 默认字体）
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(character, font, 2, 3)[0]
        text_x = (224 - text_size[0]) // 2
        text_y = (224 + text_size[1]) // 2
        
        cv2.putText(template, character, (text_x, text_y), font, 2, 0, 3)
        
        return template
    
    def list_available_chars(self) -> List[str]:
        """列出所有可用的字符"""
        return list(self._templates.keys())
    
    def list_available_styles(self, character: str) -> List[str]:
        """列出指定字符可用的风格"""
        if character not in self._templates:
            return []
        return list(set(t["style"] for t in self._templates[character]))
    
    def add_template(
        self, 
        image: np.ndarray, 
        character: str, 
        style: str = "楷书",
        calligrapher: str = "标准"
    ) -> bool:
        """
        添加新字帖
        
        Args:
            image: 字帖图像
            character: 汉字
            style: 书体风格
            calligrapher: 书法家
            
        Returns:
            是否添加成功
        """
        try:
            # 生成文件名
            filename = f"{character}_{style}_{calligrapher}.png"
            filepath = self.template_dir / filename
            
            # 保存图像
            cv2.imwrite(str(filepath), image)
            
            # 更新索引
            if character not in self._templates:
                self._templates[character] = []
            
            self._templates[character].append({
                "path": str(filepath),
                "char": character,
                "style": style,
                "calligrapher": calligrapher
            })
            
            self.logger.info(f"添加字帖: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加字帖失败: {e}")
            return False
    
    def create_template_from_user_image(
        self,
        image: np.ndarray,
        character: str,
        style: str = "楷书"
    ) -> np.ndarray:
        """
        从用户图像创建标准字帖格式
        
        处理流程：
        1. 灰度化
        2. 缩放到 224x224
        3. 二值化
        4. 居中处理
        
        Args:
            image: 用户书写图像
            character: 汉字
            style: 书体风格
            
        Returns:
            处理后的标准字帖图像
        """
        # 转灰度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 二值化
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # 找到墨迹边界
        ink_mask = binary == 0
        if np.sum(ink_mask) > 0:
            y_coords, x_coords = np.where(ink_mask)
            x1, x2 = np.min(x_coords), np.max(x_coords)
            y1, y2 = np.min(y_coords), np.max(y_coords)
            
            # 裁剪到墨迹区域
            margin = 10
            x1 = max(0, x1 - margin)
            y1 = max(0, y1 - margin)
            x2 = min(binary.shape[1], x2 + margin)
            y2 = min(binary.shape[0], y2 + margin)
            
            cropped = binary[y1:y2, x1:x2]
        else:
            cropped = binary
        
        # 缩放到 224x224（保持宽高比）
        h, w = cropped.shape
        scale = 200 / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        
        resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 居中放置
        template = np.ones((224, 224), dtype=np.uint8) * 255
        x_offset = (224 - new_w) // 2
        y_offset = (224 - new_h) // 2
        template[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return template


# 创建全局单例
template_manager = TemplateManager()
