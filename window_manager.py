import glfw
import sys

class WindowManager:
    def __init__(self, width=800, height=600, title="Stimulus", fullscreen=False, xpos=None, ypos=None,
                 floating=False, mouse_passthrough=False, visible_regions=None):
        self.width = width
        self.height = height
        self.title = title
        self.fullscreen = fullscreen
        self.xpos = xpos
        self.ypos = ypos
        # 置顶：刺激窗需要始终盖在 Webots 窗口之上时开启
        self.floating = floating
        self.mouse_passthrough = mouse_passthrough
        self.visible_regions = visible_regions
        self.window = None

    def initialize(self):
        import ctypes
        try:
            # Match the camera client rectangle in physical screen pixels.
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
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
        if self.visible_regions is not None:
            glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
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

        if self.visible_regions is not None:
            self.set_visible_regions(self.visible_regions)

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
        if self.visible_regions is not None:
            glfw.show_window(self.window)
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

    def set_bounds(self, rect, visible_regions=None):
        resizing = (rect['width'], rect['height']) != (self.width, self.height)
        if resizing and visible_regions is not None:
            glfw.hide_window(self.window)
        glfw.set_window_pos(self.window, rect['x'], rect['y'])
        glfw.set_window_size(self.window, rect['width'], rect['height'])
        self.xpos, self.ypos = rect['x'], rect['y']
        self.width, self.height = rect['width'], rect['height']
        if visible_regions is not None:
            self.set_visible_regions(visible_regions)
        if resizing and visible_regions is not None:
            glfw.show_window(self.window)

    def set_visible_regions(self, rectangles):
        """Remove all non-target pixels from the native window, including the video.

        Some Windows OpenGL drivers report a transparent framebuffer but still
        display its background as black. A native window region leaves actual
        holes and preserves GLFW rendering/vsync and mouse passthrough.
        """
        if sys.platform != 'win32':
            raise RuntimeError('Camera target regions currently require Windows')
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        gdi.CreateRectRgn.argtypes = [ctypes.c_int] * 4
        gdi.CreateRectRgn.restype = wintypes.HRGN
        gdi.CombineRgn.argtypes = [wintypes.HRGN, wintypes.HRGN, wintypes.HRGN, ctypes.c_int]
        gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        user.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
        combined = gdi.CreateRectRgn(0, 0, 0, 0)
        if not combined:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            for rectangle in rectangles:
                part = gdi.CreateRectRgn(*rectangle)
                if not part:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if not gdi.CombineRgn(combined, combined, part, 2):  # RGN_OR
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    gdi.DeleteObject(part)
            if not user.SetWindowRgn(glfw.get_win32_window(self.window), combined, True):
                raise ctypes.WinError(ctypes.get_last_error())
            combined = None  # SetWindowRgn transfers ownership to Windows.
            self.visible_regions = rectangles
        finally:
            if combined:
                gdi.DeleteObject(combined)
