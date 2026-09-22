import tkinter as tk
import math
import sys

# ================= 全局配置 =================
WINDOW_ALPHA = 0.3
# AB距离限制
MIN_AB_M = 50
MAX_AB_M = 1500
STEP_M = 5
MIN_AB_KM = MIN_AB_M / 1000
MAX_AB_KM = MAX_AB_M / 1000
STEP_KM = STEP_M / 1000
DEFAULT_INIT_AB_M = 200
DEFAULT_INIT_AB_KM = DEFAULT_INIT_AB_M / 1000

# 炮弹弹道参数
V0 = 355    # 出膛速度 m/s
G = 9.8     # 重力加速度 m/s²
MAX_RANGE_M = V0 ** 2 / G

# 窗口全局变量
root_mask = None
canvas = None
text_tip = None

# 点位与状态
click_points = []
first_click_ignored = False  # 第一次点击忽略，从第二次开始记录点
mode_calibrate = False       # True=右键开局标定AB；False=左键开局复用旧比例尺
scale_km_per_px = None       # 当前窗口有效比例尺
ab_km = DEFAULT_INIT_AB_KM   # 当前AB基准长度(km)
# 全局永久记忆上次标定参数，跨遮罩不丢失
last_calib_ab_km = DEFAULT_INIT_AB_KM
last_calib_scale = None

# ================= 依赖检测 =================
def check_dep():
    try:
        import keyboard
    except ModuleNotFoundError:
        print("缺少库 keyboard，管理员CMD执行：pip install keyboard")
        input("回车退出程序...")
        sys.exit(1)
    global keyboard

# ================= 销毁窗口临时状态，保留全局标定记忆 =================
def close_mask():
    global root_mask, canvas, click_points, first_click_ignored, mode_calibrate, scale_km_per_px, ab_km
    if root_mask:
        root_mask.destroy()
        root_mask = None
    click_points.clear()
    first_click_ignored = False
    mode_calibrate = False
    scale_km_per_px = None
    ab_km = last_calib_ab_km

# ================= 醒目描边文字 =================
def draw_bold_text(x, y, text_str, font_size=22):
    font_cfg = ("SimHei", font_size, "bold")
    canvas.create_text(x-1, y, text=text_str, font=font_cfg, fill="#000000")
    canvas.create_text(x+1, y, text=text_str, font=font_cfg, fill="#000000")
    canvas.create_text(x, y-1, text=text_str, font=font_cfg, fill="#000000")
    canvas.create_text(x, y+1, text=text_str, font=font_cfg, fill="#000000")
    return canvas.create_text(x, y, text=text_str, font=font_cfg, fill="#ffffff")

# ================= 低抛弹道飞行时间计算 =================
def calc_low_trajectory_time(horiz_km):
    R = horiz_km * 1000.0
    if R > MAX_RANGE_M:
        return None
    ratio = (R * G) / (V0 ** 2)
    ratio = max(-1.0, min(1.0, ratio))
    two_theta = math.asin(ratio)
    theta = two_theta / 2.0
    flight_t = (2 * V0 * math.sin(theta)) / G
    return flight_t

# ================= 刷新CD距离与弹道结果 =================
def refresh_result_display(current_ab, current_scale):
    global text_tip
    if current_scale is None:
        canvas.itemconfig(text_tip, text="无有效比例尺！请右键重新标定AB")
        return
    if len(click_points) < 2:
        return
    # 区分两种模式点位下标
    if mode_calibrate:
        cx, cy = click_points[2]
        dx, dy = click_points[3]
    else:
        cx, cy = click_points[0]
        dx, dy = click_points[1]
    cd_px = math.hypot(dx - cx, dy - cy)
    cd_km = cd_px * current_scale
    flight_t = calc_low_trajectory_time(cd_km)
    max_range_km = MAX_RANGE_M / 1000

    if flight_t is None:
        info_line = f"警告：距离超过火炮最大射程({max_range_km:.2f}km)，无法命中"
    else:
        info_line = f"低抛弹道预估飞行时间：{flight_t:.2f} s"

    tip_text = (
        f"AB基准距离：{current_ab:.3f} km | CD实测距离：{cd_km:.3f} km\n"
        f"{info_line}\n任意点击关闭窗口"
    )
    canvas.itemconfig(text_tip, text=tip_text)

