"""
InkPi 书法评测系统 - 语音服务

跨平台语音播报：
- Windows: SAPI5
- Linux/RPi: espeak-ng
"""
import threading
import logging
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TTS_CONFIG


class SpeechService:
    """语音服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = TTS_CONFIG
        self._engine = None
        self._lock = threading.Lock()
        self._is_speaking = False
        
    def _init_engine(self):
        """初始化 TTS 引擎"""
        if self._engine is not None:
            return
            
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            
            # 配置语音参数
            self._engine.setProperty('rate', self.config["rate"])
            self._engine.setProperty('volume', self.config["volume"])
            
            # 尝试设置中文语音
            self._set_chinese_voice()
            
            self.logger.info("TTS 引擎初始化成功")
        except Exception as e:
            self.logger.error(f"TTS 引擎初始化失败: {e}")
            self._engine = None
            
    def _set_chinese_voice(self):
        """设置中文语音"""
        if self._engine is None:
            return
            
        voices = self._engine.getProperty('voices')
        
        # 查找中文语音
        for voice in voices:
            voice_name = voice.name.lower()
            voice_id = voice.id.lower()
            
            # Windows SAPI5 中文语音关键词
            chinese_keywords = ['chinese', '中文', 'zh', 'huihui', 'kangkang', 'yaoyao']
            
            if any(kw in voice_name or kw in voice_id for kw in chinese_keywords):
                self._engine.setProperty('voice', voice.id)
                self.logger.info(f"设置中文语音: {voice.name}")
                return
                
        self.logger.warning("未找到中文语音，使用默认语音")
        
    def speak(self, text: str, blocking: bool = False) -> bool:
        """
        播放语音
        
        Args:
            text: 要播放的文本
            blocking: 是否阻塞等待播放完成
            
        Returns:
            是否成功启动播放
        """
        if not text:
            return False
            
        self._init_engine()
        
        if self._engine is None:
            self.logger.error("TTS 引擎不可用")
            return False
            
        with self._lock:
            if self._is_speaking:
                self.logger.warning("正在播放中，跳过本次请求")
                return False
                
            self._is_speaking = True
            
        def _speak_thread():
            try:
                self.logger.info(f"播放语音: {text[:50]}...")
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                self.logger.error(f"语音播放错误: {e}")
            finally:
                with self._lock:
                    self._is_speaking = False
                    
        if blocking:
            _speak_thread()
        else:
            thread = threading.Thread(target=_speak_thread, daemon=True)
            thread.start()
            
        return True
    
    def speak_score(self, total_score: int, feedback: str = None):
        """
        播报评测结果
        
        Args:
            total_score: 总分
            feedback: 反馈文本
        """
        # 生成播报文本
        if total_score >= 80:
            grade = "优秀"
        elif total_score >= 60:
            grade = "良好"
        else:
            grade = "需要加强"
            
        text = f"评测完成，得分{total_score}分，评价{grade}。"
        
        if feedback:
            text += feedback
            
        self.speak(text)
        
    def speak_error(self, error_message: str):
        """
        播报错误信息
        
        Args:
            error_message: 错误信息
        """
        self.speak(error_message)
        
    def stop(self):
        """停止当前播放"""
        if self._engine is not None:
            try:
                self._engine.stop()
            except:
                pass
                
        with self._lock:
            self._is_speaking = False
            
    def is_speaking(self) -> bool:
        """检查是否正在播放"""
        with self._lock:
            return self._is_speaking


# 创建全局服务实例
speech_service = SpeechService()