import glfw
from window_manager import WindowManager
from stimuli import Triangle, Square, Circle, create_shader_program, Stimulus
from trigger_manager import SerialTrigger
from experiment_manager import ExperimentManager
from feedback_receiver import FeedbackReceiver
from OpenGL.GL import *
import time

import argparse
import json
import os
from startup_menu import select_mode

# Stimulus Sequence Constants
SEQ_ON_DURATION = 2.0
SEQ_OFF_DURATION = 1.0
SEQ_TOTAL_ROUNDS = 3

# layout.json 锚定到脚本目录，避免受运行时工作目录影响
LAYOUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'layout.json')


def save_layout(window, stimuli):
    wx, wy = glfw.get_window_pos(window)
    ww, wh = glfw.get_window_size(window)
    data = {
        "window": {"x": wx, "y": wy, "width": ww, "height": wh},
        "stimuli": [s.to_dict() for s in stimuli],
    }
    with open(LAYOUT_PATH, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"布局已保存到 {LAYOUT_PATH}")


def load_layout(width=800, height=600, xpos=None, ypos=None):
    """返回 (width, height, xpos, ypos, stimuli)，以入参为缺省值。文件缺失/损坏时回退默认布局。"""
    stimuli = []
    if os.path.exists(LAYOUT_PATH):
        print(f"加载布局文件 {LAYOUT_PATH}...")
        try:
            with open(LAYOUT_PATH, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict):
                win_cfg = data.get("window", {})
                width = win_cfg.get("width", width)
                height = win_cfg.get("height", height)
                xpos = win_cfg.get("x", xpos)
                ypos = win_cfg.get("y", ypos)
                for d in data.get("stimuli", []):
                    s = Stimulus.from_dict(d)
                    if s: stimuli.append(s)
            elif isinstance(data, list):
                for d in data:
                    s = Stimulus.from_dict(d)
                    if s: stimuli.append(s)
        except Exception as e:
            print(f"Failed to load layout: {e}")
    return width, height, xpos, ypos, stimuli


def get_refresh_rate_for_window(window, fallback=60.0):
    """取窗口中心所在显示器的刷新率，避免多屏时频率系统性偏移。"""
    try:
        wx, wy = glfw.get_window_pos(window)
        ww, wh = glfw.get_window_size(window)
        cx, cy = wx + ww // 2, wy + wh // 2
        for monitor in glfw.get_monitors():
            mx, my = glfw.get_monitor_pos(monitor)
            mode = glfw.get_video_mode(monitor)
            if mx <= cx < mx + mode.size.width and my <= cy < my + mode.size.height:
                return float(mode.refresh_rate) or fallback
        primary = glfw.get_primary_monitor()
        if primary is not None:
            return float(glfw.get_video_mode(primary).refresh_rate) or fallback
    except Exception:
        pass
    return fallback