# ================= 滚轮仅标定模式可用 =================
def on_mouse_wheel(event):
    global ab_km, scale_km_per_px, text_tip, last_calib_ab_km, last_calib_scale
    if not mode_calibrate:
        canvas.itemconfig(text_tip, text="当前为复用比例尺模式，滚轮仅标定AB模式可调整")
        return
    if len(click_points) < 2:
        return
    ax, ay = click_points[0]
    bx, by = click_points[1]
    ab_px = math.hypot(bx - ax, by - ay)
    if ab_px < 0.1:
        canvas.itemconfig(text_tip, text="错误：A、B两点不能重合！")
        return

    if event.delta > 0:
        ab_km += STEP_KM
    else:
        ab_km -= STEP_KM
    ab_km = max(MIN_AB_KM, min(MAX_AB_KM, ab_km))
    scale_km_per_px = ab_km / ab_px
    # 更新全局记忆
    last_calib_ab_km = ab_km
    last_calib_scale = scale_km_per_px

    if len(click_points) >= 4:
        refresh_result_display(ab_km, scale_km_per_px)
    else:
        canvas.itemconfig(text_tip, text=f"AB基准：{ab_km:.3f} km，滚轮±5m调整，请继续点击标记C、D")

# ================= 鼠标点击主逻辑 =================
def on_mouse_click(event):
    global click_points, first_click_ignored, mode_calibrate, scale_km_per_px, ab_km, text_tip
    global last_calib_ab_km, last_calib_scale
    x, y = event.x, event.y
    btn = event.num  # 1左键 3右键

    # 第一次点击直接忽略，区分模式
    if not first_click_ignored:
        first_click_ignored = True
        if btn == 3:
            # 右键：标定AB模式，滚轮可调
            mode_calibrate = True
            canvas.itemconfig(text_tip, text="首次右键已忽略，下一次点击记录A点（标定AB模式，滚轮可调整）")
        else:
            # 左键：复用全局保存的比例尺，锁定滚轮
            mode_calibrate = False
            ab_km = last_calib_ab_km
            scale_km_per_px = last_calib_scale
            canvas.itemconfig(text_tip, text=f"首次左键已忽略，复用上次标定AB={ab_km:.3f}km，滚轮不可调整，下一次点击记录C点")
        return

    if mode_calibrate:
        # 标定模式点位顺序 [A,B,C,D]
        if len(click_points) == 0:
            click_points.append((x, y))
            canvas.create_oval(x-8, y-8, x+8, y+8, fill="#0f0", outline="white", width=2)
            draw_bold_text(x+15, y, "A", 24)
            canvas.itemconfig(text_tip, text="已标记A，下一次点击记录B点")
        elif len(click_points) == 1:
            click_points.append((x, y))
            canvas.create_oval(x-8, y-8, x+8, y+8, fill="#0f0", outline="white", width=2)
            draw_bold_text(x+15, y, "B", 24)
            ax, ay = click_points[0]
            canvas.create_line(ax, ay, x, y, fill="#0f0", dash=(5,2), width=3, tags="line_ab")
            ab_px = math.hypot(x - ax, y - ay)
            if ab_px > 0.1:
                scale_km_per_px = ab_km / ab_px
                last_calib_ab_km = ab_km
                last_calib_scale = scale_km_per_px
            canvas.itemconfig(text_tip, text=f"AB基准：{ab_km:.3f} km，滚轮±5m调整，继续点击标记C点")
        elif len(click_points) == 2:
            click_points.append((x, y))
            canvas.create_oval(x-8, y-8, x+8, y+8, fill="#f22", outline="white", width=2)
            draw_bold_text(x+15, y, "C", 24)
            canvas.itemconfig(text_tip, text="已标记C，下一次点击记录D点")
        elif len(click_points) == 3:
            click_points.append((x, y))
            canvas.create_oval(x-8, y-8, x+8, y+8, fill="#f22", outline="white", width=2)
            draw_bold_text(x+15, y, "D", 24)
            cx, cy = click_points[2]
            canvas.create_line(cx, cy, x, y, fill="#fd0", dash=(3,2), width=3, tags="line_cd")
            refresh_result_display(ab_km, scale_km_per_px)
        else:
            close_mask()
    else:
        # 左键复用模式：直接采集C、D两点
        if len(click_points) == 0:
            click_points.append((x, y))
            canvas.create_oval(x-8, y-8, x+8, y+8, fill="#fd0", outline="white", width=2)
            draw_bold_text(x+15, y, "C", 24)
            canvas.itemconfig(text_tip, text="已标记C，下一次点击记录D点（当前复用模式滚轮不可调）")
        elif len(click_points) == 1:
            click_points.append((x, y))
            canvas.create_oval(x-8, y-8, x+8, y+8, fill="#fd0", outline="white", width=2)
            draw_bold_text(x+15, y, "D", 24)
            cx, cy = click_points[0]
            canvas.create_line(cx, cy, x, y, fill="#fd0", dash=(3,2), width=3, tags="line_cd")
            refresh_result_display(ab_km, scale_km_per_px)
        else:
            close_mask()

