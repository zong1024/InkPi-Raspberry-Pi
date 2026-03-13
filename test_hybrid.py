"""
InkPi v3.0 混合架构测试脚本

测试流程：
1. 创建模拟图像（用户书写 + 字帖）
2. 运行双轨预处理
3. 运行混合评测
4. 输出四维评分
"""
import cv2
import numpy as np
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from services.evaluation_service_v3 import hybrid_evaluation_service
from services.siamese_engine import siamese_engine
from services.template_manager import template_manager


def create_test_image(character: str = "永", style: str = "user") -> np.ndarray:
    """
    创建测试图像
    
    Args:
        character: 字符
        style: 风格 (user/template)
        
    Returns:
        测试图像
    """
    # 创建 512x512 白色背景
    img = np.ones((512, 512, 3), dtype=np.uint8) * 255
    
    # 绘制米字格（红色）
    cv2.rectangle(img, (50, 50), (462, 462), (0, 0, 255), 2)
    cv2.line(img, (50, 50), (462, 462), (0, 0, 255), 1)
    cv2.line(img, (462, 50), (50, 462), (0, 0, 255), 1)
    cv2.line(img, (256, 50), (256, 462), (0, 0, 255), 1)
    cv2.line(img, (50, 256), (462, 256), (0, 0, 255), 1)
    
    # 绘制汉字（模拟）
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    if style == "template":
        text_size = cv2.getTextSize(character, font, 8, 4)[0]
        text_x = (512 - text_size[0]) // 2
        text_y = (512 + text_size[1]) // 2
        cv2.putText(img, character, (text_x, text_y), font, 8, (0, 0, 0), 4)
    else:
        text_size = cv2.getTextSize(character, font, 7, 3)[0]
        text_x = (512 - text_size[0]) // 2 + 10
        text_y = (512 + text_size[1]) // 2 - 5
        cv2.putText(img, character, (text_x, text_y), font, 7, (30, 30, 30), 3)
    
    return img


def preprocess_dual_track(image: np.ndarray) -> tuple:
    """
    双轨预处理（简化版，用于测试）
    
    Args:
        image: 输入图像
        
    Returns:
        Tuple[binary_image, texture_image]
    """
    print("\n📷 双轨预处理...")
    start_time = time.perf_counter()
    
    # 转灰度
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # 二值化
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    # 缩放到 224x224
    binary_224 = cv2.resize(binary, (224, 224), interpolation=cv2.INTER_AREA)
    texture_224 = cv2.resize(gray, (224, 224), interpolation=cv2.INTER_AREA)
    
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"   ✓ 预处理完成: {elapsed:.1f}ms")
    print(f"   ✓ Binary: {binary_224.shape}, Texture: {texture_224.shape}")
    
    return binary_224, texture_224


