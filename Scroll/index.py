import pyautogui
import time
import random
from pynput import mouse
from datetime import datetime

# Coordinates where you want to start the scrolling
x_position = 2548
y_position = 299

# Flag to control when to stop the auto-scroller
running = True

# Time tracker and random interval for Alt+Tab switch
last_switch_time = time.time()
next_switch_interval = random.randint(10, 60)

# Function to handle mouse clicks
def on_click(x, y, button, pressed):
    global running
    if button == mouse.Button.right and pressed:
        print("Right-click detected. Stopping the auto-scroller.")
        running = False
        return False  # Stop the listener

# Start listening for mouse clicks
listener = mouse.Listener(on_click=on_click)
listener.start()

# Wait before starting auto-scroll
print("Waiting for 10 seconds before starting...")
time.sleep(10)

# Define stop time
stop_hour = 19
stop_minute = 45

# Auto-scroll until stopped manually or time limit reached
while running:
    now = datetime.now()
    if now.hour > stop_hour or (now.hour == stop_hour and now.minute >= stop_minute):
        print("Reached 19:45. Stopping the auto-scroller.")
        running = False
        break

    # Scroll up
    pyautogui.moveTo(x_position, y_position)
    pyautogui.scroll(1000)
    time.sleep(5)

    # Scroll down
    pyautogui.moveTo(x_position, y_position)
    pyautogui.scroll(-1000)
    time.sleep(5)

    # Check if it's time to Alt+Tab
    current_time = time.time()
    if current_time - last_switch_time >= next_switch_interval:
        print(f"Performing Alt+Tab to switch window after {next_switch_interval} seconds...")
        pyautogui.keyDown('alt')
        pyautogui.press('tab')
        pyautogui.keyUp('alt')
        last_switch_time = current_time
        next_switch_interval = random.randint(10, 180)  # Set new random interval

# Ensure the listener stops properly
listener.join()