# ================= 创建全屏拦截遮罩 =================
def create_block_mask():
    global root_mask, canvas, text_tip, ab_km
    close_mask()
    ab_km = last_calib_ab_km

    root_mask = tk.Tk()
    root_mask.attributes("-fullscreen", True)
    root_mask.attributes("-alpha", WINDOW_ALPHA)
    root_mask.attributes("-topmost", True)
    root_mask.attributes("-toolwindow", True)
    root_mask.overrideredirect(True)
    root_mask.configure(bg="black")

    canvas = tk.Canvas(root_mask, bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    screen_w = root_mask.winfo_screenwidth()
    text_tip = draw_bold_text(
        screen_w // 2, 75,
        "规则：第一次点击忽略；右键=标定AB(可滚轮)；左键=复用已保存比例尺直接测CD(滚轮锁定)",
        font_size=24
    )

    canvas.bind("<Button-1>", on_mouse_click)
    canvas.bind("<Button-3>", on_mouse_click)
    canvas.bind("<MouseWheel>", on_mouse_wheel)
    root_mask.bind("<Escape>", lambda e: close_mask())
    root_mask.mainloop()

# ================= F7全局热键循环 =================
def hotkey_loop():
    global last_calib_ab_km, last_calib_scale
    print("==== 测距工具修复版 ====")
    print(f"火炮初速355m/s，最大射程 {(V0**2/G)/1000:.2f} km")
    print("更新点：无记忆默认初始AB=200m；区分AB/CD点位下标修复计算相同问题")
    print("【操作规则】")
    print("1. f7进入页面，遮罩第一次点击直接忽略，第二次起记录点位")
    print("2. 首次右键：标定A/B，滚轮±5m可调(50m~1500m)，修改存入内存")
    print("3. 首次左键：复用内存上次标定比例尺，滚轮锁定，直接两点测CD")
    print("4. 标定/测量完成自动计算CD距离+低抛弹道飞行时间，超射程警告")
    print("================================\n")
    # 无记忆默认200m
    last_calib_ab_km = DEFAULT_INIT_AB_KM
    last_calib_scale = None
    while True:
        keyboard.wait("f7")
        create_block_mask()

if __name__ == "__main__":
    check_dep()
    import keyboard
    hotkey_loop()