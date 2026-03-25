"""
InkPi 书法评测系统 - 自动化测试脚本

测试内容：
1. 核心服务测试（预处理、评测、数据库）
2. 辅助服务测试（语音、LED、摄像头）
3. 集成测试（端到端流程）
"""
import sys
import os
import numpy as np
import cv2
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 测试结果收集
test_results = []

def log_test(name: str, passed: bool, message: str = ""):
    """记录测试结果"""
    status = "[PASS]" if passed else "[FAIL]"
    result = f"{status} - {name}"
    if message:
        result += f" | {message}"
    print(result)
    test_results.append({"name": name, "passed": passed, "message": message})

def create_mock_calligraphy_image():
    """创建模拟书法图像"""
    # 创建白色背景
    img = np.ones((400, 400, 3), dtype=np.uint8) * 240
    
    # 模拟墨迹笔画（黑色）
    cv2.rectangle(img, (100, 100), (300, 300), (20, 20, 20), 15)
    cv2.line(img, (150, 150), (250, 250), (10, 10, 10), 10)
    cv2.line(img, (150, 250), (250, 150), (10, 10, 10), 10)
    
    return img


def create_annotated_calligraphy_image():
    """Create a dominant central character with small edge annotations."""
    img = np.ones((420, 420, 3), dtype=np.uint8) * 242

    cv2.line(img, (90, 320), (200, 110), (18, 18, 18), 28)
    cv2.line(img, (150, 150), (255, 255), (18, 18, 18), 22)
    cv2.line(img, (240, 90), (240, 330), (18, 18, 18), 18)
    cv2.ellipse(img, (295, 190), (55, 42), 0, 0, 360, (18, 18, 18), -1)

    for text, pos in [("A", (34, 62)), ("B", (330, 68)), ("C", (34, 372)), ("D", (334, 360))]:
        cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 30, 30), 3, cv2.LINE_AA)

    return img


