import threading
import asyncio
import time
import signal
import sys
import logging
logger = logging.getLogger("KlipperScreen.Encoder")
from abc import ABC, abstractmethod

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.error("RPi.GPIO not available")

class EncoderMode(ABC):
    """Абстрактный базовый класс для режимов энкодера"""
    
    def __init__(self, clockwise_handler=None, counterclockwise_handler=None):
        self.clockwise_handler = clockwise_handler
        self.counterclockwise_handler = counterclockwise_handler
    
    @abstractmethod
    def get_name(self):
        """Возвращает имя режима"""
        pass
    
    def set_clockwise_handler(self, handler):
        """Установка обработчика для вращения по часовой стрелке"""
        self.clockwise_handler = handler  # Исправлено: было clockwise_handler
    
    def set_counterclockwise_handler(self, handler):
        """Установка обработчика для вращения против часовой стрелки"""
        self.counterclockwise_handler = handler  # Исправлено: было counterclockwise_handler
    
    def handle_clockwise(self):
        """Обработка вращения по часовой стрелке"""
        if self.clockwise_handler:
            self.clockwise_handler()
        return self.get_name() + "_clockwise"
    
    def handle_counterclockwise(self):
        """Обработка вращения против часовой стрелки"""
        if self.counterclockwise_handler:
            self.counterclockwise_handler()
        return self.get_name() + "_counterclockwise"


