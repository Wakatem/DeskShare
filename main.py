import mss.windows
import pygetwindow as gw
import mss
import time
import cv2
import numpy as np
from screeninfo import get_monitors
from pyvda import AppView, get_apps_by_z_order, VirtualDesktop, get_virtual_desktops
import win32gui
import win32con
import pystray
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw
import ctypes
import threading
from multiprocessing import Queue, Process, Value


def resize_and_compress_frame(frame, target_width=1920):
    # Convert raw bytes to a numpy array
    img_np = np.array(frame)
    
    # Resize the frame
    # height, width = img_np.shape[:2]
    # target_height = int((target_width / width) * height)
    # resized_img = cv2.resize(img_np, (target_width, target_height))
    
    # Compress the frame (e.g., JPEG compression)
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
    _, compressed_img = cv2.imencode('.jpg', img_np, encode_param)
    
    return cv2.imdecode(compressed_img, 1)



def get_window_coordinates(window_title):
    # Get the window object for the specific app
    window = gw.getWindowsWithTitle(window_title)
    if window:
        win = window[0]
        return win
    else:
        raise Exception(f"Window with title '{window_title}' not found.")


def grab(queue, stop_sharing, desktop_number):
    fps = 30
    primary_monitor = get_monitors()[0]
    left, top, width, height = primary_monitor.x, primary_monitor.y, primary_monitor.width, primary_monitor.height

    monitor = {"top": top, "left": left, "width": width, "height": height}
    
    with mss.mss() as sct:
        while not stop_sharing.value:
            # Avoid sharing screen when Task View is active
            active_window = gw.getActiveWindow()
            if active_window is not None and active_window.title == "Task View":
                continue

            # Capture the window region if selected desktop is the current one
            if VirtualDesktop.current().number == desktop_number:
                img = sct.grab(monitor)
                compressed_img = resize_and_compress_frame(img)
                queue.put(compressed_img)

            time.sleep(1/fps)
    
    print("Stopped capturing")


def display(queue, stop_sharing):
    cv2.namedWindow('DeskShare', cv2.WINDOW_NORMAL)
    cv2.setWindowProperty('DeskShare', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    while not stop_sharing.value:
        if not queue.empty():
            img = queue.get()
            if img is not None:
                img = np.array(img)
                cv2.imshow("DeskShare", img)
        cv2.waitKey(1)

    cv2.destroyAllWindows()
    print("Stopped displaying")



def update_desktops_menu(icon):
    global desktop_items, desktops_menu, quit_program
    while not quit_program:
        try:
            # Update the menu items to reflect the available virtual desktops
            if len(desktop_items) != len(get_virtual_desktops()):
                desktop_items = [item(f"Desktop {desktop.number}", select_desktop(desktop.number), checked=get_selected_desktop(desktop.number), radio=True) for desktop in get_virtual_desktops()]
                items_list = list(icon.menu.items)
                items_list[0] = item('Start Sharing', menu(*desktop_items))
                icon.menu = menu(*items_list)
                icon.update_menu()
        except Exception as e:
            print(f"An error occurred: {e}")
        time.sleep(2)

def get_selected_desktop(number):
    def inner(item):
        global selected_desktop
        return selected_desktop == number
    return inner

def select_desktop(number):
    def inner(icon, item):
        global selected_desktop, queue, stop_sharing
        stop_sharing.value = False
        selected_desktop = number
        icon.update_menu()

        Process(target=grab, args=(queue, stop_sharing, selected_desktop,)).start()
        Process(target=display, args=(queue, stop_sharing,)).start()

    return inner


def on_stop_sharing(icon, item):
    global stop_sharing, selected_desktop
    stop_sharing.value = True
    icon.notify(f"Sharing has been stopped")
    selected_desktop = 0

def quit(icon, item):
    global stop_sharing, update_thread, quit_program
    stop_sharing.value = True
    quit_program = True
    update_thread.join()
    icon.stop()


if __name__ == '__main__':
    # Make the application DPI aware to handle display scaling properly
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

    queue: Queue = Queue()
    selected_desktop = 0
    stop_sharing = Value('b', False)
    quit_program = False

    # Create a menu with all available virtual desktops
    desktop_items = [item(f"Desktop {desktop.number}", select_desktop(desktop.number), checked=get_selected_desktop(desktop.number), radio=True) for desktop in get_virtual_desktops()]
    desktops_menu = menu(*desktop_items)

    items_menu = menu(
        item('Start Sharing', desktops_menu),
        item('Stop Sharing', on_stop_sharing, enabled=lambda item: selected_desktop != 0),
        item('Quit', quit)
    )

    # Load the application icon
    icon_image = Image.open("icon.ico")
    tray_icon = icon('DeskShare', icon_image, menu=items_menu)

    # Start update_desktops_menu in a separate thread
    update_thread = threading.Thread(target=update_desktops_menu, args=(tray_icon,))
    update_thread.daemon = True
    update_thread.start()

    tray_icon.run()