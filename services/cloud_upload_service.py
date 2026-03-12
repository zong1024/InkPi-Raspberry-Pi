"""
云开发上传服务 - 将评测结果上传到微信云开发
"""
import requests
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any


class CloudUploadService:
    """微信云开发上传服务"""
    
    def __init__(self, env_id: str = "inkpi-cloud"):
        """
        初始化云开发上传服务
        
        Args:
            env_id: 云开发环境ID
        """
        self.env_id = env_id
        # 云函数HTTP调用地址（需要在云开发控制台开启HTTP访问）
        self.base_url = f"https://{env_id}.service.tcloudbase.com"
        
    def upload_evaluation_result(
        self,
        openid: str,
        total_score: int,
        detail_scores: Dict[str, int],
        feedback: str,
        image_path: Optional[str] = None,
        processed_image_path: Optional[str] = None,
        recognized_char: Optional[str] = None,
        confidence: Optional[float] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上传评测结果到云开发
        
        Args:
            openid: 用户openid
            total_score: 总分
            detail_scores: 四维评分
            feedback: 评价反馈
            image_path: 原图路径
            processed_image_path: 处理后图片路径
            recognized_char: 识别的汉字
            confidence: 识别置信度
            title: 标题
            
        Returns:
            上传结果
        """
        # 先上传图片到云存储
        image_url = ""
        processed_image_url = ""
        
        if image_path and os.path.exists(image_path):
            image_url = self._upload_file(image_path, "images")
            
        if processed_image_path and os.path.exists(processed_image_path):
            processed_image_url = self._upload_file(processed_image_path, "processed")
        
        # 调用云函数上传数据
        data = {
            "openid": openid,
            "title": title or f"书法评测 · {datetime.now().strftime('%Y-%m-%d')}",
            "totalScore": total_score,
            "detailScores": detail_scores,
            "feedback": feedback,
            "imageUrl": image_url,
            "processedImageUrl": processed_image_url,
            "recognizedChar": recognized_char or "",
            "confidence": confidence or 0
        }
        
        return self._call_cloud_function("uploadResult", data)
    
    def _upload_file(self, file_path: str, folder: str = "") -> str:
        """
        上传文件到云存储
        
        Args:
            file_path: 文件路径
            folder: 存储文件夹
            
        Returns:
            文件URL
        """
        try:
            # 使用云存储HTTP API上传
            url = f"{self.base_url}/storage/upload"
            
            filename = os.path.basename(file_path)
            cloud_path = f"{folder}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                data = {'path': cloud_path}
                
                response = requests.post(url, files=files, data=data, timeout=30)
                
            if response.status_code == 200:
                result = response.json()
                return result.get('fileID', '')
            else:
                print(f"上传文件失败: {response.text}")
                return ""
                
        except Exception as e:
            print(f"上传文件异常: {e}")
            return ""
    
    def _call_cloud_function(self, function_name: str, data: Dict) -> Dict[str, Any]:
        """
        调用云函数
        
        Args:
            function_name: 云函数名称
            data: 请求数据
            
        Returns:
            云函数返回结果
        """
        try:
            url = f"{self.base_url}/functions/{function_name}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                url, 
                data=json.dumps(data), 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class MockCloudUploadService(CloudUploadService):
    """模拟云上传服务（用于测试）"""
    
    def __init__(self):
        """初始化模拟服务"""
        super().__init__("mock-env")
        self.uploaded_results = []
    
    def upload_evaluation_result(
        self,
        openid: str,
        total_score: int,
        detail_scores: Dict[str, int],
        feedback: str,
        image_path: Optional[str] = None,
        processed_image_path: Optional[str] = None,
        recognized_char: Optional[str] = None,
        confidence: Optional[float] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """模拟上传"""
        result = {
            "success": True,
            "id": f"mock_{len(self.uploaded_results) + 1}",
            "message": "上传成功（模拟）",
            "data": {
                "openid": openid,
                "title": title or f"书法评测 · {datetime.now().strftime('%Y-%m-%d')}",
                "totalScore": total_score,
                "detailScores": detail_scores,
                "feedback": feedback,
                "timestamp": datetime.now().isoformat()
            }
        }
        self.uploaded_results.append(result)
        print(f"[模拟上传] 评测结果: 总分={total_score}, 四维={detail_scores}")
        return result
    
    def _upload_file(self, file_path: str, folder: str = "") -> str:
        """模拟文件上传"""
        return f"mock://{folder}/{os.path.basename(file_path)}"
    
    def _call_cloud_function(self, function_name: str, data: Dict) -> Dict[str, Any]:
        """模拟云函数调用"""
        return {"success": True, "data": "mock"}


# 使用示例
if __name__ == "__main__":
    # 使用模拟服务测试
    service = MockCloudUploadService()
    
    result = service.upload_evaluation_result(
        openid="test_user_123",
        total_score=85,
        detail_scores={
            "structure": 83,
            "stroke": 78,
            "balance": 91,
            "rhythm": 88
        },
        feedback="太棒了！您的书法水平很高，请继续保持！",
        title="九成宫醴泉铭 · 每日评测"
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))