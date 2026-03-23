"""
InkPi 模型转换工具

参考 DeepVision 的模型转换工具链设计
支持:
- PyTorch -> ONNX
- ONNX -> TFLite
- 模型量化 (INT8)
"""
import torch
import torch.onnx
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ModelConverter:
    """模型转换器"""
    
    def __init__(self, model_path: str, output_dir: str = None):
        """
        初始化转换器
        
        Args:
            model_path: 模型文件路径
            output_dir: 输出目录
        """
        self.model_path = Path(model_path)
        self.output_dir = Path(output_dir) if output_dir else self.model_path.parent
        
    def to_onnx(
        self,
        output_name: str = None,
        input_size: int = 224,
        opset_version: int = 11,
        simplify: bool = True,
    ) -> Path:
        """
        转换为 ONNX 格式
        
        Args:
            output_name: 输出文件名
            input_size: 输入尺寸
            opset_version: ONNX opset 版本
            simplify: 是否简化模型
            
        Returns:
            输出文件路径
        """
        from core.models.siamese_net import load_model
        
        output_name = output_name or self.model_path.stem + ".onnx"
        output_path = self.output_dir / output_name
        
        logger.info(f"转换模型到 ONNX: {output_path}")
        
        # 加载模型
        model = load_model(str(self.model_path), device="cpu")
        model.eval()
        
        # 创建虚拟输入
        dummy_input1 = torch.randn(1, 1, input_size, input_size)
        dummy_input2 = torch.randn(1, 1, input_size, input_size)
        
        # 导出 ONNX
        torch.onnx.export(
            model,
            (dummy_input1, dummy_input2),
            str(output_path),
            opset_version=opset_version,
            input_names=["input1", "input2"],
            output_names=["feature1", "feature2"],
            do_constant_folding=True,
            dynamic_axes={
                "input1": {0: "batch_size"},
                "input2": {0: "batch_size"},
                "feature1": {0: "batch_size"},
                "feature2": {0: "batch_size"},
            }
        )
        
        logger.info(f"ONNX 导出完成: {output_path}")
        
        # 简化模型
        if simplify:
            try:
                import onnx
                from onnxsim import simplify as onnx_simplify
                
                onnx_model = onnx.load(str(output_path))
                simplified_model, check = onnx_simplify(onnx_model)
                
                if check:
                    onnx.save(simplified_model, str(output_path))
                    logger.info("ONNX 模型简化完成")
            except ImportError:
                logger.warning("onnx-simplifier 未安装，跳过简化步骤")
        
        return output_path
    
    def to_tflite(
        self,
        onnx_path: str = None,
        output_name: str = None,
        quantize: bool = False,
    ) -> Path:
        """
        转换为 TFLite 格式
        
        Args:
            onnx_path: ONNX 模型路径 (如果为 None，先转换为 ONNX)
            output_name: 输出文件名
            quantize: 是否量化为 INT8
            
        Returns:
            输出文件路径
        """
        import onnx
        from onnx2tf import convert
        
        output_name = output_name or self.model_path.stem + ".tflite"
        output_path = self.output_dir / output_name
        
        # 如果没有 ONNX 文件，先转换
        if onnx_path is None:
            onnx_path = self.to_onnx()
        
        onnx_path = Path(onnx_path)
        
        logger.info(f"转换 ONNX 到 TFLite: {output_path}")
        
        # 转换为 TFLite
        convert(
            input_onnx_file_path=str(onnx_path),
            output_folder_path=str(self.output_dir / "tflite_temp"),
            output_signaturedefs=True,
            copy_onnx_input_output_names_to_tflite=True,
        )
        
        # 找到生成的 TFLite 文件
        tflite_files = list((self.output_dir / "tflite_temp").glob("*.tflite"))
        if tflite_files:
            import shutil
            shutil.move(str(tflite_files[0]), str(output_path))
            shutil.rmtree(str(self.output_dir / "tflite_temp"))
        
        # 量化
        if quantize:
            output_path = self._quantize_tflite(output_path)
        
        logger.info(f"TFLite 导出完成: {output_path}")
        
        return output_path
    
    def _quantize_tflite(self, tflite_path: Path) -> Path:
        """量化 TFLite 模型"""
        try:
            import tensorflow as tf
            
            logger.info("量化 TFLite 模型...")
            
            converter = tf.lite.TFLiteConverter.from_tflite_file(str(tflite_path))
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.int8]
            
            quantized_model = converter.convert()
            
            quantized_path = tflite_path.with_suffix(".int8.tflite")
            with open(quantized_path, "wb") as f:
                f.write(quantized_model)
            
            logger.info(f"量化模型保存: {quantized_path}")
            
            return quantized_path
            
        except ImportError:
            logger.warning("TensorFlow 未安装，跳过量化步骤")
            return tflite_path


def convert_to_onnx(
    model_path: str,
    output_dir: str = None,
    **kwargs
) -> Path:
    """
    便捷函数：转换为 ONNX
    
    Args:
        model_path: 模型路径
        output_dir: 输出目录
        **kwargs: 其他参数
        
    Returns:
        输出文件路径
    """
    converter = ModelConverter(model_path, output_dir)
    return converter.to_onnx(**kwargs)


def convert_to_tflite(
    model_path: str,
    output_dir: str = None,
    **kwargs
) -> Path:
    """
    便捷函数：转换为 TFLite
    
    Args:
        model_path: 模型路径
        output_dir: 输出目录
        **kwargs: 其他参数
        
    Returns:
        输出文件路径
    """
    converter = ModelConverter(model_path, output_dir)
    return converter.to_tflite(**kwargs)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="模型转换工具")
    parser.add_argument("--model", type=str, required=True, help="模型文件路径")
    parser.add_argument("--output", type=str, default=None, help="输出目录")
    parser.add_argument("--format", type=str, choices=["onnx", "tflite", "all"], default="onnx", help="输出格式")
    parser.add_argument("--quantize", action="store_true", help="是否量化")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    converter = ModelConverter(args.model, args.output)
    
    if args.format == "onnx":
        converter.to_onnx()
    elif args.format == "tflite":
        converter.to_tflite(quantize=args.quantize)
    else:
        onnx_path = converter.to_onnx()
        converter.to_tflite(onnx_path=str(onnx_path), quantize=args.quantize)