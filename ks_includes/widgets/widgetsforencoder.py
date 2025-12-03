import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

screen = None

def set_global_screen(s):
    global screen
    screen = s

class EncComboBox(Gtk.ComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect("notify::popup-shown", self._on_popup_shown_changed)
        
    @classmethod
    def new_with_model(cls, model):
        obj = cls()
        obj.set_model(model)
        return obj

    def _on_popup_shown_changed(self, widget, gparam):
        if screen is None:
            logging.error(f"screen is not set, run set_global_screen before usage widgetsforencoder module ")
            return
            
        style_context = self.get_style_context()
        if self.props.popup_shown:
            style_context.add_class('active')
            screen.encoder_arrow_mode()
        else:
            style_context.remove_class('active')
            screen.encoder_focus_mode()
        return False
    

class EncComboBoxText(Gtk.ComboBoxText):
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect("notify::popup-shown", self._on_popup_shown_changed)
        
    def _on_popup_shown_changed(self, widget, gparam):
        if screen is None:
            logging.error(f"screen is not set, run set_global_screen before usage widgetsforencoder module ")
            return
            
        style_context = self.get_style_context()
        if self.props.popup_shown:
            style_context.add_class('active')
            screen.encoder_arrow_mode()
        else:
            style_context.remove_class('active')
            screen.encoder_focus_mode()
        return False

class EncScale(Gtk.Scale):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect("key-press-event", self._on_key_press)
        self.connect("value-changed", lambda widget: self.emit("button-release-event", Gdk.Event.new(Gdk.EventType.BUTTON_RELEASE)))

    @classmethod
    def new_with_range(cls, orientation, min=0, max=10, step=1):
        # Создаем adjustment для шкалы
        adjustment = Gtk.Adjustment(value=min, lower=min, upper=max, 
                                  step_increment=step, page_increment=step * 5)
        
        # Создаем экземпляр с adjustment и ориентацией
        scale = cls(adjustment=adjustment, orientation=orientation)
        return scale
        
    def _on_key_press(self, widget, event):
        if screen is None:
            logging.error(f"screen is not set, run set_global_screen before usage widgetsforencoder module ")
            return

        if event.keyval == Gdk.KEY_Return or event.keyval == Gdk.KEY_KP_Enter:
            if self.get_style_context().has_class('active'):
                self.get_style_context().remove_class('active')
                if screen:
                    screen.encoder_focus_mode()
                self.emit("button-release-event", Gdk.Event.new(Gdk.EventType.BUTTON_RELEASE))
            else:
                self.get_style_context().add_class('active')
                if screen:
                    screen.encoder_arrow_mode()
            return True
        return False
    
    