#!/usr/bin/env python3
# test_xdotool_encoder.py
import logging
import time
import signal
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from ks_includes.Encoder import EncoderController
    print("✅ Encoder module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Encoder module: {e}")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def signal_handler(sig, frame):
    print("\nStopping encoder...")
    sys.exit(0)

def test_encoder():
    print("Testing xdotool-based encoder...")
    
    encoder = EncoderController()
    
    # Установка обработчика сигналов для graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Запускаем энкодер
    if encoder.start():
        print("✅ Encoder started successfully")
        print("Rotate the encoder to test. Press Ctrl+C to stop.")
        
        # Бесконечный цикл чтобы держать программу активной
        try:
            while encoder.is_running():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nInterrupted by user")
    else:
        print("❌ Failed to start encoder")
    
    encoder.stop()
    print("Encoder test completed")

if __name__ == "__main__":
    test_encoder()