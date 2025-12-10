# Copyright (c) 2025 Azat Fayzrakhmanov
# Author: Azat Fayzrakhmanov <k1b0rg.azat@gmail.com>
#
# Encoder handler module for KlipperScreen
# Supports rotary encoder with button, multiple operating modes,
# interrupt-based GPIO handling (RPi.GPIO), speed-adaptive rotation,
# and long/short button press detection.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import threading
import math
import time
import signal
import sys
import logging
logger = logging.getLogger("KlipperScreen.Encoder")
from abc import ABC, abstractmethod

try:
    import RPi.GPIO as GPIO  # USE rpi-lgpio python package
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.error("rpi-lgpio not available")

class EncoderMode(ABC):
    """Abstract base class for encoder modes"""

    def __init__(self, clockwise_handler=None, counterclockwise_handler=None,
                 clockwise_boosthandler=None, counterclockwise_boosthandler=None):
        self.clockwise_handler = clockwise_handler
        self.counterclockwise_handler = counterclockwise_handler
        self.clockwise_boosthandler = clockwise_boosthandler
        self.counterclockwise_boosthandler = counterclockwise_boosthandler

    @abstractmethod
    def get_name(self):
        """Returns the name of the mode"""
        pass
    
    @staticmethod
    def repeat(func, repeat=1):
        for i in range(repeat):
            func()

    def set_clockwise_handler(self, handler, boosthandler=None):
        """Set handler for clockwise rotation"""
        self.clockwise_handler = handler  # Fixed: was clockwise_handler
        self.clockwise_boosthandler = boosthandler

    def set_counterclockwise_handler(self, handler, boosthandler=None):
        """Set handler for counterclockwise rotation"""
        self.counterclockwise_handler = handler  # Fixed: was counterclockwise_handler
        self.counterclockwise_boosthandler = boosthandler

    def handle_clockwise(self, boost=False, repeatcount=1):
        """Handle clockwise rotation"""
        if self.clockwise_boosthandler and boost:
            self.repeat(self.clockwise_boosthandler, repeatcount)
        elif self.clockwise_handler:
            self.repeat(self.clockwise_handler, repeatcount)
        return self.get_name() + "_clockwise"

    def handle_counterclockwise(self, boost=False, repeatcount=1):
        """Handle counterclockwise rotation"""
        if self.counterclockwise_boosthandler and boost:
            self.repeat(self.counterclockwise_boosthandler, repeatcount)
        elif self.counterclockwise_handler:
            self.repeat(self.counterclockwise_handler, repeatcount)
        return self.get_name() + "_counterclockwise"


