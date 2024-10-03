import pyautogui
from pynput import mouse
import time

print('Press Ctrl-C to quit.')

# Keep track of the time between clicks to detect double-click
last_click_time = 0

def on_click(x, y, button, pressed):
    global last_click_time
    if pressed:
        current_time = time.time()
        # If the second click happens within 0.3 seconds, treat it as a double-click
        if current_time - last_click_time < 0.3:
            print(f"Double click detected at X: {x} Y: {y}. Exiting program.")
            return False  # This stops the listener and ends the program
        else:
            last_click_time = current_time
            print(f"Mouse clicked at X: {x} Y: {y}")

# Start the mouse listener
with mouse.Listener(on_click=on_click) as listener:
    listener.join()