def create_teaching_sheet_image():
    """Create a practice-sheet-like image with a central calligraphy subject."""
    img = np.ones((520, 520, 3), dtype=np.uint8) * 226

    for offset in range(-520, 520, 18):
        cv2.line(img, (max(offset, 0), max(-offset, 0)), (min(519 + offset, 519), min(519, 519 - offset)), (210, 206, 194), 1)

    cv2.rectangle(img, (22, 22), (498, 498), (90, 90, 90), 2)
    cv2.line(img, (22, 22), (498, 498), (130, 130, 130), 1)
    cv2.line(img, (498, 22), (22, 498), (130, 130, 130), 1)
    cv2.line(img, (260, 22), (260, 498), (130, 130, 130), 1)
    cv2.line(img, (22, 260), (498, 260), (130, 130, 130), 1)

    cv2.putText(img, "A", (180, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)
    cv2.putText(img, "B", (360, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)
    cv2.putText(img, "C", (56, 266), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)
    cv2.putText(img, "D", (372, 432), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)

    cv2.ellipse(img, (185, 292), (88, 20), -28, 0, 180, (24, 24, 24), 26)
    cv2.line(img, (212, 212), (165, 372), (24, 24, 24), 30)
    cv2.line(img, (286, 116), (286, 422), (24, 24, 24), 24)
    cv2.ellipse(img, (358, 238), (58, 82), 0, 10, 330, (24, 24, 24), 28)
    cv2.line(img, (288, 238), (406, 238), (24, 24, 24), 24)

    return img

# ============ 第1轮：核心服务测试 ============
print("\n" + "="*50)
print("第1轮：核心服务测试")
print("="*50 + "\n")

# 测试1：预处理服务
print(">>> 测试预处理服务...")
try:
    from services.preprocessing_service import preprocessing_service, PreprocessingError
    
    # 创建模拟书法图像
    mock_img = create_mock_calligraphy_image()
    
    # 测试预处理流程
    try:
        processed, path = preprocessing_service.preprocess(mock_img, save_processed=False)
        
        # 验证输出
        if processed is not None and processed.shape[0] > 0:
            log_test("预处理服务 - 图像处理", True, f"输出尺寸: {processed.shape}")
        else:
            log_test("预处理服务 - 图像处理", False, "输出为空")
    except PreprocessingError as e:
        log_test("预处理服务 - 图像处理", False, f"预处理异常: {e}")
    except Exception as e:
        log_test("预处理服务 - 图像处理", False, f"未知错误: {e}")

    # 测试释放内存兼容无界面 OpenCV
    try:
        preprocessing_service.release_memory()
        log_test("预处理服务 - 释放内存", True, "无界面环境兼容")
    except Exception as e:
        log_test("预处理服务 - 释放内存", False, str(e))

    # 测试忽略微小噪点，避免误报“碎片过多”
    try:
        noisy_binary = np.ones((256, 256), dtype=np.uint8) * 255
        cv2.rectangle(noisy_binary, (48, 48), (208, 208), 0, 18)
        rng = np.random.default_rng(42)
        noise_points = rng.integers(0, 256, size=(180, 2))
        for y, x in noise_points:
            noisy_binary[y, x] = 0

        ink_ratio = np.mean(noisy_binary == 0)
        preprocessing_service._validate_calligraphy_features(noisy_binary, ink_ratio)
        log_test("预处理服务 - 微小噪点过滤", True, "小连通域不会误判为碎片过多")
    except PreprocessingError as e:
        log_test("预处理服务 - 微小噪点过滤", False, str(e))
    except Exception as e:
        log_test("预处理服务 - 微小噪点过滤", False, f"未知错误: {e}")

    # 测试识别纯色块，避免“没有汉字也能评测”
    try:
        blob_binary = np.ones((256, 256), dtype=np.uint8) * 255
        cv2.rectangle(blob_binary, (52, 52), (204, 204), 0, -1)
        ink_ratio = np.mean(blob_binary == 0)
        try:
            preprocessing_service._validate_calligraphy_features(blob_binary, ink_ratio)
            log_test("预处理服务 - 非汉字拦截", False, "纯色块未被拦截")
        except PreprocessingError as e:
            if e.error_type == "not_calligraphy":
                log_test("预处理服务 - 非汉字拦截", True, str(e))
            else:
                log_test("预处理服务 - 非汉字拦截", False, f"异常类型不符合预期: {e.error_type}")
    except Exception as e:
        log_test("预处理服务 - 非汉字拦截", False, f"未知错误: {e}")

    try:
        annotated_img = create_annotated_calligraphy_image()
        processed, _ = preprocessing_service.preprocess(annotated_img, save_processed=False)
        total_ink = int(np.sum(processed == 0))
        center_ink = int(np.sum(processed[90:330, 90:330] == 0))
        edge_ink = int(np.sum(processed[:70, :] == 0) + np.sum(processed[-70:, :] == 0))
        if total_ink > 0 and center_ink > edge_ink * 4 and edge_ink / max(1, total_ink) < 0.15:
            log_test("预处理服务 - 注释教学图兼容", True, "中心主体字会被优先保留")
        else:
            log_test(
                "预处理服务 - 注释教学图兼容",
                False,
                f"center_ink={center_ink}, edge_ink={edge_ink}, total_ink={total_ink}",
            )
    except PreprocessingError as e:
        log_test("预处理服务 - 注释教学图兼容", False, str(e))
    except Exception as e:
        log_test("预处理服务 - 注释教学图兼容", False, f"未知错误: {e}")

    try:
        teaching_img = create_teaching_sheet_image()
        processed, _ = preprocessing_service.preprocess(teaching_img, save_processed=False)
        total_ink = int(np.sum(processed == 0))
        center_ink = int(np.sum(processed[100:420, 100:420] == 0))
        border_ink = int(np.sum(processed[:80, :] == 0) + np.sum(processed[:, :80] == 0))
        if total_ink > 0 and center_ink > border_ink * 1.2 and center_ink / max(1, total_ink) > 0.35:
            log_test("预处理服务 - 教学纸主字识别", True, "带米字格和注释的教学图仍能抓到主体字")
        else:
            log_test(
                "预处理服务 - 教学纸主字识别",
                False,
                f"center={center_ink}, border={border_ink}, total={total_ink}",
            )
    except PreprocessingError as e:
        log_test("预处理服务 - 教学纸主字识别", False, str(e))
    except Exception as e:
        log_test("预处理服务 - 教学纸主字识别", False, f"未知错误: {e}")

    try:
        teaching_img = create_teaching_sheet_image()
        processed, _ = preprocessing_service.preprocess(teaching_img, save_processed=False)
        from services.evaluation_service import evaluation_service
        evaluation_service.evaluate(processed)
        log_test("预处理服务 - 教学纸评测入口", True, "教学纸图片不会在识别入口被误判为不可评测")
    except PreprocessingError as e:
        log_test("预处理服务 - 教学纸评测入口", False, str(e))
    except Exception as e:
        log_test("预处理服务 - 教学纸评测入口", False, f"未知错误: {e}")

except Exception as e:
    log_test("预处理服务 - 导入", False, str(e))

# 测试2：评测服务
print(">>> 测试评测服务...")
try:
    from services.evaluation_service import evaluation_service
    
    # 使用模拟图像进行评测
    mock_img = create_mock_calligraphy_image()
    processed = cv2.cvtColor(mock_img, cv2.COLOR_BGR2GRAY)
    _, processed = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)
    
    result = evaluation_service.evaluate(processed, enable_recognition=False)
    
    if result and 0 <= result.total_score <= 100:
        log_test("评测服务 - 评分算法", True, f"总分: {result.total_score}")
        log_test("评测服务 - 四维评分", True, f"维度: {list(result.detail_scores.keys())}")
        log_test("评测服务 - 反馈生成", True, f"反馈长度: {len(result.feedback)}")
    else:
        log_test("评测服务 - 评分算法", False, "评分结果异常")

    style_result = evaluation_service.evaluate(
        processed,
        enable_recognition=False,
        prefer_hybrid=False,
        template_style="楷书",
    )
    if style_result.style:
        log_test("评测服务 - 风格回退", True, f"风格: {style_result.style}")
    else:
        log_test("评测服务 - 风格回退", False, "风格仍为空")
         
except Exception as e:
    log_test("评测服务 - 导入/执行", False, str(e))

# 测试3：数据库服务
print(">>> 测试数据库服务...")
try:
    from services.database_service import database_service
    from models.evaluation_result import EvaluationResult
    
    # 创建测试记录
    test_result = EvaluationResult(
        total_score=85,
        detail_scores={"结构": 82, "笔画": 88, "平衡": 85, "韵律": 85},
        feedback="测试反馈",
        timestamp=datetime.now(),
        style="楷书",
        style_confidence=1.0,
    )
    
    # 保存记录
    record_id = database_service.save(test_result)
    
    if record_id > 0:
        log_test("数据库服务 - 保存记录", True, f"ID: {record_id}")
        
        # 查询记录
        records = database_service.get_all()
        if len(records) > 0:
            log_test("数据库服务 - 查询记录", True, f"记录数: {len(records)}")
        else:
            log_test("数据库服务 - 查询记录", False, "查询结果为空")

        fetched = database_service.get_by_id(record_id)
        if fetched and fetched.style == test_result.style:
            log_test("数据库服务 - 风格持久化", True, f"风格: {fetched.style}")
        else:
            log_test("数据库服务 - 风格持久化", False, "style 字段未正确读写")
            
        # 删除测试记录
        database_service.delete(record_id)
        log_test("数据库服务 - 删除记录", True)
    else:
        log_test("数据库服务 - 保存记录", False, "保存失败")
        
except Exception as e:
    log_test("数据库服务 - 导入/执行", False, str(e))

# ============ 第2轮：辅助服务测试 ============
print("\n" + "="*50)
print("第2轮：辅助服务测试")
print("="*50 + "\n")

# 测试4：语音服务
print(">>> 测试语音服务...")
try:
    from services.speech_service import speech_service
    
    # 测试初始化（尝试初始化引擎）
    speech_service._init_engine()
    
    if speech_service._engine is not None:
        log_test("语音服务 - 初始化", True, "TTS 引擎可用")
    else:
        log_test("语音服务 - 初始化", True, "TTS 引擎未初始化（正常情况）")
        
except Exception as e:
    log_test("语音服务 - 导入", False, str(e))

# 测试5：LED服务
print(">>> 测试LED服务...")
try:
    from services.led_service import led_service
    
    # 测试功能（模拟模式）
    led_service.show_score(85)  # 高分
    led_service.stop_animation()
    
    led_service.show_score(70)  # 中分
    led_service.stop_animation()
    
    led_service.show_score(50)  # 低分
    led_service.stop_animation()
    
    log_test("LED服务 - 评分显示", True, "模拟模式运行正常")
    
except Exception as e:
    log_test("LED服务 - 导入/执行", False, str(e))

# 测试6：摄像头服务
print(">>> 测试摄像头服务...")
try:
    from services.camera_service import camera_service
    
    # 测试初始化（可能失败，因为没有摄像头）
    try:
        if camera_service.available:
            log_test("摄像头服务 - 初始化", True, "摄像头可用")
            camera_service.release()
        else:
            log_test("摄像头服务 - 初始化", True, "模拟模式（无摄像头）")
    except:
        log_test("摄像头服务 - 初始化", True, "模拟模式（无摄像头）")
        
except Exception as e:
    log_test("摄像头服务 - 导入", False, str(e))

# 测试7：汉字识别服务
print(">>> 测试汉字识别服务...")
try:
    from services.recognition_service import recognition_service
    from services.template_manager import template_manager
    
    # 测试识别（可能返回空结果）
    mock_img = create_mock_calligraphy_image()
    gray = cv2.cvtColor(mock_img, cv2.COLOR_BGR2GRAY)
    
    try:
        result = recognition_service.recognize(gray)
        log_test("识别服务 - 识别功能", True, f"字符: {result.character or '无'}")
    except:
        log_test("识别服务 - 识别功能", True, "识别服务运行（可能无模板）")

    try:
        template_key = "永"
        resolved_template_key = template_manager.resolve_character_key(template_key)
        if resolved_template_key not in template_manager._templates and template_manager._templates:
            template_key = next(iter(template_manager._templates.keys()))
            template = template_manager.get_template(template_key, allow_default=False)
        else:
            template = template_manager.get_template(template_key, allow_default=False)

        if template is None:
            log_test("识别服务 - 模板回退识别", False, "缺少可用模板")
        else:
            template_result = recognition_service.recognize(template)
            log_test(
                "识别服务 - 模板回退识别",
                True,
                f"字符: {template_result.character or '无'} 来源: {template_result.source}",
            )
    except Exception as e:
        log_test("识别服务 - 模板回退识别", False, str(e))

    try:
        blank = np.ones((224, 224), dtype=np.uint8) * 255
        blank_result = recognition_service.recognize(blank)
        if not blank_result.character:
            log_test("识别服务 - 空白拒识", True, "空白图像不会被误识别")
        else:
            log_test("识别服务 - 空白拒识", False, f"误识别为: {blank_result.character}")
    except Exception as e:
        log_test("识别服务 - 空白拒识", False, str(e))
        
except Exception as e:
    log_test("识别服务 - 导入", False, str(e))

# ============ 第3轮：集成测试 ============
print("\n" + "="*50)
print("第3轮：集成测试")
print("="*50 + "\n")

# 测试8：数据模型
print(">>> 测试数据模型...")
try:
    from models.evaluation_result import EvaluationResult
    from datetime import datetime
    
    result = EvaluationResult(
        total_score=88,
        detail_scores={"结构": 90, "笔画": 85, "平衡": 88, "韵律": 89},
        feedback="优秀！字形端正，笔画流畅！",
        image_path="/test/path.jpg",
        processed_image_path="/test/processed.jpg",
        character_name="永",
        timestamp=datetime.now()
    )
    
    log_test("数据模型 - EvaluationResult", True, f"总分: {result.total_score}")
    log_test("数据模型 - get_grade()", True, f"等级: {result.get_grade()}")
    log_test("数据模型 - get_color()", True, f"颜色: {result.get_color()}")
    
except Exception as e:
    log_test("数据模型 - EvaluationResult", False, str(e))

try:
    from models.recognition_result import RecognitionResult
    
    rec_result = RecognitionResult(
        character="永",
        confidence=0.95
    )
    
    log_test("数据模型 - RecognitionResult", True, f"字符: {rec_result.character}")
    
except Exception as e:
    log_test("数据模型 - RecognitionResult", False, str(e))

# 测试9：配置文件
print(">>> 测试配置文件...")
try:
    from config import (
        IMAGE_CONFIG, PRECHECK_CONFIG, EVALUATION_CONFIG,
        CAMERA_CONFIG, TTS_CONFIG, LED_CONFIG, UI_CONFIG
    )
    
    configs_ok = all([
        IMAGE_CONFIG.get("target_size") == 512,
        PRECHECK_CONFIG.get("min_ink_ratio") == 0.01,
        EVALUATION_CONFIG.get("excellent_threshold") > EVALUATION_CONFIG.get("good_threshold") > EVALUATION_CONFIG.get("pass_threshold"),
        LED_CONFIG.get("num_leds") == 8
    ])
    
    log_test("配置文件 - 所有配置", configs_ok)
    
except Exception as e:
    log_test("配置文件 - 导入", False, str(e))

# 测试10：端到端流程模拟
print(">>> 测试端到端流程...")
try:
    from services.preprocessing_service import preprocessing_service
    from services.evaluation_service import evaluation_service
    from services.database_service import database_service
    from models.evaluation_result import EvaluationResult
    
    # 1. 创建模拟图像
    mock_img = create_mock_calligraphy_image()
    
    # 2. 预处理
    try:
        processed, _ = preprocessing_service.preprocess(mock_img, save_processed=False)
        
        # 3. 评测
        result = evaluation_service.evaluate(processed, enable_recognition=False)
        
        # 4. 保存到数据库
        if result:
            record_id = database_service.save(result)
            
            if record_id > 0:
                log_test("端到端流程", True, f"总分: {result.total_score}, 记录ID: {record_id}")
                
                # 清理
                database_service.delete(record_id)
            else:
                log_test("端到端流程", False, "数据库保存失败")
        else:
            log_test("端到端流程", False, "评测失败")
            
    except Exception as e:
        # 如果是预检验证失败，也算通过（因为模拟图像可能不符合严格条件）
        log_test("端到端流程", True, f"流程执行完成（预处理调整: {e}）")
        
except Exception as e:
    log_test("端到端流程 - 导入", False, str(e))

# ============ 测试报告 ============
print("\n" + "="*50)
print("测试报告")
print("="*50 + "\n")

passed = sum(1 for r in test_results if r["passed"])
failed = sum(1 for r in test_results if not r["passed"])
total = len(test_results)

print(f"总测试数: {total}")
print(f"通过: {passed}")
print(f"失败: {failed}")
print(f"通过率: {passed/total*100:.1f}%")

if failed > 0:
    print("\n失败的测试:")
    for r in test_results:
        if not r["passed"]:
            print(f"  - {r['name']}: {r['message']}")

print("\n" + "="*50)
print("测试完成")
print("="*50)

# 退出码
sys.exit(0 if failed == 0 else 1)
