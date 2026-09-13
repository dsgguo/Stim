import numpy as np
from OpenGL.GL import *
import math
import time
import ctypes

# basic shaders
# 5x7 bitmap font for static direction captions drawn on the targets.
GLYPHS = {
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
}


VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec3 aPos;
uniform mat4 model;
void main() {
    gl_Position = model * vec4(aPos, 1.0);
}
"""

FRAGMENT_SHADER_SOURCE = """
#version 330 core
out vec4 FragColor;
uniform vec4 color;
void main() {
    FragColor = color;
}
"""

def create_shader_program():
    # Vertex Shader
    vertex_shader = glCreateShader(GL_VERTEX_SHADER)
    glShaderSource(vertex_shader, VERTEX_SHADER_SOURCE)
    glCompileShader(vertex_shader)
    if not glGetShaderiv(vertex_shader, GL_COMPILE_STATUS):
        print("Vertex Shader Error:", glGetShaderInfoLog(vertex_shader))

    # Fragment Shader
    fragment_shader = glCreateShader(GL_FRAGMENT_SHADER)
    glShaderSource(fragment_shader, FRAGMENT_SHADER_SOURCE)
    glCompileShader(fragment_shader)
    if not glGetShaderiv(fragment_shader, GL_COMPILE_STATUS):
        print("Fragment Shader Error:", glGetShaderInfoLog(fragment_shader))

    # Shader Program
    shader_program = glCreateProgram()
    glAttachShader(shader_program, vertex_shader)
    glAttachShader(shader_program, fragment_shader)
    glLinkProgram(shader_program)
    if not glGetProgramiv(shader_program, GL_LINK_STATUS):
        print("Shader Link Error:", glGetProgramInfoLog(shader_program))

    glDeleteShader(vertex_shader)
    glDeleteShader(fragment_shader)

    return shader_program

class Stimulus:
    def __init__(self, x=0.0, y=0.0, size=0.5, color=(1.0, 1.0, 1.0)):
        self.x = x
        self.y = y
        self.base_size = size
        self.current_size = size
        self.color = color 
        
        self.is_flickering = False
        self.flicker_freq = 1.0
        self.flicker_phase = 0.0
        self.flicker_start_frame = 0
        self.flicker_start_time = 0
        self.flicker_duration = None
        
        self.is_flashing_border = False
        self.border_flash_start_time = 0
        self.border_flash_duration = 0.2
        self.border_color = (1.0, 0.0, 0.0)
        
        self.vao = None
        self.vbo = None
        self.shader = None
        self.num_vertices = 0

        # Static direction caption (drawn on top of the flicker in a constant color)
        self.caption_text = None
        self.caption_color = (0.55, 0.0, 0.0, 1.0)
        self.caption_vao = None
        self.caption_vbo = None
        self.caption_vertices = 0

    def init_gl(self, shader_program):
        self.shader = shader_program
        self.setup_buffers()

    def setup_buffers(self):
        # Override in subclasses
        pass

    def set_flicker(self, freq, phase=0.0, duration=None, current_frame=0):
        self.flicker_freq = freq
        self.flicker_phase = phase
        self.flicker_duration = duration
        self.is_flickering = True
        self.flicker_start_frame = current_frame
        self.flicker_start_time = time.time() # Keep for duration check if needed, or use frames

    def stop_flicker(self):
        self.is_flickering = False

    def trigger_border_flash(self, color=(1.0, 0.0, 0.0)):
        self.is_flashing_border = True
        self.border_flash_start_time = time.time()
        self.border_color = color

    def set_caption(self, text, color=(0.55, 0.0, 0.0)):
        """Show a constant 5x7-bitmap text on the target; the VAO builds lazily on first draw."""
        self.caption_text = (text or '').upper() or None
        self.caption_color = (color[0], color[1], color[2], 1.0)
        self.caption_vao = None
        self.caption_vertices = 0

    def _build_caption_buffers(self, max_cell=0.035, max_width=0.92):
        text = self.caption_text or ''
        glyphs = [GLYPHS[ch] for ch in text if ch in GLYPHS]
        if not glyphs:
            return
        total_cells_w = len(glyphs) * 6 - 1
        cell = min(max_cell, max_width / total_cells_w)
        width = total_cells_w * cell
        left = -width / 2.0
        top = 3.5 * cell
        vertices = []
        for gi, rows in enumerate(glyphs):
            gx = left + gi * 6 * cell
            for ry, row in enumerate(rows):
                for cx, flag in enumerate(row):
                    if flag != '1':
                        continue
                    x0 = gx + cx * cell
                    y0 = top - ry * cell
                    x1 = x0 + cell
                    y1 = y0 - cell
                    vertices += [x0, y0, 0.0, x1, y0, 0.0, x1, y1, 0.0,
                                 x0, y0, 0.0, x1, y1, 0.0, x0, y1, 0.0]
        if not vertices:
            return
        data = np.array(vertices, dtype=np.float32)
        self.caption_vao = glGenVertexArrays(1)
        glBindVertexArray(self.caption_vao)
        self.caption_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.caption_vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * data.itemsize, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        self.caption_vertices = len(vertices) // 3

    def update_alpha(self, current_frame, refresh_rate):
        current_time = time.time()
        alpha = 1.0
        if self.is_flickering:
            # Use frames for phase to be refresh-synchronized
            frames_elapsed = current_frame - self.flicker_start_frame
            time_elapsed_frames = frames_elapsed / refresh_rate
            
            # Duration check (can use frames or time, frames is more consistent now)
            if self.flicker_duration and (current_time - self.flicker_start_time) > self.flicker_duration:
                self.is_flickering = False
            else:
                intensity = 0.5 * (1 + math.sin(2 * math.pi * self.flicker_freq * time_elapsed_frames + self.flicker_phase))
                alpha = intensity
        return alpha, current_time

    def get_model_matrix(self, scale_mult=1.0):
        # Construct 4x4 matrix manually or use library. Numpy is fine.
        # Identity
        mat = np.identity(4, dtype=np.float32)
        # Scale
        s = self.current_size * scale_mult
        viewport_scale = getattr(self, 'viewport_scale', None)
        mat[0, 0] = viewport_scale[0] * scale_mult if viewport_scale else s
        mat[1, 1] = viewport_scale[1] * scale_mult if viewport_scale else s
        mat[2, 2] = s
        # Translate
        mat[0, 3] = self.x
        mat[1, 3] = self.y
        # OpenGL expects column-major order, so transpose if we send as row-major by default? 
        # glUniformMatrix4fv with transpose=GL_TRUE for row-major numpy arrays.
        return mat

    def draw(self, current_frame=0, refresh_rate=60.0, active=False):
        if self.shader is None:
            return

        glUseProgram(self.shader)
        
        alpha, current_time = self.update_alpha(current_frame, refresh_rate)
        viewport_target = getattr(self, 'viewport_scale', None) is not None
        main_scale = 1.0
        
        # 1. Draw Selection Highlight (Active state)
        if active:
            # Draw a faint gray border/box around it
            model = self.get_model_matrix(scale_mult=1.1)
            model_loc = glGetUniformLocation(self.shader, "model")
            glUniformMatrix4fv(model_loc, 1, GL_TRUE, model)
            
            color_loc = glGetUniformLocation(self.shader, "color")
            # Dim white/gray highlight
            glUniform4f(color_loc, 0.5, 0.5, 0.5, 0.3)
            
            glBindVertexArray(self.vao)
            glDrawArrays(GL_TRIANGLE_FAN, 0, self.num_vertices)

        # 2. Draw Border Flash (Triggered by 'B' or serial)
        if self.is_flashing_border:
            if current_time - self.border_flash_start_time > self.border_flash_duration:
                self.is_flashing_border = False
            else:
                model = self.get_model_matrix(scale_mult=1.0 if viewport_target else 1.2)
                if viewport_target:
                    main_scale = 0.84  # Keep cue/feedback borders within the native target region.
                model_loc = glGetUniformLocation(self.shader, "model")
                glUniformMatrix4fv(model_loc, 1, GL_TRUE, model)
                
                color_loc = glGetUniformLocation(self.shader, "color")
                glUniform4f(color_loc, self.border_color[0], self.border_color[1], self.border_color[2], 1.0)
                
                glBindVertexArray(self.vao)
                glDrawArrays(GL_TRIANGLE_FAN, 0, self.num_vertices)

        # 3. Draw Main Shape
        model = self.get_model_matrix(scale_mult=main_scale)
        model_loc = glGetUniformLocation(self.shader, "model")
        glUniformMatrix4fv(model_loc, 1, GL_TRUE, model)
        
        color_loc = glGetUniformLocation(self.shader, "color")
        if viewport_target:
            # Modulate luminance, keeping each target opaque at its dark phase.
            # The native window region makes everything outside the targets transparent.
            glUniform4f(color_loc, self.color[0] * alpha, self.color[1] * alpha, self.color[2] * alpha, 1.0)
        else:
            glUniform4f(color_loc, self.color[0], self.color[1], self.color[2], alpha)
        
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_FAN, 0, self.num_vertices)
        glBindVertexArray(0)

        # 4. Static caption in a constant color, readable during both flicker phases
        if self.caption_text:
            if self.caption_vao is None:
                self._build_caption_buffers()
            if self.caption_vao is not None:
                glUniform4f(color_loc, *self.caption_color)
                glBindVertexArray(self.caption_vao)
                glDrawArrays(GL_TRIANGLES, 0, self.caption_vertices)
                glBindVertexArray(0)

    def to_dict(self):
        return {
            "type": self.__class__.__name__,
            "x": self.x,
            "y": self.y,
            "size": self.current_size,
            "color": self.color,
            "flicker_freq": self.flicker_freq,
            "flicker_phase": self.flicker_phase
        }



    @staticmethod
    def from_dict(data):
        class_name = data.get("type", "Square")

        # 白名单：layout.json 是外部输入，不允许它实例化任意类
        if class_name not in ("Square", "Triangle", "Circle"):
            return None
        cls = globals().get(class_name)
        if not cls:
            return None
        
        obj = cls(x=data["x"], y=data["y"], size=data["size"], color=tuple(data["color"]))
        obj.flicker_freq = data.get("flicker_freq", 1.0)
        obj.flicker_phase = data.get("flicker_phase", 0.0)
        return obj


class Triangle(Stimulus):
    def setup_buffers(self):
        vertices = np.array([
            0.0,  0.5, 0.0,
           -0.5, -0.5, 0.0,
            0.5, -0.5, 0.0
        ], dtype=np.float32)
        
        self.num_vertices = 3
        
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * vertices.itemsize, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

class Square(Stimulus):
    def setup_buffers(self):
        # Triangle Fan for square: Center (optional) or just 4 points. 
        # Order: Top-Right, Bottom-Right, Bottom-Left, Top-Left for Fan?
        # Let's use 4 corners. 
        # V0: -0.5, 0.5
        # V1: 0.5, 0.5
        # V2: 0.5, -0.5
        # V3: -0.5, -0.5
        
        vertices = np.array([
            0.5,  0.5, 0.0,  # Top Right
            0.5, -0.5, 0.0,  # Bottom Right
           -0.5, -0.5, 0.0,  # Bottom Left
           -0.5,  0.5, 0.0   # Top Left
        ], dtype=np.float32)
        
        self.num_vertices = 4
        
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        # Using Triangle Fan, this order works if correct? 
        # Standard: 0, 1, 2, 3 gives two triangles? 
        # GL_TRIANGLE_FAN: v0 is center. 
        # Let's use GL_TRIANGLE_FAN and simple order. 
        # Vertices: TR, BR, BL, TL. 
        # Fan from TR: TR -> BR -> BL (Tri 1), TR -> BL -> TL (Tri 2). 
        
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * vertices.itemsize, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

class Circle(Stimulus):
    def setup_buffers(self, segments=36):
        vertices = []
        # Center vertex for Fan
        vertices.extend([0.0, 0.0, 0.0])
        
        radius = 0.5
        angle_step = 2 * math.pi / segments
        
        for i in range(segments + 1):
            angle = i * angle_step
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            vertices.extend([x, y, 0.0])
            
        vertices = np.array(vertices, dtype=np.float32)
        self.num_vertices = len(vertices) // 3
        
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * vertices.itemsize, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
