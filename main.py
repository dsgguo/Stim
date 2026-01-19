import glfw
from window_manager import WindowManager
from stimuli import Triangle, Square, Circle, create_shader_program, Stimulus
from trigger_manager import SerialTrigger
from experiment_manager import ExperimentManager
from OpenGL.GL import *
import time

import argparse
import json
import os

def main(width=800, height=600, xpos=None, ypos=None, serial_port=None, mode='free'):
    window_mgr = WindowManager(width=width, height=height, title="Stimulus Window", fullscreen=False, xpos=xpos, ypos=ypos)
    if not window_mgr.initialize():
        print("Failed to initialize window")
        return

    # Initialize Trigger
    trigger = None
    if serial_port:
        trigger = SerialTrigger(serial_port)

    # Initialize Shader
    shader_program = create_shader_program()
    if not shader_program:
        print("Failed to compile shaders")
        window_mgr.terminate()
        return

    # Create Stimuli
    stimuli = []
    if os.path.exists('layout.json'):
        print("加载布局文件 layout.json...")
        try:
            with open('layout.json', 'r') as f:
                data = json.load(f)
                for d in data:
                    s = Stimulus.from_dict(d)
                    if s: stimuli.append(s)
        except Exception as e:
            print(f"Failed to load layout: {e}")
    
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
        experiment_mgr = ExperimentManager(mode, stimuli, trigger)
        experiment_mgr.start()
    
    # Transparency settings
    is_bg_transparent = True
    glClearColor(0.0, 0.0, 0.0, 0.0)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # Frame-based timing setup
    refresh_rate = glfw.get_video_mode(glfw.get_primary_monitor()).refresh_rate
    if refresh_rate < 1: refresh_rate = 60.0 # Fallback
    frame_count = 0
    print(f"检测到刷新率: {refresh_rate} Hz")

    # Input state tracking (to avoid rapid toggling)
    last_f_state = glfw.RELEASE
    last_b_state = glfw.RELEASE
    last_tab_state = glfw.RELEASE
    last_s_state = glfw.RELEASE # For Ctrl+S
    last_g_state = glfw.RELEASE # For Background Toggle

    print("控制说明:")
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
    print("  M: 模拟结果反馈(Mode 1, Key 1-6)")
    print("  Right Mouse Drag: 移动窗口")
    print("  ESC: 退出")

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

    while not window_mgr.should_close():
        # Input Handling
        window = window_mgr.window
        if glfw.get_key(window, glfw.KEY_ESCAPE) == glfw.PRESS:
            glfw.set_window_should_close(window, True)

        # Cycle Stimulus
        tab_state = glfw.get_key(window, glfw.KEY_TAB)
        if tab_state == glfw.PRESS and last_tab_state == glfw.RELEASE:
            active_idx = (active_idx + 1) % len(stimuli)
            print(f"当前刺激块: {type(stimuli[active_idx]).__name__}")
        last_tab_state = tab_state

        active_stim = stimuli[active_idx]

        # Movement (Arrow Keys)
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

        # Timed Flicker (Test duration of 2.0s)
        if glfw.get_key(window, glfw.KEY_T) == glfw.PRESS:
             if glfw.get_key(window, glfw.KEY_LEFT_SHIFT) != glfw.PRESS and \
                glfw.get_key(window, glfw.KEY_RIGHT_SHIFT) != glfw.PRESS:
                 active_stim.set_flicker(freq=active_stim.flicker_freq, duration=2.0, current_frame=frame_count)
                 if trigger:
                     trigger.write_event(active_idx + 1)
                 print("闪烁已开始 (2.0秒)")

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

        # Sequenced Flicker (Shift + T)
        t_key = glfw.get_key(window, glfw.KEY_T)
        if t_key == glfw.PRESS:
             if glfw.get_key(window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or \
                glfw.get_key(window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS:
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

        # Save Layout (Ctrl + S)
        s_key = glfw.get_key(window, glfw.KEY_S)
        if s_key == glfw.PRESS and last_s_state == glfw.RELEASE:
             if glfw.get_key(window, glfw.KEY_LEFT_SUPER) == glfw.PRESS or \
                glfw.get_key(window, glfw.KEY_RIGHT_SUPER) == glfw.PRESS or \
                glfw.get_key(window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or \
                glfw.get_key(window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS:
                 
                 data = [s.to_dict() for s in stimuli]
                 with open('layout.json', 'w') as f:
                     json.dump(data, f, indent=4)
                 print("\n布局已保存到 layout.json")
        last_s_state = s_key


        # Update Experiment Manager
        if experiment_mgr:
            experiment_mgr.update(time.time(), frame_count)
            
            # Simulated Feedback for Online Discrete (Mode 1)
            # Keys 1-6 map to result_idx 0-5
            if experiment_mgr.mode == 'online_discrete':
                for i in range(6):
                    key_code = getattr(glfw, f"KEY_{i+1}")
                    if glfw.get_key(window, key_code) == glfw.PRESS:
                        # Simple debounce needed? Maybe for this test okay
                         experiment_mgr.trigger_feedback(i)

        # Render
        glClear(GL_COLOR_BUFFER_BIT)
        
        for i, s in enumerate(stimuli):
            # Pass active state to highlight the selected one
            is_active = (i == active_idx)
            s.draw(current_frame=frame_count, refresh_rate=refresh_rate, active=is_active)

        window_mgr.swap_buffers()
        window_mgr.poll_events()
        frame_count += 1

    window_mgr.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=800, help="Window width")
    parser.add_argument("--height", type=int, default=600, help="Window height")
    parser.add_argument("--x", type=int, default=None, help="Window X position")
    parser.add_argument("--y", type=int, default=None, help="Window Y position")
    parser.add_argument("--port", type=str, default=None, help="Serial port for trigger")
    parser.add_argument("--mode", type=str, default="free", choices=['free', 'offline', 'online_discrete', 'online_continuous'], help="Experiment Mode")
    args = parser.parse_args()
    main(width=args.width, height=args.height, xpos=args.x, ypos=args.y, serial_port=args.port, mode=args.mode)
