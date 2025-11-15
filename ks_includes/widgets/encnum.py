import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

class Encnum(Gtk.Box):
    def __init__(self, screen, change_temp, pid_calibrate, close_function):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.change_temp = change_temp
        self.pid_calibrate = pid_calibrate
        self.screen = screen
        self._gtk = screen.gtk
        self.close_function = close_function
        
        # Создаем выпадающий список с числами 0-300
        self.labels = {}
        self.labels['entry'] = Gtk.ComboBoxText()
        for i in range(301):
            self.labels['entry'].append_text(str(i))
        self.labels['entry'].set_active(0)  # По умолчанию выбран 0
        self.labels['entry'].connect("changed", self.on_selection_changed)
        if self.screen.encoder_support:
            self.labels['entry'].connect("popup", lambda x: self.screen.encoder_arrow_mode())
            self.labels['entry'].connect("popdown", lambda x: self.screen.encoder_focus_mode())
                
        # Создаем кнопки
        self.labels['Ok'] = self._gtk.Button('complete', _('OK'), style="color1")
        self.labels['cancel'] = self._gtk.Button('cancel', _('Cancel'), style="color2")
        self.labels['calibrate'] = self._gtk.Button('heat-up', _('Calibrate'), style="color4")
        self.labels['cooldown'] = self._gtk.Button('cool-down', _('Cooldown'), style="color3")
        self.labels['calibrate'].set_sensitive(False)
        
        # Устанавливаем одинаковую высоту для всех кнопок
        if self.screen.vertical_mode:
            height = self._gtk.font_size * 4
        else:
            height = self._gtk.font_size * 5
        self.labels['entry'].set_size_request(-1, height)
        self.labels['Ok'].set_size_request(-1, height)
        self.labels['cancel'].set_size_request(-1, height)
        self.labels['calibrate'].set_size_request(-1, height)
        self.labels['cooldown'].set_size_request(-1, height)
        
        # Подключаем обработчики
        self.labels['Ok'].connect("clicked", self.on_ok_clicked)
        self.labels['cancel'].connect("clicked", self.close_function)
        self.labels['calibrate'].connect("clicked", self.on_calibrate_clicked)
        self.labels['cooldown'].connect("clicked", self.on_cooldown_clicked)
        
        # Создаем сетку для кнопок
        btn_grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        btn_grid.set_direction(Gtk.TextDirection.LTR)
        btn_grid.get_style_context().add_class('encnum')
        
        # Добавляем кнопки в сетку
        btn_grid.attach(self.labels['Ok'], 0, 0, 1, 1)
        btn_grid.attach(self.labels['cancel'], 1 ,0, 1, 1)
        btn_grid.attach(self.labels['cooldown'], 0, 1, 1, 1)
        btn_grid.attach(self.labels['calibrate'], 1, 1, 1, 1)

        # Упаковываем элементы интерфейса
        self.add(self.labels['entry'])
        self.add(btn_grid)
        
        # Инициализируем состояние кнопки Calibrate
        self.on_selection_changed()

    def show_pid(self, can_pid):
        self.labels['calibrate'].set_visible(can_pid)

    def on_selection_changed(self, *args):
        """Обновляет состояние кнопки Calibrate в зависимости от выбранного значения"""
        self.screen.encoder_focus_mode()
        new_temp = self.validate_temp(self.labels['entry'].get_active_text())
        self.labels['calibrate'].set_sensitive(new_temp is not None and new_temp > 9)

    def on_calibrate_clicked(self, widget):
        """Обработчик нажатия кнопки Calibrate"""
        temp = self.validate_temp(self.labels['entry'].get_active_text())
        if temp is not None:
            self.pid_calibrate(temp)

    def on_ok_clicked(self, widget):
        """Обработчик нажатия кнопки OK"""
        temp = self.validate_temp(self.labels['entry'].get_active_text())
        if temp is not None:
            self.change_temp(temp)
            
    def clear(self):
        self.labels['entry'].set_active(0)
    
    def on_cooldown_clicked(self, *args):
        self.change_temp(0)

    @staticmethod
    def validate_temp(temp):
        """Проверка корректности температуры"""
        try:
            return float(temp)
        except ValueError:
            return None