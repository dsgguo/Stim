import glfw
import sys

class WindowManager:
    def __init__(self, width=800, height=600, title="Stimulus", fullscreen=False, xpos=None, ypos=None,
                 floating=False, mouse_passthrough=False):
        self.width = width
        self.height = height
        self.title = title
        self.fullscreen = fullscreen
        self.xpos = xpos
        self.ypos = ypos
        # 置顶：刺激窗需要始终盖在 Webots 窗口之上时开启
        self.floating = floating
        self.mouse_passthrough = mouse_passthrough
        self.window = None

    def initialize(self):
        import ctypes
        try:
            # 开启高DPI感知，防止Windows因为缩放导致窗口变黑/透明度失效以及大小错位
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        if not glfw.init():
            return False

        # Set window hints for transparency and version
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        if sys.platform == 'darwin':
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True) # Required on Mac

        glfw.window_hint(glfw.DECORATED, glfw.FALSE)

        # Transparency hint
        glfw.window_hint(glfw.TRANSPARENT_FRAMEBUFFER, glfw.TRUE)
        glfw.window_hint(glfw.ALPHA_BITS, 8) # 确保有Alpha通道来支持透明
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)
        if self.floating and not self.fullscreen:
            glfw.window_hint(glfw.FLOATING, glfw.TRUE)  # always-on-top

        monitor = None
        if self.fullscreen:
            monitor = glfw.get_primary_monitor()
            vmode = glfw.get_video_mode(monitor)
            self.width = vmode.size.width
            self.height = vmode.size.height
            # In true fullscreen, decorated hint is usually ignored but good to keep
        
        self.window = glfw.create_window(self.width, self.height, self.title, monitor, None)
        if not self.window:
            glfw.terminate()
            return False

        if self.mouse_passthrough:
            attribute = getattr(glfw, 'MOUSE_PASSTHROUGH', None)
            if (attribute is None or not hasattr(glfw, 'set_window_attrib')
                    or not hasattr(glfw, 'get_window_attrib')
                    or glfw.get_version() < (3, 4, 0)):
                raise RuntimeError('Stim mouse passthrough requires GLFW 3.4 or later')
            # Only this undecorated Stim window is affected; keyboard handling is retained.
            glfw.set_window_attrib(self.window, attribute, glfw.TRUE)
            if glfw.get_window_attrib(self.window, attribute) != glfw.TRUE:
                raise RuntimeError('GLFW could not enable mouse passthrough for the Stim window')
            print('Stim mouse passthrough enabled.', flush=True)

        if self.xpos is not None and self.ypos is not None:
            glfw.set_window_pos(self.window, self.xpos, self.ypos)

        glfw.make_context_current(self.window)
        glfw.swap_interval(1) # Enable V-Sync
        return True

    def should_close(self):
        return glfw.window_should_close(self.window)

    def swap_buffers(self):
        glfw.swap_buffers(self.window)

    def poll_events(self):
        glfw.poll_events()

    def terminate(self):
        glfw.terminate()

    def get_window_size(self):
        return glfw.get_window_size(self.window)
