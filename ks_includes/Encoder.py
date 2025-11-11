import threading
import time
import signal
import sys
from abc import ABC, abstractmethod

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("RPi.GPIO not available - using mock mode")

class EncoderMode(ABC):
    """Абстрактный базовый класс для режимов энкодера"""
    
    def __init__(self):
        self.clockwise_handler = None
        self.counterclockwise_handler = None
    
    @abstractmethod
    def get_name(self):
        """Возвращает имя режима"""
        pass
    
    def set_clockwise_handler(self, handler):
        """Установка обработчика для вращения по часовой стрелке"""
        self.clockwise_handler = handler
    
    def set_counterclockwise_handler(self, handler):
        """Установка обработчика для вращения против часовой стрелки"""
        self.counterclockwise_handler = handler
    
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
    Класс для обработки событий энкодера в отдельном потоке
    с поддержкой различных режимов работы
    """
    
    def __init__(self, pin_a=22, pin_b=23, pin_button=24, hold_time=3, 
                                    use_gpio=True, debounce_delay=0.1):
        """
        Инициализация обработчика энкодера
        
        Args:
            pin_a: Пин канала A энкодера
            pin_b: Пин канала B энкодера  
            pin_button: Пин кнопки энкодера
            hold_time: Время удержания кнопки для длинного нажатия
            use_gpio: Использовать реальный GPIO (False для тестирования)
        """
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_button = pin_button
        self.hold_time = hold_time
        self.use_gpio = use_gpio and GPIO_AVAILABLE
        
        # Состояние
        self.running = False
        self.thread = None
        self.encoder_value = 0
        self.last_encoded = 0
        self.last_button_state = 1  # Кнопка не нажата
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
        
        # Инициализация GPIO
        if self.use_gpio:
            self._setup_gpio()
            
        # Защита от дребезга
        self.debounce_delay = debounce_delay
        self.last_encoder_time = 0
        self.last_button_time = 0
    
    def _setup_gpio(self):
        """Настройка GPIO"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
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
            # По индексу
            mode_names = list(self.modes.keys())
            if 0 <= mode_identifier < len(mode_names):
                self.current_mode = mode_names[mode_identifier]
                self.mode_index = mode_identifier
        elif mode_identifier in self.modes:
            # По имени
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
    
    def _read_encoder(self):
        """Чтение состояния энкодера"""
        if not self.use_gpio:
            return 0
        
        current_time = time.time()
        
        # Защита от дребезга - игнорируем слишком частые срабатывания
        if current_time - self.last_encoder_time < self.debounce_delay:
            return 0
            
        MSB = GPIO.input(self.pin_a)
        LSB = GPIO.input(self.pin_b)
        
        encoded = (MSB << 1) | LSB
        sum_val = (self.last_encoded << 2) | encoded
        
        if sum_val == 0b1101 or sum_val == 0b0100 or sum_val == 0b0010 or sum_val == 0b1011:
            self.encoder_value += 1
            self.last_encoder_time = current_time
        if sum_val == 0b1110 or sum_val == 0b0111 or sum_val == 0b0001 or sum_val == 0b1000:
            self.encoder_value -= 1
            self.last_encoder_time = current_time
        
        
        self.last_encoded = encoded
        return self.encoder_value
    
    def _handle_rotation(self):
        """Обработка вращения энкодера"""
        value = self._read_encoder()
        
        if value > 0:
            if self.current_mode:
                action_result = self.modes[self.current_mode].handle_clockwise()
                if self.rotation_callback:
                    self.rotation_callback(action_result, "clockwise")
            self.encoder_value = 0
        elif value < 0:
            if self.current_mode:
                action_result = self.modes[self.current_mode].handle_counterclockwise()
                if self.rotation_callback:
                    self.rotation_callback(action_result, "counterclockwise")
            self.encoder_value = 0
    
    def _handle_button(self):
        """Обработка нажатия кнопки"""
        if not self.use_gpio:
            return
            
        current_state = GPIO.input(self.pin_button)
        
        # Обнаружение нажатия (переход от 1 к 0)
        if current_state == 0 and self.last_button_state == 1:
            self.button_press_time = time.time()
            self.button_held = False
        
        # Обнаружение отпускания (переход от 0 к 1)
        elif current_state == 1 and self.last_button_state == 0:
            press_duration = time.time() - self.button_press_time
            
            if not self.button_held and self.button_press_callback:
                # Короткое нажатие
                self.button_press_callback()
            elif self.button_held and self.button_hold_callback:
                # Длинное нажатие уже обработано
                pass
        
        # Проверка длинного нажатия
        if current_state == 0 and not self.button_held:
            if time.time() - self.button_press_time >= self.hold_time:
                self.button_held = True
                if self.button_hold_callback:
                    self.button_hold_callback()
        
        self.last_button_state = current_state
    
    def _worker(self):
        """Рабочий цикл в отдельном потоке"""
        while self.running:
            self._handle_rotation()
            self._handle_button()
            time.sleep(0.2)  # 10ms delay
    
    def start(self):
        """Запуск обработчика в отдельном потоке"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._worker)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Остановка обработчика"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        if self.use_gpio:
            GPIO.cleanup()
    
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

# Пример использования с полностью кастомными режимами
if __name__ == "__main__":
    
    # Конкретные функции-обработчики
    def volume_up():
        print("Увеличиваем громкость")
        # Здесь код для увеличения громкости
    
    def volume_down():
        print("Уменьшаем громкость")
        # Здесь код для уменьшения громкости
    
    def brightness_up():
        print("Увеличиваем яркость")
        # Здесь код для увеличения яркости
    
    def brightness_down():
        print("Уменьшаем яркость")
        # Здесь код для уменьшения яркости
    
    def type_aa():
        print("Вводим AA")
        # Здесь код для ввода текста "AA"
    
    def type_bb():
        print("Вводим BB")
        # Здесь код для ввода текста "BB"
    
    def on_rotation(action, direction):
        print(f"Encoder rotated {direction}: {action}")
    
    def on_button_press():
        print("Button pressed - switching mode")
        encoder.next_mode()
    
    def on_button_hold():
        print("Button held - special action")
        # Действие при длинном нажатии
    
    def on_mode_change(mode_name):
        print(f"Mode changed to: {mode_name}")
    
    # Создание и настройка обработчика
    encoder = EncoderHandler()  # use_gpio=False для тестирования
    
    # Создание кастомных режимов
    class VolumeMode(EncoderMode):
        def get_name(self):
            return "VolumeMode"
    
    class BrightnessMode(EncoderMode):
        def get_name(self):
            return "BrightnessMode"
    
    class TextMode(EncoderMode):
        def get_name(self):
            return "TextMode"
    
    # Добавление режимов в обработчик
    volume_mode = VolumeMode()
    brightness_mode = BrightnessMode()
    text_mode = TextMode()
    
    encoder.add_mode(volume_mode)
    encoder.add_mode(brightness_mode)
    encoder.add_mode(text_mode)
    
    # Установка обработчиков для каждого режима
    encoder.set_mode_handlers("VolumeMode", volume_up, volume_down)
    encoder.set_mode_handlers("BrightnessMode", brightness_up, brightness_down)
    encoder.set_mode_handlers("TextMode", type_aa, type_bb)
    
    # Установка callback функций для дополнительной обработки
    encoder.set_rotation_callback(on_rotation)
    encoder.set_button_press_callback(on_button_press)
    encoder.set_button_hold_callback(on_button_hold)
    encoder.set_mode_change_callback(on_mode_change)
    
    # Запуск обработчика
    encoder.start()
    print("Encoder handler started. Press Ctrl+C to stop.")
    
    try:
        # Главный цикл
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        encoder.stop()
        print("Encoder handler stopped.")