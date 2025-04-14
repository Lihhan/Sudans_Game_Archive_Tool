from datetime import datetime, timedelta, timezone
from PIL import Image
import os
import json
import time
import re
import win32gui
import win32ui
import win32con
import sys
import ctypes
from ctypes import wintypes

DEFAULT_PATH = os.path.join(os.environ["USERPROFILE"], "AppData", "LocalLow", "DoubleCross", "SultansGame", "SAVEDATA")
CONFIG_FILE = os.path.join(DEFAULT_PATH, "config.json")
SETTING_FILE = os.path.join(DEFAULT_PATH, "setting.json")
CURRENT_SAVE_PATH = DEFAULT_PATH
MORE_SAVE_PATH = os.path.join(DEFAULT_PATH, "save-manager")
CURRENT_ID = ''
GAME_WINDOW_NAME = "Sultan's Game"

if getattr(sys, 'frozen', False):
    current_dir = sys._MEIPASS
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))


def is_failure_save(folder_path):
    files = os.listdir(folder_path)

    has_auto_save = "auto_save.json" in files
    has_round_end = any(re.match(r"round_\d+_end\.json", f) for f in files)

    return not has_auto_save and not has_round_end


def get_folder_info(folder_path):
    folder_name = os.path.basename(folder_path)
    item = {
        "name": folder_name,
        "description": "无描述。",
        "timestamp": int(os.path.getmtime(folder_path)),
        "path": os.path.abspath(folder_path),
        "failure": False,
        "ingame": None
    }

    # 查找最大 round 文件
    round_files = [
        f for f in os.listdir(folder_path)
        if re.match(r"round_(\d+)_end\.json", f)
    ]
    turns = [
        int(re.search(r"round_(\d+)_end\.json", f).group(1))
        for f in round_files
    ]
    item["turn"] = max(turns) + 1 if turns else 1

    # 读取 global.json
    global_path = os.path.join(folder_path, "global.json")
    if os.path.exists(global_path):
        try:
            with open(global_path, 'r', encoding='utf-8') as f:
                global_data = json.load(f)
            if isinstance(global_data, dict) and "inGame" in global_data:
                item["ingame"] = bool(global_data["inGame"])
        except Exception as e:
            print(f"读取 {global_path} 失败：{e}")
            item["failure"] = True
    else:
        item["failure"] = True

    if is_failure_save(folder_path):
        item["failure"] = True

    # 图片路径
    preview_path = os.path.join(folder_path, "preview.jpg")
    item["image"] = preview_path if os.path.exists(preview_path) else ""

    return item


def load_or_create_config():
    global CURRENT_SAVE_PATH, CURRENT_ID
    if not os.path.exists(MORE_SAVE_PATH):
        os.makedirs(MORE_SAVE_PATH)
    if not os.path.exists(os.path.join(DEFAULT_PATH, 'ScreenShot')):
        os.makedirs(os.path.join(DEFAULT_PATH, 'ScreenShot'))

    if os.path.exists(SETTING_FILE):
        with open(SETTING_FILE, "r", encoding="utf-8") as f:
            setting = json.load(f)
        CURRENT_SAVE_PATH = setting['SAVE_PATH']
        CURRENT_ID = setting['ID']
    else:
        CURRENT_ID = find_latest_numeric_folder(DEFAULT_PATH)
        setting = {'SAVE_PATH': f'{DEFAULT_PATH}',
                   'ID': f'{CURRENT_ID}'}
        with open(SETTING_FILE, "w", encoding="utf-8") as f:
            json.dump(setting, f, ensure_ascii=False, indent=2)

    existing_items = []

    # 读取旧的 config.json（如果存在）
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            existing_items = json.load(f)

    # 生成 folder_name -> item 映射（旧）
    old_items_map = {
        os.path.basename(item["path"]): item
        for item in existing_items
        if os.path.exists(item["path"])
    }

    # 扫描当前文件夹（新）
    updated_items = []

    for folder_name in os.listdir(MORE_SAVE_PATH):
        folder_path = os.path.join(MORE_SAVE_PATH, folder_name)
        if not os.path.isdir(folder_path):
            continue

        # 如果已有记录并且目录仍存在，保留并更新必要字段
        if folder_name in old_items_map:
            item = old_items_map[folder_name]
            item["timestamp"] = int(os.path.getmtime(folder_path))
            item["path"] = os.path.abspath(folder_path)
            item["failure"] = False
            item["ingame"] = None
            # 查找最大 round 文件
            round_files = [
                f for f in os.listdir(folder_path)
                if re.match(r"round_(\d+)_end\.json", f)
            ]
            turns = [
                int(re.search(r"round_(\d+)_end\.json", f).group(1))
                for f in round_files
            ]
            item["turn"] = max(turns) + 1 if turns else 1
            # 读取 global.json
            global_path = os.path.join(folder_path, "global.json")
            if os.path.exists(global_path):
                try:
                    with open(global_path, 'r', encoding='utf-8') as f:
                        global_data = json.load(f)
                    if isinstance(global_data, dict) and "inGame" in global_data:
                        item["ingame"] = bool(global_data["inGame"])
                except Exception as e:
                    print(f"读取 {global_path} 失败：{e}")
                    item["failure"] = True
            else:
                item["failure"] = True
            if is_failure_save(folder_path):
                item["failure"] = True
        else:
            item = get_folder_info(folder_path)

        updated_items.append(item)

    # 保存为 config.json
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_items, f, ensure_ascii=False, indent=2)

    cleanup_unused_images()

    return updated_items


