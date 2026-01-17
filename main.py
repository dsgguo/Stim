import glfw
from window_manager import WindowManager
from stimuli import Triangle, Square, Circle, create_shader_program
from OpenGL.GL import *
import time

def main():
    window_mgr = WindowManager(title="Stimulus Window", fullscreen=True)
    if not window_mgr.initialize():
        print("Failed to initialize window")
        return

    # Initialize Shader
    shader_program = create_shader_program()
    if not shader_program:
        print("Failed to compile shaders")
        window_mgr.terminate()
        return

    # Create Stimuli
    tri = Triangle(x=-0.6, y=0.0, color=(0.0, 1.0, 0.0))
    sq = Square(x=0.0, y=0.0, color=(0.0, 0.0, 1.0))
    circ = Circle(x=0.6, y=0.0, color=(1.0, 0.0, 1.0))

    num_stimuli = 6
    stimuli = []
    for i in range(num_stimuli):
        x_pos = -0.8 + i * 0.4
        y_pos = -0.5 + i % 2 * 0.5
        color = 0.1 * i, 0.5, 1.0 - 0.1 * i
        s = Square(x=x_pos, y=y_pos, size=0.15, color=color)
        stimuli.append(s)
        
    active_idx = 1 # Square default

    for s in stimuli:
        s.init_gl(shader_program)

    # Transparency settings
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

    print("控制说明:")
    print("  TAB: 切换刺激块形状")
    print("  UP/DOWN (上下键): 调整大小")
    print("  F: 切换闪烁 (开/关)")
    print("  T: 定时闪烁 (2秒)")
    print("  LEFT/RIGHT (左右键): 调整闪烁频率")
    print("  B: 触发边框闪烁")
    print("  ESC: 退出")

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

        # Size Control
        if glfw.get_key(window, glfw.KEY_UP) == glfw.PRESS:
            active_stim.current_size = min(2.0, active_stim.current_size + 0.01)
        if glfw.get_key(window, glfw.KEY_DOWN) == glfw.PRESS:
            active_stim.current_size = max(0.1, active_stim.current_size - 0.01)

        # Flicker Control
        f_state = glfw.get_key(window, glfw.KEY_F)
        if f_state == glfw.PRESS and last_f_state == glfw.RELEASE:
            if active_stim.is_flickering:
                active_stim.stop_flicker()
                print("闪烁已停止")
            else:
                active_stim.set_flicker(freq=active_stim.flicker_freq, current_frame=frame_count)
                print("闪烁已开始 (持续)")
        last_f_state = f_state

        # Timed Flicker (Test duration of 2.0s)
        if glfw.get_key(window, glfw.KEY_T) == glfw.PRESS:
            active_stim.set_flicker(freq=active_stim.flicker_freq, duration=2.0, current_frame=frame_count)
            print("闪烁已开始 (2.0秒)")

        # Flicker Frequency
        if glfw.get_key(window, glfw.KEY_RIGHT) == glfw.PRESS:
            active_stim.flicker_freq += 0.1
            print(f"频率: {active_stim.flicker_freq:.1f} Hz", end='\r')
        if glfw.get_key(window, glfw.KEY_LEFT) == glfw.PRESS:
             active_stim.flicker_freq = max(0.1, active_stim.flicker_freq - 0.1)
             print(f"频率: {active_stim.flicker_freq:.1f} Hz", end='\r')

        # Border Flash
        b_state = glfw.get_key(window, glfw.KEY_B)
        if b_state == glfw.PRESS and last_b_state == glfw.RELEASE:
            active_stim.trigger_border_flash()
            print("边框闪烁 (指令已接收)")
        last_b_state = b_state

        # Render
        glClear(GL_COLOR_BUFFER_BIT)
        
        for s in stimuli:
            s.draw(current_frame=frame_count, refresh_rate=refresh_rate)

        window_mgr.swap_buffers()
        window_mgr.poll_events()
        frame_count += 1

    window_mgr.terminate()

if __name__ == "__main__":
    main()
