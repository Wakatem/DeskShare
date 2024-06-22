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

def get_window_coordinates(window_title):
    # Get the window object for the specific app
    window = gw.getWindowsWithTitle(window_title)
    if window:
        win = window[0]
        return win
    else:
        raise Exception(f"Window with title '{window_title}' not found.")


def record_and_show_window(desktop_number):
    global stop_sharing

    primary_monitor = get_monitors()[0]
    left, top, width, height = primary_monitor.x, primary_monitor.y, primary_monitor.width, primary_monitor.height

    cv2.startWindowThread()
    cv2.namedWindow('DeskShare', cv2.WINDOW_NORMAL)
    cv2.setWindowProperty('DeskShare', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    # cv2.resizeWindow('DeskShare', width, height)

    win: gw.Win32Window = get_window_coordinates("DeskShare")
    app_view = AppView(win._hWnd)
    new_desktop = VirtualDesktop.current()
    app_view.move(new_desktop)

    with mss.mss() as sct:
        while not stop_sharing:
            if VirtualDesktop.current().number == desktop_number:
                # Capture the window region
                monitor = {"top": top, "left": left, "width": width, "height": height}
                img = sct.grab(monitor)
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)

                cv2.imshow("DeskShare", frame)

            # Allow for keyboard and mouse interrupt
            cv2.waitKey(1)

    cv2.destroyAllWindows()




def get_selected_desktop(number):
    def inner(item):
        global selected_desktop
        return selected_desktop == number
    return inner

def select_desktop(number):
    def inner(icon, item):
        global selected_desktop
        selected_desktop = number
        record_and_show_window(number)
    return inner


def on_stop_sharing(icon, item):
    global stop_sharing, selected_desktop
    stop_sharing = True
    icon.notify(f"Sharing has been stopped")
    selected_desktop = 0

def quit(icon, item):
    global stop_sharing
    stop_sharing = True
    icon.stop()


if __name__ == '__main__':
    # Make the application DPI aware to handle display scaling properly
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

    selected_desktop = 0
    stop_sharing = False

    # Create a menu with all available virtual desktops
    desktop_items = [item(f"Desktop {desktop.number}", select_desktop(desktop.number), checked=get_selected_desktop(desktop.number), radio=True) for desktop in get_virtual_desktops()]
    desktops_menu = menu(*desktop_items)

    items_menu = menu(
        item('Start Sharing', desktops_menu),
        item('Stop Sharing', on_stop_sharing),
        item('Quit', quit)
    )

    # Load the application icon
    icon_image = Image.open("icon.ico")
    icon('DeskShare', icon_image, menu=items_menu).run()
