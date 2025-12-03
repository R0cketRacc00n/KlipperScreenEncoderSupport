import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from  ks_includes.widgets.spinentry import SpinEntry

class Encnum(Gtk.Box):
    def __init__(self, screen, change_temp, pid_calibrate, close_function):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.change_temp = change_temp
        self.pid_calibrate = pid_calibrate
        self.screen = screen
        self._gtk = screen.gtk
        self.close_function = close_function
        
        self.labels = {}
        # Создаем счетчик
        self.labels['entry'] = SpinEntry(screen, min_val=0, max_val=300, step=1, initial_value=0)
        self.labels['entry'].connect("changed", self.on_selection_changed)
        self.connect("show", self.on_show)
        self.connect("parent-set", self.on_parent_set)
        
        buttons_config = [
            ('Ok', 'complete', _('OK'), 'color3', self.on_ok_clicked, (0, 0)),
            ('cancel', 'cancel', _('Cancel'), 'color2', self.close_function, (1, 0)),
            ('cooldown', 'cool-down', _('Cooldown'), 'color4', self.on_cooldown_clicked, (0, 1)),
            ('calibrate', 'heat-up', _('Calibrate'), 'color3', self.on_calibrate_clicked, (1, 1))
        ]
        
        # Создаем сетку для кнопок
        btn_grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        btn_grid.set_direction(Gtk.TextDirection.LTR)
        btn_grid.get_style_context().add_class('encnum')      
        
        # Создаем кнопки
        if self.screen.vertical_mode:
            position = Gtk.PositionType.LEFT
            height = self._gtk.font_size * 5
        else:
            position = Gtk.PositionType.TOP
            height = self._gtk.font_size * 4
            
        for key, icon, label, style, handler, (col, row) in buttons_config:
            btn = self._gtk.Button(icon, label, style=style, position=position)
            btn.connect("clicked", handler)
            btn.set_size_request(-1, height)
            self.labels[key] = btn
            btn_grid.attach(btn, col, row, 1, 1)

        # Упаковываем элементы интерфейса
        self.add(self.labels['entry'])
        self.add(btn_grid)
        
        # Инициализируем состояние кнопки Calibrate
        self.on_selection_changed()

    def show_pid(self, can_pid):
        self.labels['calibrate'].set_visible(can_pid)

    def on_selection_changed(self, *args):
        """Обновляет состояние кнопки Calibrate  и Ok в зависимости от выбранного значения"""
        new_temp = self.validate_temp(self.labels['entry'].value)
        self.labels['Ok'].set_sensitive(new_temp is not None and new_temp > 0)
        self.labels['calibrate'].set_sensitive(new_temp is not None and new_temp >= 50)

    def on_calibrate_clicked(self, widget):
        """Обработчик нажатия кнопки Calibrate"""
        temp = self.validate_temp(self.labels['entry'].value)
        if temp is not None:
            self.pid_calibrate(temp)

    def on_ok_clicked(self, widget):
        """Обработчик нажатия кнопки Ok"""
        temp = self.validate_temp(self.labels['entry'].value)
        if temp is not None:
            self.change_temp(temp)
            
    def clear(self, value=0):
        self.labels['entry'].value = value if value is not None else 0
        self.labels['cooldown'].set_sensitive(value is not None and value > 0 )

    def on_cooldown_clicked(self, *args):
        self.change_temp(0)

    def on_show(self, widget):
        # Устанавливаем фокус на поле ввода при показе виджета
        self.labels['entry'].grab_focus()

    def on_parent_set(self, widget, old_parent):
        if self.get_parent() is not None and not self.is_visible:
            self.show()
        elif self.get_parent() is None:
            # Виджет был удален из интерфейса
            self.hide()

    @staticmethod
    def validate_temp(temp):
        """Проверка корректности температуры"""
        try:
            return int(temp)
        except ValueError:
            return None