class EncoderHandler:
    """
    Class for handling encoder events using interrupts
    and supporting various operating modes
    """

    def __init__(self, pin_a=22, pin_b=23, pin_button=24, hold_time=3):
        """
        Initialize the encoder handler

        Args:
            pin_a: Encoder channel A pin (default 22)
            pin_b: Encoder channel B pin (default 23)
            pin_button: Encoder button pin (default 24)
            hold_time: Button hold duration for long press (seconds)
        """

        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_button = pin_button
        self.hold_time = hold_time
        self.use_gpio = GPIO_AVAILABLE

        # Encoder state
        self.last_state = 0
        self.encoder_position = 0
        self.encoder_last_time = time.monotonic()

        # Button state
        self.last_button_state = 1
        self.button_press_time = 0

        # Operating modes
        self.modes = {}
        self.current_mode = None
        self.mode_index = 0

        # Callback functions
        self.rotation_callback = None
        self.button_press_callback = None
        self.button_hold_callback = None
        self.mode_change_callback = None

        # Running flag
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()

    def _setup_gpio(self):
        """Configure GPIO pins and interrupts"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pin_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info("GPIO setup successful")
        # Configure encoder interrupts with built-in debouncing

        GPIO.add_event_detect(self.pin_a, GPIO.BOTH, callback=self._handle_encoder, bouncetime=1)
        logger.info("GPIO setup for pin A successful")
        GPIO.add_event_detect(self.pin_b, GPIO.BOTH, callback=self._handle_encoder, bouncetime=1)
        logger.info("GPIO setup for pin B successful")
        # Configure button interrupt with built-in debouncing
        GPIO.add_event_detect(self.pin_button, GPIO.BOTH, callback=self._handle_button, bouncetime=5)
        self.last_state = (GPIO.input(self.pin_a) << 1) + GPIO.input(self.pin_b)

        logger.info("GPIO interrupts configured")

    def _cleanup_gpio(self):
        """Release GPIO pins and reset settings"""
        # Remove interrupt handlers
        GPIO.remove_event_detect(self.pin_a)
        GPIO.remove_event_detect(self.pin_b)
        GPIO.remove_event_detect(self.pin_button)

        # Set pins to safe state
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        GPIO.setup(self.pin_button, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        GPIO.cleanup()

        logger.info("GPIO pins released and reset")

    def _worker(self):
        """Worker loop in a separate thread"""
        # Initialize GPIO
        if self.use_gpio:
            try:
                self._setup_gpio()
                logger.info(f"GPIO initialized: A={self.pin_a}, B={self.pin_b}, BTN={self.pin_button}")
            except Exception as e:
                logger.error(f"GPIO setup error: {e} \n  A={self.pin_a}, B={self.pin_b}, BTN={self.pin_button}")
                self.use_gpio = False

        self.stop_event.wait()

        if self.use_gpio:
            self._cleanup_gpio()

    def start(self):
        """Start the encoder handler in a separate thread"""
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker)
        logger.info("Thread created")
        self.thread.daemon = False
        self.thread.start()
        logger.info("Thread started")

    def stop(self):
        """Stop the handler and clean up GPIO"""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.0)

    def _handle_encoder(self, channel):
        """Encoder interrupt handler"""
        if not self.running:
            return
        # Read current pin states
        state = ((self.last_state << 2) + (GPIO.input(self.pin_a) << 1) + GPIO.input(self.pin_b)) & 0b1111

        if state in [0b1101, 0b0100, 0b0010, 0b1011]:
            self.encoder_position += 1
        elif state in [0b1110, 0b1000, 0b0001, 0b0111]:
            self.encoder_position -= 1

        self.last_state = state
        if abs(self.encoder_position) >= 4:
            speed = max(0.05, min(0.5, time.monotonic() - self.encoder_last_time))
            if speed <= 0.05:
                count = 10
            elif speed >= 0.5:
                count = 1
            else:
                p = 1.4
                A = 2.223
                B = -0.329
                count = int(A * ((-math.log(speed)) ** p) + B) 

            if count > 5:
                boost = True
                count >>= 1 #divide 2
            else:
                boost = False

            if self.encoder_position > 0:
                """Call handler for clockwise rotation"""
                if self.current_mode and self.current_mode in self.modes:
                    action_result = self.modes[self.current_mode].handle_clockwise(boost, count)
                    if self.rotation_callback:
                        self.rotation_callback(action_result, "clockwise")
            else:
                """Call handler for counterclockwise rotation"""
                if self.current_mode and self.current_mode in self.modes:
                    action_result = self.modes[self.current_mode].handle_counterclockwise(boost, count)
                    if self.rotation_callback:
                        self.rotation_callback(action_result, "counterclockwise")
            self.encoder_last_time = time.monotonic()
            self.encoder_position = 0

    def _handle_button(self, channel):
        """Button interrupt handler"""
        if not self.running:
            return

        current_state = ((self.last_button_state << 1) + GPIO.input(self.pin_button)) & 0b11

        # Handle press (transition 1->0)
        if current_state == 0b10:
            self.button_press_time = time.monotonic()
            logging.info("Button down")

        # Handle release (transition 0->1)
        elif current_state == 0b01:
            press_duration = time.monotonic() - self.button_press_time
            logging.info("Button up")

            # Check for long press
            if press_duration >= (self.hold_time - 1):
                if self.button_hold_callback:
                    self.button_hold_callback()
            else:
                if self.button_press_callback:
                    # Short press
                    self.button_press_callback()

        self.last_button_state = current_state

    def add_mode(self, mode):
        """
        Add a new operating mode

        Args:
            mode: Instance of a class inherited from EncoderMode
        """
        mode_name = mode.get_name()
        self.modes[mode_name] = mode
        if self.current_mode is None:
            self.current_mode = mode_name

    def set_mode_handlers(self, mode_identifier,
            clockwise_handler, counterclockwise_handler,
            clockwise_boosthandler=None, counterclockwise_boosthandler=None
        ):
        """
        Set rotation handlers for a specific mode, including optional boost handlers.

        Args:
            mode_identifier (str or int): Mode name or index.
            clockwise_handler (callable): Function called on slow/normal clockwise rotation.
            counterclockwise_handler (callable): Function called on slow/normal counterclockwise rotation.
            clockwise_boosthandler (callable, optional): Function called on fast (boosted) clockwise rotation.
            counterclockwise_boosthandler (callable, optional): Function called on fast (boosted) counterclockwise rotation.
        """
        mode = self._get_mode(mode_identifier)
        if mode:
            mode.set_clockwise_handler(clockwise_handler, 
                                            boosthandler=clockwise_boosthandler)
            mode.set_counterclockwise_handler(counterclockwise_handler, 
                                     boosthandler=counterclockwise_boosthandler)

    def _get_mode(self, mode_identifier):
        """Get mode object by identifier"""
        if isinstance(mode_identifier, int):
            mode_names = list(self.modes.keys())
            if 0 <= mode_identifier < len(mode_names):
                return self.modes[mode_names[mode_identifier]]
        elif mode_identifier in self.modes:
            return self.modes[mode_identifier]
        return None

    def set_mode(self, mode_identifier):
        """
        Set the current operating mode

        Args:
            mode_identifier: Mode name or index in the list of modes
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
        """Switch to the next mode"""
        mode_names = list(self.modes.keys())
        if mode_names:
            self.mode_index = (self.mode_index + 1) % len(mode_names)
            self.current_mode = mode_names[self.mode_index]

            if self.mode_change_callback:
                self.mode_change_callback(self.current_mode)

    def set_rotation_callback(self, callback):
        """Set callback for encoder rotation"""
        self.rotation_callback = callback

    def set_button_press_callback(self, callback):
        """Set callback for short button press"""
        self.button_press_callback = callback

    def set_button_hold_callback(self, callback):
        """Set callback for long button press"""
        self.button_hold_callback = callback

    def set_mode_change_callback(self, callback):
        """Set callback for mode change"""
        self.mode_change_callback = callback

    def get_current_mode(self):
        """Get the name of the current mode"""
        return self.current_mode

    def get_available_modes(self):
        """Get a list of available modes"""
        return list(self.modes.keys())