def main(width=800, height=600, xpos=None, ypos=None, serial_port=None, mode='free',
         feedback_port=5006, topmost=True, auto_start=False, exit_on_complete=False,
         stop_file=None, mouse_passthrough=False):
    stop_file = os.path.abspath(stop_file) if stop_file else None
    if stop_file and os.path.isfile(stop_file):
        print("Stim start cancelled by manager.", flush=True)
        return
    # 先读取布局，以支持覆盖窗口的尺寸与位置
    width, height, xpos, ypos, stimuli = load_layout(width, height, xpos, ypos)

    window_mgr = WindowManager(width=width, height=height, title="Stimulus Window", fullscreen=False,
                               xpos=xpos, ypos=ypos, floating=topmost and mode != 'free',
                               mouse_passthrough=mouse_passthrough)
    trigger = None
    feedback_receiver = None
    try:
        if not window_mgr.initialize():
            raise RuntimeError("Stim window initialization failed; check the display and OpenGL support")

        # Initialize Trigger
        if serial_port:
            trigger = SerialTrigger(serial_port)

        # Initialize Shader
        shader_program = create_shader_program()
        if not shader_program:
            raise RuntimeError("Stim shader initialization failed; check OpenGL 3.3 support")

        if not stimuli:
            print("Using default layout.")
            # tri = Triangle(x=-0.6, y=0.0, color=(0.0, 1.0, 0.0))
            # sq = Square(x=0.0, y=0.0, color=(0.0, 0.0, 1.0))
            # circ = Circle(x=0.6, y=0.0, color=(1.0, 0.0, 1.0))

            num_stimuli = 6
            for i in range(num_stimuli):
                x_pos = -0.8 + i * 0.4
                y_pos = -0.5 + i % 2 * 0.5
                color = 0.1 * i, 0.5, 1.0 - 0.1 * i
                s = Square(x=x_pos, y=y_pos, size=0.3, color=color)
                stimuli.append(s)

        active_idx = 0 if stimuli else -1

        for s in stimuli:
            s.init_gl(shader_program)


        # Experiment Manager
        experiment_mgr = None
        if mode != 'free':
            if mode == 'online_continuous':
                try:
                    feedback_receiver = FeedbackReceiver(ip='0.0.0.0', port=feedback_port)
                    feedback_receiver.start()
                except OSError as e:
                    print(f"⚠️ 反馈端口 {feedback_port} 绑定失败（可能被上个实例占用），本次无闭环反馈: {e}")
                    feedback_receiver = None
            experiment_mgr = ExperimentManager(mode, stimuli, trigger, feedback_receiver)
            experiment_mgr.start()

        # Transparency settings
        is_bg_transparent = True
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glEnable(GL_BLEND)
        # RGB 走标准 alpha 混合，alpha 通道原值写回（否则 framebuffer alpha 变成 a^2，
        # 透明窗口按 premultiplied 合成时会给闪烁波形叠加 2f 谐波）
        glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA)

        # Frame-based timing setup
        refresh_rate = get_refresh_rate_for_window(window_mgr.window, fallback=60.0)
        if refresh_rate < 1: refresh_rate = 60.0 # Fallback
        frame_count = 0
        print(f"检测到刷新率: {refresh_rate} Hz")
        if auto_start and experiment_mgr is not None:
            experiment_mgr.resume()
            print("Stim experiment started by manager.", flush=True)

        # Input state tracking (to avoid rapid toggling)
        last_f_state = glfw.RELEASE
        last_b_state = glfw.RELEASE
        last_tab_state = glfw.RELEASE
        last_s_state = glfw.RELEASE # For Ctrl+S
        last_g_state = glfw.RELEASE # For Background Toggle
        last_t_state = glfw.RELEASE # For Timed/Sequenced Flicker (edge detection)

        print("控制说明:")
        if mode == 'free':
            print("  TAB: 切换刺激块形状")
            print("  ARROW KEYS: 移动刺激块")
            print("  Mouse Drag: 拖拽刺激块")
            print("  F: 切换闪烁 (开/关)")
            print("  Shift+F: 全局闪烁开关")
            print("  T: 定时闪烁 (2秒)")
            print("  Shift+T: 序列闪烁 (3轮, 每轮2秒, 间隔1秒)")
            print("  B: 触发边框闪烁")
            print("  G: 切换背景透明度")
            print("  Ctrl+S: 保存当前布局")
            print("  Right Mouse Drag: 移动窗口")
            print("  ESC: 自动保存并返回选择界面")
        else:
            print("  TAB: 切换刺激块形状 (高亮)")
            print("  F: 切换闪烁 (开/关)")
            print("  Shift+F: 全局闪烁开关")
            print("  G: 切换背景透明度")
            print("  SPACE: 开始/继续实验")
            print("  M / 数字键 1-6: 模拟分类结果反馈 (online_discrete)")
            print("  Right Mouse Drag: 移动窗口")
            print("  ESC: 返回选择界面")

        # Mouse State
        is_dragging = False
        drag_offset_x = 0.0
        drag_offset_y = 0.0
    
        # Window Drag State
        is_win_dragging = False
        win_drag_start_x = 0
        win_drag_start_y = 0
    
        last_mouse_left = glfw.RELEASE
        last_mouse_right = glfw.RELEASE
    
        # Sequence State
        # Sequence State (Legacy - kept for 'free' mode or manual override)
        # The ExperimentManager handles this for specific modes
        is_sequencing = False

        print("EXPERIMENT_STIM_READY", flush=True)
        while not window_mgr.should_close():
            if stop_file and os.path.isfile(stop_file):
                print("Stim stop requested by manager.", flush=True)
                break
            # Input Handling
            window = window_mgr.window
            if glfw.get_key(window, glfw.KEY_ESCAPE) == glfw.PRESS:
                if mode == 'free':
                    save_layout(window, stimuli)
                glfw.set_window_should_close(window, True)

            # Cycle Stimulus
            tab_state = glfw.get_key(window, glfw.KEY_TAB)
            if tab_state == glfw.PRESS and last_tab_state == glfw.RELEASE:
                active_idx = (active_idx + 1) % len(stimuli)
                print(f"当前刺激块: {type(stimuli[active_idx]).__name__}")
            last_tab_state = tab_state

            active_stim = stimuli[active_idx]

            # Movement (Arrow Keys) — Design mode only
            if mode == 'free':
                move_speed = 0.01
                if glfw.get_key(window, glfw.KEY_UP) == glfw.PRESS:
                    active_stim.y += move_speed
                if glfw.get_key(window, glfw.KEY_DOWN) == glfw.PRESS:
                    active_stim.y -= move_speed
                if glfw.get_key(window, glfw.KEY_LEFT) == glfw.PRESS:
                    active_stim.x -= move_speed
                if glfw.get_key(window, glfw.KEY_RIGHT) == glfw.PRESS:
                    active_stim.x += move_speed

            # Mouse Interaction
            mouse_left = glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_LEFT)
            mx, my = glfw.get_cursor_pos(window)
            win_w, win_h = window_mgr.get_window_size()

            # Convert to NDC [-1, 1]
            # X: 0->w to -1->1 => (x/w)*2 - 1
            # Y: 0->h to 1->-1 => 1 - (y/h)*2  (OpenGL Y is up, Screen Y is down)
            ndc_x = (mx / win_w) * 2 - 1
            ndc_y = 1 - (my / win_h) * 2

            # Left-button click + drag to move stimuli — Design mode only
            if mode == 'free':
                if mouse_left == glfw.PRESS and last_mouse_left == glfw.RELEASE:
                    # Check click hit for ALL stimuli
                    clicked_idx = -1
                    for i, s in enumerate(stimuli):
                        half_size = s.current_size * 0.5
                        if (s.x - half_size <= ndc_x <= s.x + half_size) and \
                           (s.y - half_size <= ndc_y <= s.y + half_size):
                            clicked_idx = i
                            # Don't break immediately if we want z-order, but stimuli list order is drawing order (last on top)
                            # So we should prob pick the last one that matches.
                            # Let's just pick the first one found for simplicity or reverse iterate.

                    if clicked_idx != -1:
                        active_idx = clicked_idx
                        active_stim = stimuli[active_idx] # Update reference immediately
                        print(f"选中刺激块: {type(active_stim).__name__} (Index: {active_idx})")

                        is_dragging = True
                        drag_offset_x = active_stim.x - ndc_x
                        drag_offset_y = active_stim.y - ndc_y

                if mouse_left == glfw.RELEASE:
                    is_dragging = False

                if is_dragging:
                    active_stim.x = ndc_x + drag_offset_x
                    active_stim.y = ndc_y + drag_offset_y

                last_mouse_left = mouse_left

            # Window Movement (Right Mouse Drag)
            mouse_right = glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_RIGHT)
            if mouse_right == glfw.PRESS and last_mouse_right == glfw.RELEASE:
                 is_win_dragging = True
                 # Record initial click pos
                 win_drag_start_x, win_drag_start_y = glfw.get_cursor_pos(window)
        
            if mouse_right == glfw.RELEASE:
                 is_win_dragging = False
        
            if is_win_dragging:
                 cx, cy = glfw.get_cursor_pos(window)
                 wx, wy = glfw.get_window_pos(window)
                 # Delta = current_cursor - start_cursor
                 # We simply move the window by this delta.
                 # Note: Moving window moves the coordinate system, so cursor pos relative to window *might* stay same if we dont move mouse.
                 # Actually if we move window +dx, the window moves under cursor.
                 # If we just move window, the relative cursor pos changes? No.
                 # Ideally: new_win_pos = old_win_pos + (cx - win_drag_start_x)
                 glfw.set_window_pos(window, int(wx + cx - win_drag_start_x), int(wy + cy - win_drag_start_y))

            last_mouse_right = mouse_right

            # Flicker Control
            f_state = glfw.get_key(window, glfw.KEY_F)
            if f_state == glfw.PRESS and last_f_state == glfw.RELEASE:
                # Check modifier for Global Flicker
                if glfw.get_key(window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or \
                   glfw.get_key(window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS:
                    # Global Toggle
                    any_off = any(not s.is_flickering for s in stimuli)
                    if any_off:
                        for s in stimuli:
                            s.set_flicker(freq=s.flicker_freq, current_frame=frame_count)
                        if trigger:
                            trigger.write_event(100) # Global Start Tag
                    else:
                        for s in stimuli:
                            s.stop_flicker()
                    print(f"全局闪烁: {'开启' if any_off else '停止'}")
                else:
                    # Single Toggle for Active
                    if active_stim.is_flickering:
                        active_stim.stop_flicker()
                        print("闪烁已停止")
                    else:
                        active_stim.set_flicker(freq=active_stim.flicker_freq, current_frame=frame_count)
                        if trigger:
                            trigger.write_event(active_idx + 1)
                        print("闪烁已开始 (持续)")
            last_f_state = f_state

            # Timed Flicker (Test duration of 2.0s) & Sequenced Flicker — 按下沿触发一次
            t_state = glfw.get_key(window, glfw.KEY_T)
            t_pressed = (t_state == glfw.PRESS and last_t_state == glfw.RELEASE)
            shift_pressed = glfw.get_key(window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or \
                            glfw.get_key(window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
            if t_pressed:
                if not shift_pressed:
                    active_stim.set_flicker(freq=active_stim.flicker_freq, duration=2.0, current_frame=frame_count)
                    if trigger:
                        trigger.write_event(active_idx + 1)
                    print("闪烁已开始 (2.0秒)")
                else:
                    if not is_sequencing:
                        is_sequencing = True
                        seq_round = 0
                        seq_phase = 0 # ON
                        seq_start_time = time.time()
                        # Start All
                        for s in stimuli:
                            s.set_flicker(freq=s.flicker_freq, current_frame=frame_count)
                        if trigger:
                            # Event ID for global/sequence: 100
                            trigger.write_event(100)
                        print("序列闪烁开始: 第 1 轮 (ON)")
            last_t_state = t_state

            # Background Toggle (G Key)
            g_state = glfw.get_key(window, glfw.KEY_G)
            if g_state == glfw.PRESS and last_g_state == glfw.RELEASE:
                is_bg_transparent = not is_bg_transparent
                if is_bg_transparent:
                    glClearColor(0.0, 0.0, 0.0, 0.0)
                    print("背景: 透明")
                else:
                    glClearColor(0.0, 0.0, 0.0, 1.0)
                    print("背景: 黑色")
            last_g_state = g_state

            # Sequence Update Loop
            if is_sequencing:
                current_time = time.time()
                elapsed = current_time - seq_start_time

                if seq_phase == 0: # ON Phase
                    if elapsed > SEQ_ON_DURATION:
                        # Switch to OFF
                        for s in stimuli:
                            s.stop_flicker()
                        seq_phase = 1
                        seq_start_time = current_time
                        print(f"序列闪烁: 第 {seq_round + 1} 轮结束 (Pause)")
                elif seq_phase == 1: # OFF Phase
                    if elapsed > SEQ_OFF_DURATION:
                        seq_round += 1
                        if seq_round >= SEQ_TOTAL_ROUNDS:
                            is_sequencing = False
                            print("序列闪烁完成")
                        else:
                            # Start Next Round
                            for s in stimuli:
                                s.set_flicker(freq=s.flicker_freq, current_frame=frame_count)
                            if trigger:
                                trigger.write_event(100)
                            seq_phase = 0
                            seq_start_time = current_time
                            print(f"序列闪烁: 第 {seq_round + 1} 轮 (ON)")



            # Border Flash
            b_state = glfw.get_key(window, glfw.KEY_B)
            if b_state == glfw.PRESS and last_b_state == glfw.RELEASE:
                active_stim.trigger_border_flash()
                print("边框闪烁 (指令已接收)")
            last_b_state = b_state

            # Save Layout (Ctrl + S) — Design mode only
            if mode == 'free':
                s_key = glfw.get_key(window, glfw.KEY_S)
                if s_key == glfw.PRESS and last_s_state == glfw.RELEASE:
                     if glfw.get_key(window, glfw.KEY_LEFT_SUPER) == glfw.PRESS or \
                        glfw.get_key(window, glfw.KEY_RIGHT_SUPER) == glfw.PRESS or \
                        glfw.get_key(window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or \
                        glfw.get_key(window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS:

                         save_layout(window, stimuli)
                last_s_state = s_key


            # Update Experiment Manager
            if experiment_mgr:
                experiment_mgr.update(time.time(), frame_count)
                if (exit_on_complete and mode == 'offline'
                        and experiment_mgr.state == experiment_mgr.STATE_IDLE):
                    print("Offline stimulus session finished.", flush=True)
                    break
            
                # Simulated Feedback for Online Discrete (Mode 1)
                # Keys 1-6 map to result_idx 0-5
                if experiment_mgr.mode == 'online_discrete':
                    for i in range(6):
                        key_code = getattr(glfw, f"KEY_{i+1}")
                        if glfw.get_key(window, key_code) == glfw.PRESS:
                            # Simple debounce needed? Maybe for this test okay
                             experiment_mgr.trigger_feedback(i)
            
                # Resume/Start with Space
                if glfw.get_key(window, glfw.KEY_SPACE) == glfw.PRESS:
                    experiment_mgr.resume()

            # Update Viewport inside loop to accommodate resizing or OS forced canvas clamps
            fb_w, fb_h = glfw.get_framebuffer_size(window)
            glViewport(0, 0, fb_w, fb_h)

            # Render
            glClear(GL_COLOR_BUFFER_BIT)
        
            for i, s in enumerate(stimuli):
                # Pass active state to highlight the selected one
                is_active = (i == active_idx)
                s.draw(current_frame=frame_count, refresh_rate=refresh_rate, active=is_active)

            window_mgr.swap_buffers()
            window_mgr.poll_events()
            frame_count += 1

    finally:
        # Each resource is released even when another cleanup action raises.
        try:
            if feedback_receiver is not None:
                feedback_receiver.stop()
        finally:
            try:
                if trigger is not None:
                    trigger.close()
            finally:
                window_mgr.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=2200, help="Window width")
    parser.add_argument("--height", type=int, default=1200, help="Window height")
    parser.add_argument("--x", type=int, default=None, help="Window X position")
    parser.add_argument("--y", type=int, default=None, help="Window Y position")
    parser.add_argument("--port", type=str, default='COM9', help="Serial port for trigger (设为 none 可禁用串口)")
    parser.add_argument("--feedback-port", type=int, default=5006, help="UDP port for robot feedback (default 5006)")
    parser.add_argument("--no-topmost", action='store_true', help="实验模式下不置顶窗口")
    parser.add_argument("--mouse-passthrough", action='store_true', help="鼠标穿过刺激窗口，可操作后面的管理器（需要 GLFW 3.4+）")
    parser.add_argument("--auto-start", action='store_true', help="窗口就绪后自动开始实验，无需按空格")
    parser.add_argument("--exit-on-complete", action='store_true', help="离线刺激完成后自动退出")
    parser.add_argument("--stop-file", help="检测到此文件时停止并释放串口、UDP 和窗口资源")
    parser.add_argument("--mode", type=str, default=None, choices=['free', 'offline', 'online_discrete', 'online_continuous'], help="Experiment Mode")
    args = parser.parse_args()

    serial_port = None if args.port.strip().lower() in ('none', 'off', '') else args.port

    if args.mode is not None:
        # CLI explicitly specified mode: single run, no menu loop
        print(f"Starting in mode: {args.mode}")
        main(width=args.width, height=args.height, xpos=args.x, ypos=args.y,
             serial_port=serial_port, mode=args.mode,
             feedback_port=args.feedback_port, topmost=not args.no_topmost,
             auto_start=args.auto_start, exit_on_complete=args.exit_on_complete,
             stop_file=args.stop_file, mouse_passthrough=args.mouse_passthrough)
    else:
        # Menu loop: select_mode → main → select_mode → ...
        while True:
            if args.stop_file and os.path.isfile(args.stop_file):
                break
            selected_mode = select_mode()
            if selected_mode is None:
                # User cancelled the menu (ESC / window close) → exit program
                break
            print(f"Starting in mode: {selected_mode}")
            main(width=args.width, height=args.height, xpos=args.x, ypos=args.y,
                 serial_port=serial_port, mode=selected_mode,
                 feedback_port=args.feedback_port, topmost=not args.no_topmost,
                 auto_start=args.auto_start, exit_on_complete=args.exit_on_complete,
                 stop_file=args.stop_file, mouse_passthrough=args.mouse_passthrough)