class EncoderHandler:
    """
    Класс для обработки событий энкодера с использованием прерываний
    и поддержкой различных режимов работы
    """
        
    def __init__(self, pin_a=22, pin_b=23, pin_button=24, hold_time=3):
        """
        Инициализация обработчика энкодера
        
        Args:
            pin_a: Пин канала A энкодера (по умолчанию 5)
            pin_b: Пин канала B энкодера (по умолчанию 6)  
            pin_button: Пин кнопки энкодера (по умолчанию 13)
            hold_time: Время удержания кнопки для длинного нажатия (сек)
        """
                   
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_button = pin_button
        self.hold_time = hold_time
        self.use_gpio = GPIO_AVAILABLE
        
        # Состояние энкодера
        self.last_state = 0
        self.encoder_position = 0
        self.encoder_last_time = time.time()
        
        # Состояние кнопки
        self.last_button_state = 1
        self.button_press_time = 0
        self.button_held = False
        
        # Режимы работы
        self.modes = {}
        self.current_mode = None
        self.mode_index = 0
        
        # Callback функции
        self.rotation_callback = None
        self.button_press_callback = None
        self.button_hold_callback = None
        self.mode_change_callback = None
        
        
        # Флаг работы
        self.running = False
        self.thread = None

    def _setup_gpio(self):
        """Настройка GPIO и прерываний"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info("GPIO setup succes")
        # Настраиваем прерывания для энкодера с встроенным антидребезгом
        
        GPIO.add_event_detect(self.pin_a, GPIO.BOTH, callback=self._handle_encoder, bouncetime=2)
        logger.info("GPIO setup a pin succes")
        GPIO.add_event_detect(self.pin_b, GPIO.BOTH, callback=self._handle_encoder, bouncetime=2)
        logger.info("GPIO setup b pin succes")
        # Настраиваем прерывания для кнопки с встроенным антидребезгом
        GPIO.add_event_detect(self.pin_button, GPIO.BOTH, callback=self._handle_button, bouncetime=50)
        self.last_state = (GPIO.input(self.pin_a) << 1) + GPIO.input(self.pin_b)
        
        logger.info("GPIO interrupts configured")
    
    def _cleanup_gpio(self):
        """Освобождение GPIO-пинов и сброс настроек"""
        # Удаляем обработчики прерываний
        GPIO.remove_event_detect(self.pin_a)
        GPIO.remove_event_detect(self.pin_b)
        GPIO.remove_event_detect(self.pin_button)
        
        # Переводим пины в безопасный режим
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        GPIO.setup(self.pin_button, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        GPIO.cleanup()
        
        logger.info("GPIO pins released and reset")
    
    def _worker(self):
        """Рабочий цикл в отдельном потоке"""
        # Инициализация GPIO
        if self.use_gpio:
            try:
                self._setup_gpio()
                logger.info(f"GPIO initialized: A={self.pin_a}, B={self.pin_b}, BTN={self.pin_button}")
            except Exception as e:
                logger.error(f"GPIO setup error: {e} \n  A={self.pin_a}, B={self.pin_b}, BTN={self.pin_button}")
                self.use_gpio = False
        while self.running:
            pass
            time.sleep(1)
        
        if self.use_gpio:
            self._cleanup_gpio()
    
    def start(self):
        """Запуск обработчика в отдельном потоке"""
        if self.running:
            return 
        self._worker()    
        self.running = True
        self.thread = threading.Thread(target=self._worker)
        logger.info("create thread")
        self.thread.daemon = True
        self.thread.start()
        logger.info("start thread")
    
    def stop(self):
        """Остановка обработчика и очистка GPIO"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    
    def _handle_encoder(self, channel):
        """Обработчик прерывания энкодера"""
        if not self.running:
            return      
        # Читаем текущее состояние пинов
        state = ( (self.last_state << 2) + (GPIO.input(self.pin_a) << 1) + GPIO.input(self.pin_b) ) & 0b1111
        
        if state in [0b1101, 0b0100, 0b0010, 0b1011]:
            self.encoder_position += 1
        elif state in [0b1110, 0b1000, 0b0001, 0b0111]:
            self.encoder_position -= 1
            
        print(f"{state:04b}")
        self.last_state = state
        if abs(self.encoder_position) >= 4:
            speed = time.time() - self.encoder_last_time
            if speed >=1/3:
                count = 1
            elif speed >= 1/6:
                count = 2
            elif speed >= 1/12:
                count = 4
            else:
                count = 8
            for i in range(count) :
                if self.encoder_position > 0:
                    """Вызов обработчика для вращения по часовой стрелке"""
                    if self.current_mode and self.current_mode in self.modes:
                        action_result = self.modes[self.current_mode].handle_clockwise()
                        if self.rotation_callback:
                            self.rotation_callback(action_result, "clockwise")
                else:
                    """Вызов обработчика для вращения против часовой стрелки"""
                    if self.current_mode and self.current_mode in self.modes:
                        action_result = self.modes[self.current_mode].handle_counterclockwise()
                        if self.rotation_callback:
                            self.rotation_callback(action_result, "counterclockwise")
            self.encoder_last_time = time.time()
            self.encoder_position = 0
    
    def _handle_button(self, channel):
        """Обработчик прерывания кнопки"""
        if not self.running:
            return
            
        current_state = GPIO.input(self.pin_button)
        
        # Обработка нажатия (переход 1->0)
        if current_state == 0 and self.last_button_state == 1:
            self.button_press_time = time.time()
            self.button_held = False
        
        # Обработка отпускания (переход 0->1)
        elif current_state == 1 and self.last_button_state == 0:
            press_duration = time.time() - self.button_press_time
            
            if not self.button_held and self.button_press_callback:
                # Короткое нажатие
                self.button_press_callback()
            
            self.button_held = False
        
        # Проверка длинного нажатия
        if current_state == 0 and not self.button_held:
            if time.time() - self.button_press_time >= self.hold_time:
                self.button_held = True
                if self.button_hold_callback:
                    self.button_hold_callback()
        
        self.last_button_state = current_state
    
    def add_mode(self, mode):
        """
        Добавление нового режима работы
        
        Args:
            mode: Экземпляр класса, унаследованного от EncoderMode
        """
        mode_name = mode.get_name()
        self.modes[mode_name] = mode
        if self.current_mode is None:
            self.current_mode = mode_name
    
    def set_mode_handlers(self, mode_identifier, clockwise_handler, counterclockwise_handler):
        """
        Установка обработчиков для конкретного режима
        
        Args:
            mode_identifier: Имя режима или индекс
            clockwise_handler: Функция для вращения по часовой стрелке
            counterclockwise_handler: Функция для вращения против часовой стрелки
        """
        mode = self._get_mode(mode_identifier)
        if mode:
            mode.set_clockwise_handler(clockwise_handler)
            mode.set_counterclockwise_handler(counterclockwise_handler)
    
    def _get_mode(self, mode_identifier):
        """Получение объекта режима по идентификатору"""
        if isinstance(mode_identifier, int):
            mode_names = list(self.modes.keys())
            if 0 <= mode_identifier < len(mode_names):
                return self.modes[mode_names[mode_identifier]]
        elif mode_identifier in self.modes:
            return self.modes[mode_identifier]
        return None
    
    def set_mode(self, mode_identifier):
        """
        Установка текущего режима работы
        
        Args:
            mode_identifier: Имя режима или индекс в списке режимов
        """
        
        if isinstance(mode_identifier, int):
            mode_names = list(self.modes.keys())
            if 0 <= mode_identifier < len(mode_names):
                self.current_mode = mode_names[mode_identifier]
                self.mode_index = mode_identifier
        elif mode_identifier in self.modes:
            self.current_mode = mode_identifier
            mode_names = list(self.modes.keys())
            self.mode_index = mode_names.index(mode_identifier)
        
        if self.mode_change_callback:
            self.mode_change_callback(self.current_mode)
    
    def next_mode(self):
        """Переключение на следующий режим"""
        
        mode_names = list(self.modes.keys())
        if mode_names:
            self.mode_index = (self.mode_index + 1) % len(mode_names)
            self.current_mode = mode_names[self.mode_index]
            
            if self.mode_change_callback:
                self.mode_change_callback(self.current_mode)
    
    def set_rotation_callback(self, callback):
        """Установка callback для вращения энкодера"""
        self.rotation_callback = callback
    
    def set_button_press_callback(self, callback):
        """Установка callback для короткого нажатия кнопки"""
        self.button_press_callback = callback
    
    def set_button_hold_callback(self, callback):
        """Установка callback для длинного нажатия кнопки"""
        self.button_hold_callback = callback
    
    def set_mode_change_callback(self, callback):
        """Установка callback для смены режима"""
        self.mode_change_callback = callback
    
    def get_current_mode(self):
        """Получение имени текущего режима"""
        return self.current_mode
    
    def get_available_modes(self):
        """Получение списка доступных режимов"""
        return list(self.modes.keys())


