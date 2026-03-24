"""
InkPi 书法评测系统 - LED 灯带服务

基于树莓派5 SPI 驱动 WS2812B RGB 灯带
使用硬件 SPI (SPI0 MOSI) 模拟 WS2812B 时序

硬件连接：
- DIN → SPI0 MOSI (GPIO10, Pin 19)
- VCC → 5V (Pin 2/4)
- GND → GND (Pin 6/9/14/20/25/30/34/39)

灯光效果：
- 85-100分：绿色呼吸灯
- 60-84分：黄色/橙色稳定光
- 0-59分：红色闪烁警告
"""
import logging
import threading
import time
from typing import Tuple, Optional
from pathlib import Path

# 检测是否在树莓派上运行
IS_RASPBERRY_PI = False
try:
    with open('/proc/device-tree/model', 'r') as f:
        if 'Raspberry Pi' in f.read():
            IS_RASPBERRY_PI = True
except:
    pass

# 只在树莓派上导入硬件库
if IS_RASPBERRY_PI:
    try:
        import spidev
        LED_AVAILABLE = True
    except ImportError:
        LED_AVAILABLE = False
        logging.debug("spidev is not installed; LED service will run in simulation mode.")
else:
    LED_AVAILABLE = False


class LEDService:
    """WS2812B LED 灯带控制服务"""
    
    # 颜色定义 (R, G, B)
    COLORS = {
        'green': (0, 255, 100),       # 高分 - 绿色
        'cyan': (0, 255, 255),        # 高分 - 青色
        'yellow': (255, 200, 0),      # 中分 - 黄色
        'orange': (255, 100, 0),      # 中分 - 橙色
        'red': (255, 0, 0),           # 低分 - 红色
        'off': (0, 0, 0),             # 关闭
        'white': (255, 255, 255),     # 白色（测试用）
    }
    
    def __init__(self, num_leds: int = 8, spi_bus: int = 0, spi_device: int = 0):
        """
        初始化 LED 服务
        
        Args:
            num_leds: LED 灯珠数量
            spi_bus: SPI 总线号 (默认 0)
            spi_device: SPI 设备号 (默认 0)
        """
        self.logger = logging.getLogger(__name__)
        self.num_leds = num_leds
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        
        self.spi = None
        self.available = LED_AVAILABLE
        self._disabled_reason = None
        self._animation_thread = None
        self._stop_animation = False
        
        # 亮度 (0.0 - 1.0)
        self.brightness = 0.3
        
        if self.available:
            self._init_spi()
        else:
            self.logger.info("LED 服务运行在模拟模式（非树莓派环境）")
    
    def _init_spi(self):
        """初始化 SPI 接口"""
        device_path = Path(f"/dev/spidev{self.spi_bus}.{self.spi_device}")
        if not device_path.exists():
            self.available = False
            self._disabled_reason = f"SPI device {device_path} is not available"
            self.logger.debug(
                f"{self._disabled_reason}; LED service will run in simulation mode."
            )
            return

        try:
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            # WS2812B 需要 800kHz，SPI 需要更高频率
            # 每个比特需要 3 个 SPI 比特来编码
            # 800kHz * 3 * 8 = 19.2MHz，使用 20MHz
            self.spi.max_speed_hz = 2000000
            self.spi.mode = 0
            self.logger.info(f"SPI 初始化成功: bus={self.spi_bus}, device={self.spi_device}")
        except Exception as e:
            self.available = False
            self._disabled_reason = f"SPI initialization is unavailable: {e}"
            self.logger.debug(
                f"{self._disabled_reason}; LED service will run in simulation mode."
            )

    def _disable_spi(self, reason: str):
        """Disable hardware access and fall back to simulation mode."""
        self.available = False
        self._disabled_reason = reason
        if self.spi:
            try:
                self.spi.close()
            except Exception:
                pass
            finally:
                self.spi = None
        self.logger.debug(f"{reason}; LED service will run in simulation mode.")
    
    def _encode_color(self, r: int, g: int, b: int) -> bytes:
        """
        将 RGB 颜色编码为 WS2812B SPI 数据
        
        WS2812B 时序编码 (使用 SPI 模式 0)：
        - 1 码: 110 (高电平长)
        - 0 码: 100 (高电平短)
        
        每个颜色比特转换为 3 个 SPI 比特
        
        Args:
            r, g, b: 颜色分量 (0-255)
            
        Returns:
            编码后的字节序列
        """
        data = []
        
        # WS2812B 数据顺序是 GRB
        for byte in [g, r, b]:
            for bit in range(7, -1, -1):
                if byte & (1 << bit):
                    # 1 码: 11100000 (0xE0)
                    data.append(0xE0)
                else:
                    # 0 码: 11000000 (0xC0)
                    data.append(0xC0)
        
        return bytes(data)
    
    def _apply_brightness(self, r: int, g: int, b: int) -> Tuple[int, int, int]:
        """应用亮度调整"""
        return (
            int(r * self.brightness),
            int(g * self.brightness),
            int(b * self.brightness)
        )
    
    def set_color(self, color_name: str, led_index: Optional[int] = None):
        """
        设置 LED 颜色
        
        Args:
            color_name: 颜色名称 (green, cyan, yellow, orange, red, off, white)
            led_index: LED 索引，None 表示全部
        """
        if color_name not in self.COLORS:
            self.logger.warning(f"未知颜色: {color_name}")
            return
        
        r, g, b = self.COLORS[color_name]
        r, g, b = self._apply_brightness(r, g, b)
        
        if not self.available:
            self.logger.debug(f"[模拟] 设置 LED 颜色: {color_name}")
            return
        
        # 构建数据帧
        frame = bytearray()
        
        # 前置复位信号 (至少 50μs 低电平)
        frame.extend([0x00] * 4)
        
        # LED 数据
        for i in range(self.num_leds):
            if led_index is None or i == led_index:
                frame.extend(self._encode_color(r, g, b))
            else:
                frame.extend(self._encode_color(0, 0, 0))
        
        # 后置复位
        frame.extend([0x00] * 4)
        
        try:
            self.spi.writebytes(list(frame))
        except Exception as e:
            self._disable_spi(f"LED write is unavailable: {e}")
    
    def set_rgb(self, r: int, g: int, b: int, led_index: Optional[int] = None):
        """
        直接设置 RGB 颜色
        
        Args:
            r, g, b: 颜色分量 (0-255)
            led_index: LED 索引，None 表示全部
        """
        r, g, b = self._apply_brightness(r, g, b)
        
        if not self.available:
            self.logger.debug(f"[模拟] 设置 RGB: ({r}, {g}, {b})")
            return
        
        frame = bytearray()
        frame.extend([0x00] * 4)
        
        for i in range(self.num_leds):
            if led_index is None or i == led_index:
                frame.extend(self._encode_color(r, g, b))
            else:
                frame.extend(self._encode_color(0, 0, 0))
        
        frame.extend([0x00] * 4)
        
        try:
            self.spi.writebytes(list(frame))
        except Exception as e:
            self._disable_spi(f"LED write is unavailable: {e}")
    
    def off(self):
        """关闭所有 LED"""
        self.set_color('off')
    
    def show_score(self, score: int):
        """
        根据分数显示灯光效果
        
        Args:
            score: 评测分数 (0-100)
        """
        # 停止之前的动画
        self.stop_animation()
        
        if score >= 85:
            # 高分：绿色呼吸灯
            self._start_breathing('green', 'cyan')
        elif score >= 60:
            # 中分：黄色/橙色稳定光
            self.set_color('yellow')
        else:
            # 低分：红色闪烁警告
            self._start_blinking('red', interval=0.3)
        
        self.logger.info(f"LED 显示分数效果: {score}")
    
    def _start_breathing(self, color1: str, color2: str = None, duration: float = 2.0):
        """
        启动呼吸灯效果
        
        Args:
            color1: 主颜色
            color2: 次颜色（渐变用）
            duration: 呼吸周期（秒）
        """
        self._stop_animation = False
        
        def breathing():
            r1, g1, b1 = self.COLORS[color1]
            if color2:
                r2, g2, b2 = self.COLORS[color2]
            else:
                r2, g2, b2 = r1, g1, b1
            
            while not self._stop_animation:
                # 渐亮
                for i in range(0, 101, 5):
                    if self._stop_animation:
                        return
                    brightness = i / 100
                    r = int(r1 * brightness + r2 * (1 - brightness))
                    g = int(g1 * brightness + g2 * (1 - brightness))
                    b = int(b1 * brightness + b2 * (1 - brightness))
                    self.set_rgb(r, g, b)
                    time.sleep(duration / 40)
                
                # 渐暗
                for i in range(100, -1, -5):
                    if self._stop_animation:
                        return
                    brightness = i / 100
                    r = int(r1 * brightness + r2 * (1 - brightness))
                    g = int(g1 * brightness + g2 * (1 - brightness))
                    b = int(b1 * brightness + b2 * (1 - brightness))
                    self.set_rgb(r, g, b)
                    time.sleep(duration / 40)
        
        self._animation_thread = threading.Thread(target=breathing, daemon=True)
        self._animation_thread.start()
    
    def _start_blinking(self, color: str, interval: float = 0.5):
        """
        启动闪烁效果
        
        Args:
            color: 闪烁颜色
            interval: 闪烁间隔（秒）
        """
        self._stop_animation = False
        
        def blinking():
            while not self._stop_animation:
                self.set_color(color)
                time.sleep(interval)
                self.set_color('off')
                time.sleep(interval)
        
        self._animation_thread = threading.Thread(target=blinking, daemon=True)
        self._animation_thread.start()
    
    def stop_animation(self):
        """停止当前动画"""
        self._stop_animation = True
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=1.0)
    
    def show_success(self):
        """显示成功效果（短暂绿色闪烁）"""
        self.stop_animation()
        self.set_color('green')
        time.sleep(0.5)
        self.set_color('off')
    
    def show_error(self):
        """显示错误效果（红色闪烁3次）"""
        self.stop_animation()
        for _ in range(3):
            self.set_color('red')
            time.sleep(0.2)
            self.set_color('off')
            time.sleep(0.2)
    
    def show_loading(self):
        """显示加载效果（流水灯）"""
        self._stop_animation = False
        
        def loading():
            index = 0
            while not self._stop_animation:
                for i in range(self.num_leds):
                    if self._stop_animation:
                        return
                    self.set_rgb(0, 0, 0, i)
                self.set_rgb(100, 100, 100, index)
                index = (index + 1) % self.num_leds
                time.sleep(0.1)
        
        self._animation_thread = threading.Thread(target=loading, daemon=True)
        self._animation_thread.start()
    
    def release(self):
        """释放资源"""
        self.stop_animation()
        self.off()
        if self.spi:
            self.spi.close()
            self.spi = None
        self.logger.info("LED 服务已释放")


# 创建全局服务实例
led_service = LEDService()


# ============ 非树莓派环境的模拟实现 ============
if not LED_AVAILABLE:
    class MockLEDService(LEDService):
        """模拟 LED 服务（用于开发测试）"""
        
        def __init__(self, num_leds: int = 8, spi_bus: int = 0, spi_device: int = 0):
            super().__init__(num_leds, spi_bus, spi_device)
            self.available = False
        
        def _init_spi(self):
            pass
        
        def set_color(self, color_name: str, led_index: Optional[int] = None):
            self.logger.debug("[LED 模拟] 颜色: %s, LED: %s", color_name, led_index)
        
        def set_rgb(self, r: int, g: int, b: int, led_index: Optional[int] = None):
            self.logger.debug("[LED 模拟] RGB: (%s, %s, %s), LED: %s", r, g, b, led_index)
    
    led_service = MockLEDService()
