from gi.repository import Gtk, Gdk

class SpinEntry(Gtk.Entry):
    def __init__(self, screen, min_val=0, max_val=100, step=1, page_step=10, initial_value=0):
        super().__init__()
        self.screen =screen
        # Устанавливаем начальные значения
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.page_step = page_step
        self._value = initial_value
        self.is_active = False

        # Настраиваем внешний вид и начальное значение
        self.set_text(str(initial_value))
        self.set_alignment(0.5)  # Выравнивание по центру
        self.set_width_chars(3)
        # Подключаем обработчики событий
        self.connect("key-press-event", self.on_key_press)
        self.connect("focus-out-event", self.on_focus_out)
        self.connect("changed", self.on_text_changed)
        # Блокируем события мыши с помощью лямбда-функций
        self.connect("enter-notify-event", lambda w, e: True)
        self.connect("leave-notify-event", lambda w, e: True)

        context = self.get_style_context()
        context.add_class("spin-entry")

    @property
    def value(self):
        """Возвращает текущее числовое значение"""
        return self._value

    @value.setter
    def value(self, new_value):
        """Устанавливает новое значение с проверкой диапазона"""
        # Ограничиваем значение минимальным и максимальным
        self._value = max(self.min_val, min(self.max_val, new_value))
        # Обновляем текст в Entry
        self.set_text(str(self._value))

    def on_text_changed(self, widget):
        """Обработчик изменения текста - преобразует текст в число"""
        text = self.get_text()
        if text:  # Если текст не пустой
            try:
                # Пытаемся преобразовать текст в число
                numeric_value = int(text)
                # Проверяем, находится ли значение в допустимом диапазоне
                if self.min_val <= numeric_value <= self.max_val:
                    self._value = numeric_value
            except ValueError:
                # Если преобразование не удалось, восстанавливаем предыдущее значение
                self.set_text(str(self._value))

    def on_key_press(self, widget, event):
        """Обработчик нажатия клавиш"""
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval)
        context = widget.get_style_context()

        if keyname == 'Return':
            # Переключаем активное состояние
            if self.is_active:
                context.remove_class('active')
                self.is_active = False
                self.screen.encoder_focus_mode()
            else:
                context.add_class('active')
                self.is_active = True
                self.screen.encoder_arrow_mode()
            return True

        elif keyname == 'Up':
            # Уменьшаем значение
            self.value = self._value - self.step
            return True

        elif keyname == 'Down':
            # Увеличиваем значение
            self.value = self._value + self.step
            return True

        elif keyname == 'Page_Up':
            # Уменьшаем значение на страничный шаг
            self.value = self._value - self.page_step
            return True

        elif keyname == 'Page_Down':
            # Увеличиваем значение на страничный шаг
            self.value = self._value + self.page_step
            return True

        else:
            return False

    def on_focus_out(self, widget, event):
        """Обработчик потери фокуса"""
        # Сбрасываем активное состояние при потере фокуса
        context = widget.get_style_context()
        if self.is_active:
            context.remove_class('active')
            self.is_active = False
        self.screen.encoder_focus_mode()
        # Валидируем и обновляем значение из текста
        self.on_text_changed(widget)

        return False

    def set_range(self, min_val, max_val):
        """Устанавливает минимальное и максимальное значение"""
        self.min_val = min_val
        self.max_val = max_val
        # Обновляем текущее значение с учетом нового диапазона
        self.value = self._value

    def set_increments(self, step, page_step=None):
        """Устанавливает шаг изменения (page_step игнорируется для совместимости)"""
        self.step = step

    def get_value(self):
        """Возвращает текущее значение (для совместимости с Gtk.SpinButton)"""
        return self._value

    def set_value(self, value):
        """Устанавливает значение (для совместимости с Gtk.SpinButton)"""
        self.value = value

    def get_value_as_int(self):
        """Возвращает значение как целое число"""
        return int(self._value)

    def get_value_as_float(self):
        """Возвращает значение как число с плавающей точкой"""
        return float(self._value)