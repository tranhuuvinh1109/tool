import pyautogui
import time
from pynput import mouse

# Coordinates where you want to auto-click (e.g., X: 278, Y: 533)
x_position = 2487
y_position = 15

# Flag to control when to stop the auto-clicker
running = True

# Function to handle mouse clicks
def on_click(x, y, button, pressed):
    global running
    # Stop the program if the right mouse button is clicked
    if button == mouse.Button.right and pressed:
        print("Right-click detected. Stopping the auto-clicker.")
        running = False
        return False  # Stop the listener

# Start listening for mouse clicks
listener = mouse.Listener(on_click=on_click)
listener.start()

# Wait for 5 seconds before starting the auto clicker
time.sleep(10)

# Auto click at the specific position until the right-click is detected
while running:
    # Perform a left mouse click at the specified position
    pyautogui.click(x=x_position, y=y_position)
    
    # Set the interval between clicks (e.g., 1 second)
    time.sleep(10)

# Ensure the listener stops
listener.join()
