import numpy as np
from OpenGL.GL import *
import math
import time
import ctypes

# basic shaders
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
        mat[0, 0] = s
        mat[1, 1] = s
        mat[2, 2] = s
        # Translate
        mat[0, 3] = self.x
        mat[1, 3] = self.y
        # OpenGL expects column-major order, so transpose if we send as row-major by default? 
        # glUniformMatrix4fv with transpose=GL_TRUE for row-major numpy arrays.
        return mat

    def draw(self, current_frame=0, refresh_rate=60.0):
        if self.shader is None:
            return

        glUseProgram(self.shader)
        
        alpha, current_time = self.update_alpha(current_frame, refresh_rate)
        
        # 1. Draw Border if flashing
        if self.is_flashing_border:
            if current_time - self.border_flash_start_time > self.border_flash_duration:
                self.is_flashing_border = False
            else:
                # Draw slightly larger or wireframe
                model = self.get_model_matrix(scale_mult=1.2) # Make border larger
                model_loc = glGetUniformLocation(self.shader, "model")
                glUniformMatrix4fv(model_loc, 1, GL_TRUE, model)
                
                color_loc = glGetUniformLocation(self.shader, "color")
                glUniform4f(color_loc, self.border_color[0], self.border_color[1], self.border_color[2], 1.0)
                
                glBindVertexArray(self.vao)
                glDrawArrays(GL_TRIANGLE_FAN, 0, self.num_vertices)

        # 2. Draw Main Shape
        model = self.get_model_matrix()
        model_loc = glGetUniformLocation(self.shader, "model")
        glUniformMatrix4fv(model_loc, 1, GL_TRUE, model)
        
        color_loc = glGetUniformLocation(self.shader, "color")
        glUniform4f(color_loc, self.color[0], self.color[1], self.color[2], alpha)
        
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_FAN, 0, self.num_vertices)
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
        # Subclasses must be available in global scope or resolved via a map
        # Since they are in this file, we can try globals() but we need to ensure they are defined when called.
        # However, they are defined AFTER Stimulus class. 
        # So we better use a registry or just resolve them locally if possible, 
        # OR put this method outside as a helper, OR use a lazy lookup.
        # Let's use a helper dict map assuming they are defined later. 
        # Actually, methods are bound at runtime so specific subclasses will be available in globals by the time we call this.
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
        # Fan from TR: TR -> BR -> BL (Tri 1), TR -> BL -> TL (Tri 2). Yes.
        
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
