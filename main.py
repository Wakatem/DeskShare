import mss.windows
import pygetwindow as gw
import mss
import time
import cv2
import numpy as np
from screeninfo import get_monitors
from pyvda import AppView, get_apps_by_z_order, VirtualDesktop, get_virtual_desktops
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image
import ctypes
import threading
from multiprocessing import Process, Value
from pygame.locals import *


def resize_frame(frame, target_width=1920):
    # Convert raw bytes to a numpy array
    if not isinstance(frame, np.ndarray):
        img_np = np.array(frame)
    else:
        img_np = frame
    
    # Resize the frame
    height, width = img_np.shape[:2]
    target_height = int((target_width / width) * height)
    resized_img = cv2.resize(img_np, (target_width, target_height))
    
    return resized_img


def compress_frame(frame, quality):
    # Convert raw bytes to a numpy array
    if not isinstance(frame, np.ndarray):
        img_np = np.array(frame)
    else:
        img_np = frame
    
    # Resize the frame
    # height, width = img_np.shape[:2]
    # target_height = int((target_width / width) * height)
    # resized_img = cv2.resize(img_np, (target_width, target_height))
    
    # Compress the frame (e.g., JPEG compression)
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, compressed_img = cv2.imencode('.jpg', frame, encode_param)
    
    return cv2.imdecode(compressed_img, 1)



def get_window_coordinates(window_title):
    # Get the window object for the specific app
    window = gw.getWindowsWithTitle(window_title)
    if window:
        win = window[0]
        return win
    else:
        raise Exception(f"Window with title '{window_title}' not found.")




def share_desktop():
    global fps, stop_sharing, selected_desktop

    frame_interval = 1.0 / fps
    primary_monitor = get_monitors()[0]
    left, top, width, height = primary_monitor.x, primary_monitor.y, primary_monitor.width, primary_monitor.height
    
    monitor = {"top": top, "left": left, "width": width, "height": height}
    last_frame_time = time.time()

    cv2.namedWindow('DeskShare', cv2.WINDOW_NORMAL)
    cv2.setWindowProperty('DeskShare', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    with mss.mss() as sct:

        while not stop_sharing.value:
            activeWindow = gw.getActiveWindow()

            # Avoid capturing the Task View window
            if activeWindow and activeWindow.title != "Task View":
                if VirtualDesktop.current().number == selected_desktop:
                    img = sct.grab(monitor)
                    img = np.array(img)
                    imgUMAT = cv2.UMat(img)

                    cv2.imshow("DeskShare", imgUMAT)

            # Calculate sleep time to maintain target FPS
            sleep_time = frame_interval - (time.time() - last_frame_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

            last_frame_time = time.time()
            cv2.waitKey(1)
    
    cv2.destroyAllWindows()
    print("Stopped sharing")


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
        global selected_desktop, stop_sharing
        stop_sharing.value = False
        selected_desktop = number
        icon.update_menu()
        
        share_desktop()

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

    selected_desktop = 0
    fps = 60
    stop_sharing = Value('b', False)
    # stop_sharing = False
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