def find_latest_numeric_folder(path):
    if not os.path.exists(DEFAULT_PATH):
        return ""

    numeric_folders = []

    for name in os.listdir(path):
        full_path = os.path.join(path, name)
        if os.path.isdir(full_path) and re.fullmatch(r"\d+", name):
            mtime = os.path.getmtime(full_path)
            numeric_folders.append((name, mtime))

    if not numeric_folders:
        return ""  # 没有符合条件的文件夹

    # 根据修改时间排序，取最新的
    latest_folder = max(numeric_folders, key=lambda x: x[1])[0]
    return latest_folder


def format_timestamp(ts):
    tz = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d  %H:%M:%S")


def new_folder_name():
    # 匹配 “存档数字” 的正则
    pattern = re.compile(r"^存档(\d+)$")
    max_n = 0
    # 遍历目录中的所有文件夹
    for name in os.listdir(MORE_SAVE_PATH):
        full_path = os.path.join(MORE_SAVE_PATH, name)
        if os.path.isdir(full_path):
            match = pattern.match(name)
            if match:
                n = int(match.group(1))
                if n > max_n:
                    max_n = n
    # 生成新的文件夹名
    return f"存档{max_n + 1}"


def get_window_scaling(hwnd):
    try:
        user32 = ctypes.windll.user32
        get_dpi_for_window = user32.GetDpiForWindow
        get_dpi_for_window.restype = ctypes.c_uint
        get_dpi_for_window.argtypes = [wintypes.HWND]
        dpi = get_dpi_for_window(hwnd)
        return dpi / 96.0
    except AttributeError:
        # 兼容旧系统
        dc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, dc)
        return dpi / 96.0


def screenshot_window(window_title_keyword):
    def enum_windows_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if window_title_keyword.lower() in title.lower():
                results.append((hwnd))

    # 获取匹配窗口句柄
    matches = []
    win32gui.EnumWindows(enum_windows_callback, matches)

    if not matches:
        print("未找到匹配窗口")
        return None

    hwnd = matches[0]
    print(f"捕获窗口：{win32gui.GetWindowText(hwnd)}")

    # 如果窗口最小化，先还原
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.5)

    # 激活窗口（必须要可见）
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.2)

    # 获取 DPI 缩放
    scale = get_window_scaling(hwnd)

    # 获取窗口客户区大小（排除边框和标题栏）
    client_rect = win32gui.GetClientRect(hwnd)
    width = int((client_rect[2] - client_rect[0]) * scale)
    height = int((client_rect[3] - client_rect[1]) * scale)

    # 获取客户区在屏幕上的位置（相对于桌面左上角）
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    left = int(left * scale)
    top = int(top * scale)

    # 获取桌面截图（可包含游戏画面）
    hdesktop = win32gui.GetDesktopWindow()
    desktop_dc = win32gui.GetWindowDC(hdesktop)
    img_dc = win32ui.CreateDCFromHandle(desktop_dc)
    mem_dc = img_dc.CreateCompatibleDC()

    screenshot = win32ui.CreateBitmap()
    screenshot.CreateCompatibleBitmap(img_dc, width, height)
    mem_dc.SelectObject(screenshot)

    # 将屏幕内容复制到内存 DC 中
    mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

    # 转为 PIL Image
    bmpinfo = screenshot.GetInfo()
    bmpstr = screenshot.GetBitmapBits(True)
    img = Image.frombuffer(
        'RGB',
        (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
        bmpstr, 'raw', 'BGRX', 0, 1
    )

    # 保存
    if not os.path.exists(os.path.join(DEFAULT_PATH, 'ScreenShot')):
        os.makedirs(os.path.join(DEFAULT_PATH, 'ScreenShot'))
    img_path = os.path.join(DEFAULT_PATH, 'ScreenShot',
                            f"{datetime.fromtimestamp(int(time.time())).strftime('%Y%m%d-%H%M%S')}.png")
    img.save(img_path)
    print(f"截图保存")

    # 清理
    win32gui.DeleteObject(screenshot.GetHandle())
    mem_dc.DeleteDC()
    img_dc.DeleteDC()
    win32gui.ReleaseDC(hdesktop, desktop_dc)

    return img_path


def cleanup_unused_images():
    # 读取 config.json 中所有引用的图片路径
    if not os.path.exists(CONFIG_FILE):
        print("config.json 不存在")
        return

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 收集所有正在使用的图片绝对路径
    used_images = set()
    for item in config:
        image_path = item.get("image")
        if image_path:
            abs_path = os.path.abspath(image_path)
            used_images.add(abs_path)

    # 遍历 ScreenShot 文件夹
    for filename in os.listdir(os.path.join(DEFAULT_PATH, 'ScreenShot')):
        file_path = os.path.abspath(os.path.join(DEFAULT_PATH, 'ScreenShot', filename))

        # 如果不是正在使用的图片，则删除
        if file_path not in used_images:
            try:
                os.remove(file_path)
                print(f"删除未使用的图片：{file_path}")
            except Exception as e:
                print(f"删除图片失败：{file_path}, 错误：{e}")