def test_hybrid_evaluation():
    """测试混合评测"""
    print("=" * 60)
    print("🚀 InkPi v3.0 混合架构测试")
    print("=" * 60)
    
    # 1. 创建测试图像
    print("\n📝 创建测试图像...")
    user_image = create_test_image("永", "user")
    template_image = create_test_image("永", "template")
    print("   ✓ 用户图像: 512x512")
    print("   ✓ 字帖图像: 512x512")
    
    # 2. 双轨预处理
    user_binary, user_texture = preprocess_dual_track(user_image)
    template_binary, template_texture = preprocess_dual_track(template_image)
    
    # 3. 保存字帖到模板库
    print("\n📚 保存字帖到模板库...")
    template_manager.add_template(template_binary, "永", "楷书", "标准")
    print("   ✓ 字帖已保存")
    
    # 4. 孪生网络对比
    print("\n🔄 孪生网络对比...")
    structure_score, balance_score = siamese_engine.compare_structure(
        user_binary, template_binary
    )
    print(f"   ✓ 结构分: {structure_score:.1f}")
    print(f"   ✓ 平衡分: {balance_score:.1f}")
    
    # 5. OpenCV 特征评分
    print("\n🔧 OpenCV 特征评分...")
    from services.evaluation_service_v3 import HybridEvaluationService
    service = HybridEvaluationService()
    features = service._extract_brush_features(user_texture, user_binary)
    
    print("   特征提取结果:")
    for key, value in features.items():
        print(f"     - {key}: {value:.4f}")
    
    stroke_score = service._score_stroke(features)
    rhythm_score = service._score_rhythm(features)
    print(f"   ✓ 笔画分: {stroke_score:.1f}")
    print(f"   ✓ 韵律分: {rhythm_score:.1f}")
    
    # 6. 混合评测
    print("\n🎯 混合评测...")
    result = hybrid_evaluation_service.evaluate(
        binary_image=user_binary,
        texture_image=user_texture,
        character_name="永",
        template_style="楷书"
    )
    
    # 7. 输出结果
    print("\n" + "=" * 60)
    print("📊 评测结果")
    print("=" * 60)
    print(f"  字符: {result.character_name}")
    print(f"  风格: {result.style}")
    print(f"  总分: {result.total_score}")
    print(f"\n  四维评分:")
    for dim, score in result.detail_scores.items():
        bar = "█" * (score // 5) + "░" * (20 - score // 5)
        print(f"    {dim}: {score:3d} [{bar}]")
    print(f"\n  反馈: {result.feedback}")
    print("=" * 60)
    
    return result


def test_with_real_image(image_path: str = None):
    """使用真实图像测试"""
    print("=" * 60)
    print("🚀 InkPi v3.0 真实图像测试")
    print("=" * 60)
    
    if image_path is None:
        print("\n⚠️ 未提供图像路径，使用模拟图像")
        return test_hybrid_evaluation()
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"\n❌ 无法读取图像: {image_path}")
        return None
    
    print(f"\n📷 读取图像: {image_path}")
    print(f"   尺寸: {image.shape}")
    
    binary, texture = preprocess_dual_track(image)
    
    result = hybrid_evaluation_service.evaluate(
        binary_image=binary,
        texture_image=texture,
        original_image_path=image_path,
        character_name="永",
        template_style="楷书"
    )
    
    print("\n" + "=" * 60)
    print("📊 评测结果")
    print("=" * 60)
    print(f"  总分: {result.total_score}")
    print(f"\n  四维评分:")
    for dim, score in result.detail_scores.items():
        bar = "█" * (score // 5) + "░" * (20 - score // 5)
        print(f"    {dim}: {score:3d} [{bar}]")
    print(f"\n  反馈: {result.feedback}")
    print("=" * 60)
    
    return result


def performance_test():
    """性能测试"""
    print("=" * 60)
    print("⚡ 性能测试 (10次迭代)")
    print("=" * 60)
    
    user_image = create_test_image("永", "user")
    template_image = create_test_image("永", "template")
    
    user_binary, user_texture = preprocess_dual_track(user_image)
    template_binary, _ = preprocess_dual_track(template_image)
    
    template_manager.add_template(template_binary, "永", "楷书", "标准")
    
    times = []
    for i in range(10):
        start = time.perf_counter()
        
        result = hybrid_evaluation_service.evaluate(
            binary_image=user_binary.copy(),
            texture_image=user_texture.copy(),
            character_name="永",
            template_style="楷书"
        )
        
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
        print(f"  第 {i+1:2d} 次: {elapsed:.1f}ms")
    
    print(f"\n📊 性能统计:")
    print(f"   平均: {np.mean(times):.1f}ms")
    print(f"   最小: {np.min(times):.1f}ms")
    print(f"   最大: {np.max(times):.1f}ms")
    print(f"   标准差: {np.std(times):.1f}ms")
    print(f"\n🍓 树莓派预期: {np.mean(times) * 3:.1f}ms (约3倍)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="InkPi v3.0 混合架构测试")
    parser.add_argument("--image", "-i", type=str, help="测试图像路径")
    parser.add_argument("--perf", "-p", action="store_true", help="运行性能测试")
    
    args = parser.parse_args()
    
    if args.perf:
        performance_test()
    elif args.image:
        test_with_real_image(args.image)
    else:
        test_hybrid_evaluation()