# Пример использования
if __name__ == "__main__":
    
    # Конкретные функции-обработчики
    def volume_up():
        print("Увеличиваем громкость")
    
    def volume_down():
        print("Уменьшаем громкость")
    
    def brightness_up():
        print("Увеличиваем яркость")
    
    def brightness_down():
        print("Уменьшаем яркость")
    
    def on_rotation(action, direction):
        print(f"Encoder rotated {direction}: {action}")
    
    def on_button_press():
        print("Button pressed - switching mode")
        encoder.next_mode()
    
    def on_button_hold():
        print("Button held - reset")
    
    def on_mode_change(mode_name):
        print(f"Mode changed to: {mode_name}")
    
    # Создание единственного экземпляра обработчика
    encoder = EncoderHandler(pin_a=22, pin_b=23, pin_button=24, hold_time=2)
    
    # Создание кастомных режимов
    class VolumeMode(EncoderMode):
        def get_name(self):
            return "volume"
    
    class BrightnessMode(EncoderMode):
        def get_name(self):
            return "brightness"
    
    # Добавление режимов в обработчик
    volume_mode = VolumeMode(volume_up, volume_down)
    brightness_mode = BrightnessMode(brightness_up, brightness_down)
    
    encoder.add_mode(volume_mode)
    encoder.add_mode(brightness_mode)
    
    # # Установка обработчиков для каждого режима
    # encoder.set_mode_handlers("volume", volume_up, volume_down)
    # encoder.set_mode_handlers("brightness", brightness_up, brightness_down)
    
    # Установка начального режима
    encoder.set_mode("volume")
    
    # Установка callback функций для дополнительной обработки
    encoder.set_rotation_callback(on_rotation)
    encoder.set_button_press_callback(on_button_press)
    encoder.set_button_hold_callback(on_button_hold)
    encoder.set_mode_change_callback(on_mode_change)
    
    # Запуск обработчика
    encoder.start()
    print("Encoder handler started with interrupts. Press Ctrl+C to stop.")
    
    # Обработка Ctrl+C для graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived Ctrl+C")
        encoder.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Главный цикл
        while True:
            print("aaa")
            time.sleep(10)
    except KeyboardInterrupt:
        print("Stopping...")
        encoder.stop()
        print("Encoder handler stopped.")