# Usage example
if __name__ == "__main__":

    # Concrete handler functions
    def volume_up():
        print("Increasing volume")

    def volume_down():
        print("Decreasing volume")

    def brightness_up():
        print("Increasing brightness")

    def brightness_down():
        print("Decreasing brightness")

    def on_rotation(action, direction):
        print(f"Encoder rotated {direction}: {action}")

    def on_button_press():
        print("Button pressed - switching mode")
        encoder.next_mode()

    def on_button_hold():
        print("Button held - reset")

    def on_mode_change(mode_name):
        print(f"Mode changed to: {mode_name}")

    # Create a single encoder handler instance
    encoder = EncoderHandler(pin_a=22, pin_b=23, pin_button=24, hold_time=2)

    # Define custom modes
    class VolumeMode(EncoderMode):
        def get_name(self):
            return "volume"

    class BrightnessMode(EncoderMode):
        def get_name(self):
            return "brightness"

    # Add modes to handler
    volume_mode = VolumeMode(volume_up, volume_down)
    brightness_mode = BrightnessMode(brightness_up, brightness_down)

    encoder.add_mode(volume_mode)
    encoder.add_mode(brightness_mode)

    # # Set handlers for each mode
    # encoder.set_mode_handlers("volume", volume_up, volume_down)
    # encoder.set_mode_handlers("brightness", brightness_up, brightness_down)

    # Set initial mode
    encoder.set_mode("volume")

    # Set callback functions for additional processing
    encoder.set_rotation_callback(on_rotation)
    encoder.set_button_press_callback(on_button_press)
    encoder.set_button_hold_callback(on_button_hold)
    encoder.set_mode_change_callback(on_mode_change)

    # Start the handler
    encoder.start()
    print("Encoder handler started with interrupts. Press Ctrl+C to stop.")

    # Handle Ctrl+C for graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived Ctrl+C")
        encoder.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Main loop
        while True:
            # print("aaa")
            time.sleep(10)
    except KeyboardInterrupt:
        print("Stopping...")
        encoder.stop()
        print("Encoder handler stopped.")