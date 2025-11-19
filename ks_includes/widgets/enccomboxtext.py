import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

class EncComboBoxText(Gtk.ComboBoxText):
    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.connect("notify::popup-shown", self._on_popup_shown_changed)   
        
    def _on_popup_shown_changed(self, widget, gparam):
        # Это срабатывает ВСЕГДА: при popup(), popdown(), Esc, клик вне, выбор и т.д.
        if self.props.popup_shown:
            self.get_style_context().add_class('active')
            self.screen.encoder_arrow_mode() # крутим по списку
        else:
            self.get_style_context().remove_class('active')
            self.screen.encoder_focus_mode()  # обычный режим
