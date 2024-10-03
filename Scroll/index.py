import pyautogui
import time
from pynput import mouse

# Coordinates where you want to start the scrolling (e.g., X: 278, Y: 533)
x_position = 949
y_position = 466

# Flag to control when to stop the auto-scroller
running = True

# Function to handle mouse clicks
def on_click(x, y, button, pressed):
    global running
    # Stop the program if the right mouse button is clicked
    if button == mouse.Button.right and pressed:
        print("Right-click detected. Stopping the auto-scroller.")
        running = False
        return False  # Stop the listener

# Start listening for mouse clicks
listener = mouse.Listener(on_click=on_click)
listener.start()

# Wait for 5 seconds before starting the auto scroll
time.sleep(10)

# Auto scroll at the specific position until the right-click is detected
while running:
    # Scroll up by a specified amount at the given position
    pyautogui.moveTo(x_position, y_position)
    pyautogui.scroll(1000)  # Scroll up (positive values scroll up)
    
    # Set the interval between scrolls (e.g., 1 second)
    time.sleep(5)
    
    # Scroll down by a specified amount at the given position
    pyautogui.moveTo(x_position, y_position)
    pyautogui.scroll(-1000)  # Scroll down (negative values scroll down)
    
    # Set the interval between scrolls
    time.sleep(5)

# Ensure the listener stops
listener.join()

