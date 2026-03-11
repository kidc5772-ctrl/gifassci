"""
GIF to ASCII Art Converter
A modern GUI application for converting animated GIFs to ASCII art with playback controls.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
from pathlib import Path
import threading
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional
import colorsys
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import os

# Try to import GPU support
try:
    import numba
    from numba import jit, prange
    HAS_GPU = True
    GPU_TYPE = "Numba JIT"
    
    # Pre-compile Numba functions with aggressive optimization
    @jit(nopython=True, parallel=True, cache=True, fastmath=True)
    def calculate_brightness_numba(pixels):
        """Fast brightness calculation with Numba JIT - parallel"""
        height, width, _ = pixels.shape
        brightness = np.zeros((height, width), dtype=np.float32)
        for y in prange(height):
            for x in range(width):
                r = float(pixels[y, x, 0])
                g = float(pixels[y, x, 1])
                b = float(pixels[y, x, 2])
                brightness[y, x] = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        return brightness
except ImportError:
    HAS_GPU = False
    GPU_TYPE = "None"
    def calculate_brightness_numba(pixels):
        return (0.299 * pixels[:,:,0] + 0.587 * pixels[:,:,1] + 0.114 * pixels[:,:,2]) / 255.0


@dataclass
class ConversionConfig:
    """Configuration for ASCII conversion"""
    detail_level: int = 4  # pixels per character
    contrast: float = 1.0
    brightness: float = 0.0
    char_ramp: str = "detailed"
    use_color: bool = True


class CharacterRamps:
    """Different character ramps for ASCII art"""
    SIMPLE = " .:-=+*#%@"
    DETAILED = " `.-':_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31[]tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD*#$Bg0MNWQ%&@"
    BLOCKS = " ▁▂▃▄▅▆▇█"
    FULL = " ░▒▓█"
    
    EDGE_CHARS = {
        "horizontal": "─",
        "vertical": "│",
        "diagonal_right": "╱",
        "diagonal_left": "╲",
        "corner_tl": "┌",
        "corner_tr": "┐",
        "corner_bl": "└",
        "corner_br": "┘",
    }


class GIFLoader:
    """Handles GIF loading and frame extraction"""
    
    @staticmethod
    def load_gif(filepath: str) -> Tuple[List[Image.Image], int, Tuple[int, int]]:
        """Load GIF and extract frames"""
        gif = Image.open(filepath)
        frames = []
        durations = []
        
        try:
            while True:
                frame = gif.convert("RGB")
                frames.append(frame)
                durations.append(gif.info.get("duration", 100))
                gif.seek(len(frames))
        except EOFError:
            pass
        
        fps = 1000 / np.mean(durations) if durations else 10
        return frames, int(fps), gif.size


class MP4Loader:
    """Handles MP4 loading and frame extraction with multi-threading"""
    
    @staticmethod
    def extract_audio(filepath: str, output_path: str) -> bool:
        """Extract audio from MP4 and save as temporary audio file"""
        try:
            import subprocess
            # Use ffmpeg to extract audio - try multiple approaches
            # First try: extract as AAC
            result = subprocess.run(
                ["ffmpeg", "-i", filepath, "-vn", "-acodec", "aac", "-y", output_path],
                capture_output=True,
                timeout=60
            )
            
            if result.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                return True
            
            # Second try: extract as MP3 if AAC fails
            mp3_path = output_path.replace(".aac", ".mp3")
            result = subprocess.run(
                ["ffmpeg", "-i", filepath, "-vn", "-acodec", "libmp3lame", "-y", mp3_path],
                capture_output=True,
                timeout=60
            )
            
            if result.returncode == 0 and Path(mp3_path).exists() and Path(mp3_path).stat().st_size > 0:
                # Rename to original path
                import shutil
                shutil.move(mp3_path, output_path)
                return True
            
            return False
        except Exception as e:
            print(f"Audio extraction failed: {e}")
            return False
    
    @staticmethod
    def load_mp4(filepath: str, max_frames: Optional[int] = None, progress_callback=None) -> Tuple[List[Image.Image], int, Tuple[int, int]]:
        """Load MP4 and extract frames with progress tracking"""
        import cv2
        
        cap = cv2.VideoCapture(filepath)
        
        if not cap.isOpened():
            raise ValueError("Failed to open MP4 file")
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Limit frames if specified
        if max_frames:
            frame_count = min(frame_count, max_frames)
        
        frames = []
        frame_idx = 0
        
        while frame_idx < frame_count:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            frames.append(pil_image)
            frame_idx += 1
            
            if progress_callback:
                progress_callback(frame_idx, frame_count)
        
        cap.release()
        
        if not frames:
            raise ValueError("No frames extracted from MP4")
        
        return frames, fps, (width, height)


class EdgeDetector:
    """Detects edges in images for better ASCII representation"""
    
    @staticmethod
    def detect_edges(image: Image.Image, threshold: int = 50) -> np.ndarray:
        """Detect edges using Sobel operator"""
        gray = image.convert("L")
        edges_x = ImageFilter.Kernel((3, 3), [-1, 0, 1, -2, 0, 2, -1, 0, 1])
        edges_y = ImageFilter.Kernel((3, 3), [-1, -2, -1, 0, 0, 0, 1, 2, 1])
        
        edge_x = gray.filter(edges_x)
        edge_y = gray.filter(edges_y)
        
        edges = np.sqrt(np.array(edge_x, dtype=float)**2 + np.array(edge_y, dtype=float)**2)
        return (edges > threshold).astype(np.uint8)


class ASCIIConverter:
    """Converts images to ASCII art with multi-threading support"""
    
    def __init__(self, config: ConversionConfig):
        self.config = config
        self.char_ramp = self._get_char_ramp()
        self.num_threads = min(multiprocessing.cpu_count() * 2, 16)  # Use more threads for better parallelism
    
    def _get_char_ramp(self) -> str:
        """Get character ramp based on config"""
        ramps = {
            "simple": CharacterRamps.SIMPLE,
            "detailed": CharacterRamps.DETAILED,
            "blocks": CharacterRamps.BLOCKS,
            "full": CharacterRamps.FULL,
        }
        return ramps.get(self.config.char_ramp, CharacterRamps.DETAILED)
    
    def _adjust_image(self, image: Image.Image) -> Image.Image:
        """Apply brightness and contrast adjustments"""
        from PIL import ImageEnhance
        
        img = image.copy()
        
        if self.config.contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(self.config.contrast)
        
        if self.config.brightness != 0.0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.0 + self.config.brightness)
        
        return img
    
    def _get_pixel_brightness(self, pixel: Tuple[int, int, int]) -> float:
        """Convert RGB to brightness (0-1)"""
        r, g, b = pixel
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    
    def _get_pixel_color(self, pixel: Tuple[int, int, int]) -> str:
        """Convert RGB to ANSI color code"""
        r, g, b = pixel
        r_idx = round(r / 255 * 5)
        g_idx = round(g / 255 * 5)
        b_idx = round(b / 255 * 5)
        color_code = 16 + 36 * r_idx + 6 * g_idx + b_idx
        return f"\033[38;5;{color_code}m"
    
    def _get_html_color(self, pixel: Tuple[int, int, int]) -> str:
        """Convert RGB to hex color"""
        r, g, b = pixel
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def convert_frame(self, image: Image.Image) -> Tuple[List[str], List[List[Tuple[int, int, int]]]]:
        """Convert a single frame to ASCII art - optimized with Numba"""
        img = self._adjust_image(image)
        width, height = img.size
        
        # Resize based on detail level
        new_width = max(1, width // self.config.detail_level)
        new_height = max(1, height // (self.config.detail_level * 2))
        
        # Use faster BILINEAR resampling instead of LANCZOS
        img_resized = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
        pixels = np.ascontiguousarray(img_resized, dtype=np.uint8)
        
        # Fast brightness calculation with Numba JIT
        brightness = calculate_brightness_numba(pixels)
        
        # Map brightness to characters - vectorized
        char_indices = np.minimum((brightness * (len(self.char_ramp) - 1)).astype(np.int32), len(self.char_ramp) - 1)
        
        # Build ASCII art more efficiently
        ascii_art = []
        colors = []
        
        for y in range(new_height):
            # Use list comprehension for speed
            row = [self.char_ramp[char_indices[y, x]] for x in range(new_width)]
            row_colors = [tuple(pixels[y, x]) for x in range(new_width)]
            
            ascii_art.append("".join(row))
            colors.append(row_colors)
        
        return ascii_art, colors
    
    def convert_gif(self, frames: List[Image.Image], progress_callback=None) -> List[Tuple[List[str], List[List[Tuple[int, int, int]]]]]:
        """Convert all frames of a GIF using multi-threading"""
        results = [None] * len(frames)
        lock = threading.Lock()
        completed_count = [0]
        
        def convert_frame_worker(idx, frame):
            try:
                result = self.convert_frame(frame)
                with lock:
                    results[idx] = result
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback(completed_count[0], len(frames))
            except Exception as e:
                print(f"Error converting frame {idx}: {e}")
                with lock:
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback(completed_count[0], len(frames))
        
        # Create and start threads
        threads = []
        for i, frame in enumerate(frames):
            thread = threading.Thread(target=convert_frame_worker, args=(i, frame), daemon=True)
            threads.append(thread)
            thread.start()
            
            # Limit concurrent threads to avoid memory issues
            if len(threads) >= self.num_threads:
                threads[0].join()
                threads.pop(0)
        
        # Wait for all remaining threads
        for thread in threads:
            thread.join()
        
        return results


class ASCIIExporter:
    """Exports ASCII art to files"""
    
    @staticmethod
    def export_gif(ascii_frames: List[Tuple[List[str], List[List[Tuple[int, int, int]]]]], 
                   fps: int, filepath: str, font_size: int = 10, progress_callback=None):
        """Export as animated GIF with detailed progress stages"""
        from PIL import ImageDraw, ImageFont
        
        if not ascii_frames:
            return
        
        first_frame, _ = ascii_frames[0]
        char_width = 8
        char_height = 14
        
        width = len(first_frame[0]) * char_width
        height = len(first_frame) * char_height
        
        # Stage 1: Loading font
        if progress_callback:
            progress_callback(-1, len(ascii_frames), "Loading font...")
        
        try:
            font = ImageFont.truetype("consola.ttf", 8)
        except:
            try:
                font = ImageFont.truetype("cour.ttf", 8)
            except:
                font = ImageFont.load_default()
        
        gif_frames = []
        durations = []
        
        # Stage 2: Rendering frames
        for frame_idx, (ascii_frame, colors) in enumerate(ascii_frames):
            img = Image.new("RGB", (width, height), color=(0, 0, 0))
            draw = ImageDraw.Draw(img, "RGBA")
            
            y_pos = 0
            for row_idx, line in enumerate(ascii_frame):
                x_pos = 0
                for col_idx, char in enumerate(line):
                    if char != ' ':
                        color = colors[row_idx][col_idx] if row_idx < len(colors) and col_idx < len(colors[row_idx]) else (255, 255, 255)
                        draw.text((x_pos, y_pos), char, fill=color, font=font)
                    x_pos += char_width
                y_pos += char_height
            
            gif_frames.append(img)
            durations.append(int(1000 / fps))
            
            if progress_callback:
                progress_callback(frame_idx + 1, len(ascii_frames), f"Rendering frames: {frame_idx + 1}/{len(ascii_frames)}")
        
        # Stage 3: Encoding GIF
        if progress_callback:
            progress_callback(len(ascii_frames), len(ascii_frames), "Encoding GIF (this may take a moment)...")
        
        gif_frames[0].save(
            filepath,
            save_all=True,
            append_images=gif_frames[1:],
            duration=durations,
            loop=0,
            optimize=False
        )
        
        # Stage 4: Complete
        if progress_callback:
            progress_callback(len(ascii_frames), len(ascii_frames), "GIF export complete!")
    
    @staticmethod
    def export_text(ascii_frames: List[List[str]], filepath: str):
        """Export as plain text - fast"""
        with open(filepath, "w", encoding="utf-8") as f:
            for frame_idx, frame in enumerate(ascii_frames):
                f.write("\n".join(frame))
                f.write("\n\n")
    
    @staticmethod
    def export_text_fast(ascii_frames: List[Tuple[List[str], List[List[Tuple[int, int, int]]]]], filepath: str):
        """Export as ANSI colored text - fastest option"""
        with open(filepath, "w", encoding="utf-8") as f:
            for frame_idx, (ascii_frame, colors) in enumerate(ascii_frames):
                for row_idx, line in enumerate(ascii_frame):
                    for col_idx, char in enumerate(line):
                        color = colors[row_idx][col_idx] if row_idx < len(colors) and col_idx < len(colors[row_idx]) else (255, 255, 255)
                        r, g, b = color
                        # ANSI 256 color code
                        r_idx = round(r / 255 * 5)
                        g_idx = round(g / 255 * 5)
                        b_idx = round(b / 255 * 5)
                        color_code = 16 + 36 * r_idx + 6 * g_idx + b_idx
                        f.write(f"\033[38;5;{color_code}m{char}\033[0m")
                    f.write("\n")
                f.write("\n")
    
    @staticmethod
    def export_html(ascii_frames: List[Tuple[List[str], List[List[Tuple[int, int, int]]]]], 
                   fps: int, filepath: str):
        """Export as HTML with colors and animation"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ASCII Art Animation</title>
    <style>
        body { background: #1e1e1e; color: #fff; font-family: 'Courier New', monospace; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .controls { margin-bottom: 20px; }
        button { padding: 8px 16px; margin-right: 10px; background: #0e639c; color: white; border: none; cursor: pointer; }
        button:hover { background: #1177bb; }
        .ascii-display { 
            background: #000; 
            padding: 20px; 
            border-radius: 5px; 
            overflow-x: auto;
            line-height: 1.2;
            letter-spacing: 0.5px;
        }
        .frame { display: none; }
        .frame.active { display: block; }
        .info { margin-top: 10px; color: #888; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ASCII Art Animation</h1>
        <div class="controls">
            <button onclick="play()">Play</button>
            <button onclick="pause()">Pause</button>
            <button onclick="stop()">Stop</button>
            <label><input type="checkbox" id="loop" checked> Loop</label>
        </div>
        <div class="ascii-display" id="display"></div>
        <div class="info">
            <span id="frameInfo">Frame 1 / """ + str(len(ascii_frames)) + """</span>
        </div>
    </div>
    
    <script>
        const frames = """ + ASCIIExporter._generate_js_frames(ascii_frames) + """;
        const fps = """ + str(fps) + """;
        let currentFrame = 0;
        let isPlaying = false;
        let animationId = null;
        
        function renderFrame(frameIdx) {
            const display = document.getElementById('display');
            display.innerHTML = frames[frameIdx];
            document.getElementById('frameInfo').textContent = `Frame ${frameIdx + 1} / ${frames.length}`;
        }
        
        function play() {
            isPlaying = true;
            animate();
        }
        
        function pause() {
            isPlaying = false;
            if (animationId) cancelAnimationFrame(animationId);
        }
        
        function stop() {
            isPlaying = false;
            currentFrame = 0;
            if (animationId) cancelAnimationFrame(animationId);
            renderFrame(0);
        }
        
        function animate() {
            if (!isPlaying) return;
            renderFrame(currentFrame);
            currentFrame++;
            if (currentFrame >= frames.length) {
                if (document.getElementById('loop').checked) {
                    currentFrame = 0;
                } else {
                    isPlaying = false;
                    return;
                }
            }
            animationId = setTimeout(animate, 1000 / fps);
        }
        
        renderFrame(0);
    </script>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
    
    @staticmethod
    def _generate_js_frames(ascii_frames: List[Tuple[List[str], List[List[Tuple[int, int, int]]]]]) -> str:
        """Generate JavaScript array of frames with colors"""
        import json
        frames_js = []
        for ascii_frame, colors in ascii_frames:
            frame_html = "<pre>"
            for y, line in enumerate(ascii_frame):
                for x, char in enumerate(line):
                    color = colors[y][x] if y < len(colors) and x < len(colors[y]) else (255, 255, 255)
                    hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                    # Escape HTML special characters
                    char_escaped = char.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                    frame_html += f'<span style="color: {hex_color};">{char_escaped}</span>'
                frame_html += "\n"
            frame_html += "</pre>"
            # Use JSON to properly escape the string
            frames_js.append(json.dumps(frame_html))
        return "[" + ", ".join(frames_js) + "]"
    
    @staticmethod
    def export_mp4(ascii_frames: List[Tuple[List[str], List[List[Tuple[int, int, int]]]]], 
                   fps: int, filepath: str, audio_path: Optional[str] = None, font_size: int = 10, progress_callback=None):
        """Export as MP4 with optional audio"""
        import subprocess
        import tempfile
        from PIL import ImageDraw, ImageFont
        
        if not ascii_frames:
            return
        
        first_frame, _ = ascii_frames[0]
        char_width = 8
        char_height = 14
        
        width = len(first_frame[0]) * char_width
        height = len(first_frame) * char_height
        
        # Stage 1: Loading font
        if progress_callback:
            progress_callback(-1, len(ascii_frames), "Loading font...")
        
        try:
            font = ImageFont.truetype("consola.ttf", 8)
        except:
            try:
                font = ImageFont.truetype("cour.ttf", 8)
            except:
                font = ImageFont.load_default()
        
        # Create temporary video file without audio
        temp_video = None
        try:
            temp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
            
            # Stage 2: Rendering frames to video using ffmpeg for better compatibility
            import cv2
            
            # Use H.264 codec which is more widely supported
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))
            
            if not out.isOpened():
                # Fallback to MJPEG if H.264 fails
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))
            
            for frame_idx, (ascii_frame, colors) in enumerate(ascii_frames):
                img = Image.new("RGB", (width, height), color=(255, 255, 255))
                draw = ImageDraw.Draw(img, "RGBA")
                
                y_pos = 0
                for row_idx, line in enumerate(ascii_frame):
                    x_pos = 0
                    for col_idx, char in enumerate(line):
                        if char != ' ':
                            color = colors[row_idx][col_idx] if row_idx < len(colors) and col_idx < len(colors[row_idx]) else (255, 255, 255)
                            draw.text((x_pos, y_pos), char, fill=color, font=font)
                        x_pos += char_width
                    y_pos += char_height
                
                # Convert PIL to OpenCV format (BGR)
                frame_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                out.write(frame_cv)
                
                if progress_callback:
                    progress_callback(frame_idx + 1, len(ascii_frames), f"Rendering frames: {frame_idx + 1}/{len(ascii_frames)}")
            
            out.release()
            
            # Stage 3: Re-encode with ffmpeg for better compatibility and audio muxing
            if progress_callback:
                progress_callback(len(ascii_frames), len(ascii_frames), "Encoding video...")
            
            if audio_path and Path(audio_path).exists():
                # Use ffmpeg to re-encode and add audio from original MP4
                result = subprocess.run(
                    ["ffmpeg", "-i", temp_video, "-i", audio_path, "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", filepath],
                    capture_output=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    print(f"FFmpeg error: {result.stderr.decode()}")
                    # If ffmpeg fails, try without re-encoding
                    result = subprocess.run(
                        ["ffmpeg", "-i", temp_video, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", filepath],
                        capture_output=True,
                        timeout=300
                    )
                    
                    if result.returncode != 0:
                        print(f"FFmpeg fallback error: {result.stderr.decode()}")
                        # Last resort: copy without audio
                        import shutil
                        shutil.copy(temp_video, filepath)
            else:
                # No audio, just re-encode for compatibility
                result = subprocess.run(
                    ["ffmpeg", "-i", temp_video, "-c:v", "libx264", "-preset", "fast", "-y", filepath],
                    capture_output=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    # If re-encoding fails, just copy
                    import shutil
                    shutil.copy(temp_video, filepath)
            
            # Stage 4: Complete
            if progress_callback:
                progress_callback(len(ascii_frames), len(ascii_frames), "MP4 export complete!")
        
        finally:
            # Clean up temporary video file
            if temp_video and Path(temp_video).exists():
                try:
                    Path(temp_video).unlink()
                except:
                    pass


class GIFToASCIIApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.title("GIF/MP4 to ASCII Art Converter")
        self.geometry("1400x900")
        self.minsize(800, 600)  # Set minimum window size
        
        # State
        self.gif_frames: List[Image.Image] = []
        self.ascii_frames: List[Tuple[List[str], List[List[Tuple[int, int, int]]]]] = []
        self.current_frame_idx = 0
        self.is_playing = False
        self.is_converting = False
        self.fps = 10
        self.file_path = None
        self.audio_path = None  # Store extracted audio for MP4 export
        self.is_mp4 = False  # Track if current file is MP4
        self.slider_timer = None  # Debounce timer for sliders
        
        self._setup_ui()
        self._setup_styles()
    
    def _setup_styles(self):
        """Configure dark theme"""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
    
    def _setup_ui(self):
        """Build the UI"""
        # Main container
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top control panel
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(control_frame, text="Load GIF/MP4", command=self._load_gif).pack(side="left", padx=5)
        ctk.CTkButton(control_frame, text="Play", command=self._play).pack(side="left", padx=2)
        ctk.CTkButton(control_frame, text="Pause", command=self._pause).pack(side="left", padx=2)
        ctk.CTkButton(control_frame, text="Stop", command=self._stop).pack(side="left", padx=2)
        
        self.loop_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(control_frame, text="Loop", variable=self.loop_var).pack(side="left", padx=5)
        
        ctk.CTkButton(control_frame, text="Export", command=self._export).pack(side="right", padx=5)
        
        # Main content area
        content_frame = ctk.CTkFrame(main_frame)
        content_frame.pack(fill="both", expand=True)
        
        # Left panel - Preview
        left_frame = ctk.CTkFrame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(left_frame, text="ASCII Preview", font=("Arial", 14, "bold")).pack(pady=(0, 5))
        
        self.preview_text = ctk.CTkTextbox(left_frame, font=("Courier New", 10), wrap="none")
        self.preview_text.pack(fill="both", expand=True)
        self.preview_text.configure(state="disabled")
        
        # Status label
        self.status_label = ctk.CTkLabel(left_frame, text="Ready", text_color="#888", font=("Arial", 10))
        self.status_label.pack(pady=(10, 5))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(left_frame, variable=self.progress_var)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        
        # Right panel - Controls
        right_frame = ctk.CTkFrame(content_frame, width=250)
        right_frame.pack(side="right", fill="both", padx=(10, 0))
        right_frame.pack_propagate(False)
        
        # File info
        ctk.CTkLabel(right_frame, text="File Info", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        self.info_label = ctk.CTkLabel(right_frame, text="No file loaded", justify="left")
        self.info_label.pack(fill="x", pady=(0, 20))
        
        # GPU/CPU info
        gpu_status = f"GPU: {GPU_TYPE}"
        cpu_count = multiprocessing.cpu_count()
        ctk.CTkLabel(right_frame, text=f"CPU Threads: {cpu_count}\n{gpu_status}", 
                    font=("Arial", 9), text_color="#888888", justify="left").pack(fill="x", pady=(0, 20))
        
        # Sliders
        ctk.CTkLabel(right_frame, text="Detail Level", font=("Arial", 11, "bold")).pack(anchor="w")
        self.detail_var = tk.IntVar(value=4)
        ctk.CTkSlider(right_frame, from_=1, to=20, variable=self.detail_var, command=self._on_config_change).pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(right_frame, text="Contrast", font=("Arial", 11, "bold")).pack(anchor="w")
        self.contrast_var = tk.DoubleVar(value=1.0)
        ctk.CTkSlider(right_frame, from_=0.5, to=2.0, variable=self.contrast_var, command=self._on_config_change).pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(right_frame, text="Brightness", font=("Arial", 11, "bold")).pack(anchor="w")
        self.brightness_var = tk.DoubleVar(value=0.0)
        ctk.CTkSlider(right_frame, from_=-1.0, to=1.0, variable=self.brightness_var, command=self._on_config_change).pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(right_frame, text="Font Size", font=("Arial", 11, "bold")).pack(anchor="w")
        self.font_size_var = tk.IntVar(value=10)
        ctk.CTkSlider(right_frame, from_=6, to=16, variable=self.font_size_var, command=self._on_font_size_change).pack(fill="x", pady=(0, 20))
        
        # Character ramp selector
        ctk.CTkLabel(right_frame, text="Character Ramp", font=("Arial", 11, "bold")).pack(anchor="w")
        self.ramp_var = tk.StringVar(value="detailed")
        for ramp in ["simple", "detailed", "blocks", "full"]:
            ctk.CTkRadioButton(right_frame, text=ramp.capitalize(), variable=self.ramp_var, value=ramp, command=self._on_config_change).pack(anchor="w")
        
        ctk.CTkCheckBox(right_frame, text="Use Colors", variable=tk.BooleanVar(value=True)).pack(anchor="w", pady=(10, 0))
        
        # Bind resize event for auto-fit
        self.bind("<Configure>", self._on_window_resize)
    
    def _load_gif(self):
        """Load a GIF or MP4 file with detailed progress stages"""
        filepath = filedialog.askopenfilename(filetypes=[("Media files", "*.gif *.mp4"), ("GIF files", "*.gif"), ("MP4 files", "*.mp4"), ("All files", "*.*")])
        if not filepath:
            return
        
        self.status_label.configure(text="Stage 1/4: Loading file...", text_color="#FFA500")
        self.progress_var.set(0.1)
        self.update_idletasks()
        
        def load_in_thread():
            try:
                if filepath.lower().endswith('.mp4'):
                    self.status_label.configure(text="Stage 1/4: Extracting MP4 frames...", text_color="#FFA500")
                    self.progress_var.set(0.2)
                    self.update_idletasks()
                    self.gif_frames, self.fps, size = MP4Loader.load_mp4(filepath)
                    self.is_mp4 = True
                    self.audio_path = filepath  # Store original MP4 path for audio extraction during export
                else:
                    self.status_label.configure(text="Stage 1/4: Loading GIF frames...", text_color="#FFA500")
                    self.progress_var.set(0.2)
                    self.update_idletasks()
                    self.gif_frames, self.fps, size = GIFLoader.load_gif(filepath)
                    self.is_mp4 = False
                    self.audio_path = None
                
                self.file_path = filepath
                self.current_frame_idx = 0
                self.is_playing = False
                
                # Stage 2: Update info
                self.status_label.configure(text="Stage 2/4: Updating file info...", text_color="#FFA500")
                self.progress_var.set(0.3)
                self.update_idletasks()
                
                self.info_label.configure(text=f"File: {Path(filepath).name}\nFrames: {len(self.gif_frames)}\nFPS: {self.fps}\nSize: {size[0]}x{size[1]}")
                
                # Stage 3: Starting conversion
                self.status_label.configure(text="Stage 3/4: Starting conversion...", text_color="#FFA500")
                self.progress_var.set(0.4)
                self.update_idletasks()
                
                # Convert frames
                self._convert_frames()
                
            except Exception as e:
                self.status_label.configure(text=f"Error: {str(e)}", text_color="#FF0000")
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")
        
        thread = threading.Thread(target=load_in_thread, daemon=True)
        thread.start()
    
    def _convert_frames(self):
        """Convert GIF frames to ASCII in background thread with detailed stages"""
        if not self.gif_frames:
            return
        
        self.is_converting = True
        self.progress_var.set(0)
        self.status_label.configure(text="Stage 1/4: Initializing converter... 0%", text_color="#FFA500")
        self.update_idletasks()
        
        def convert():
            try:
                # Stage 1: Initialize
                self.status_label.configure(text="Stage 1/4: Initializing converter...", text_color="#FFA500")
                self.update_idletasks()
                
                config = ConversionConfig(
                    detail_level=self.detail_var.get(),
                    contrast=self.contrast_var.get(),
                    brightness=self.brightness_var.get(),
                    char_ramp=self.ramp_var.get(),
                )
                converter = ASCIIConverter(config)
                
                # Stage 2: Processing frames
                self.status_label.configure(text="Stage 2/4: Processing frames... 0%", text_color="#FFA500")
                self.update_idletasks()
                
                def progress_callback(current, total):
                    percentage = int((current / total) * 100)
                    self.progress_var.set(current / total)
                    self.status_label.configure(text=f"Stage 2/4: Processing frames... {current}/{total} ({percentage}%)", text_color="#FFA500")
                    self.update_idletasks()
                
                self.ascii_frames = converter.convert_gif(self.gif_frames, progress_callback)
                
                # Stage 3: Rendering preview
                self.status_label.configure(text="Stage 3/4: Rendering preview...", text_color="#FFA500")
                self.progress_var.set(0.75)
                self.update_idletasks()
                
                self._display_frame(0)
                
                # Stage 4: Complete
                self.is_converting = False
                self.progress_var.set(1.0)
                self.status_label.configure(text="Stage 4/4: Conversion complete! 100%", text_color="#00FF00")
                
            except Exception as e:
                self.is_converting = False
                self.status_label.configure(text=f"Error: {str(e)}", text_color="#FF0000")
                messagebox.showerror("Error", f"Conversion failed: {str(e)}")
        
        thread = threading.Thread(target=convert, daemon=True)
        thread.start()
    
    def _display_frame(self, idx: int):
        """Display a frame in the preview (plain text for performance)"""
        if not self.ascii_frames or idx >= len(self.ascii_frames):
            return
        
        ascii_frame, colors = self.ascii_frames[idx]
        
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", "\n".join(ascii_frame))
        self.preview_text.configure(state="disabled")
        
        # Auto-fit font size to display entire ASCII art
        self._auto_fit_display(ascii_frame)
        
        self.current_frame_idx = idx
    
    def _auto_fit_display(self, ascii_frame: List[str]):
        """Auto-fit font size to display entire ASCII art in viewport"""
        if not ascii_frame:
            return
        
        # Get frame dimensions
        frame_width = len(ascii_frame[0]) if ascii_frame else 0
        frame_height = len(ascii_frame)
        
        # Get preview widget dimensions
        self.preview_text.update()
        widget_width = self.preview_text.winfo_width()
        widget_height = self.preview_text.winfo_height()
        
        if widget_width <= 1 or widget_height <= 1:
            return
        
        # Estimate character dimensions (monospace font)
        # Approximate: each character is about 7-8 pixels wide and 14-16 pixels tall
        char_width = 7
        char_height = 14
        
        # Calculate required font size to fit content
        # Leave some padding (90% of available space)
        max_width_chars = int((widget_width * 0.9) / char_width)
        max_height_chars = int((widget_height * 0.9) / char_height)
        
        # Determine if we need to scale down
        width_ratio = frame_width / max_width_chars if max_width_chars > 0 else 1
        height_ratio = frame_height / max_height_chars if max_height_chars > 0 else 1
        
        # Use the larger ratio to ensure everything fits
        scale_ratio = max(width_ratio, height_ratio, 1.0)
        
        # Calculate new font size (start from current or default)
        current_font_size = self.font_size_var.get()
        new_font_size = max(6, int(current_font_size / scale_ratio))
        
        # Only update if significantly different to avoid constant changes
        if abs(new_font_size - current_font_size) > 1:
            self.font_size_var.set(new_font_size)
            self.preview_text.configure(font=("Courier New", new_font_size))
    
    def _play(self):
        """Start playback"""
        if not self.ascii_frames:
            messagebox.showwarning("Warning", "Load a GIF first")
            return
        
        self.is_playing = True
        self._animate()
    
    def _pause(self):
        """Pause playback"""
        self.is_playing = False
    
    def _stop(self):
        """Stop playback"""
        self.is_playing = False
        self._display_frame(0)
    
    def _animate(self):
        """Animation loop - non-blocking"""
        if not self.is_playing or not self.ascii_frames:
            return
        
        self._display_frame(self.current_frame_idx)
        self.current_frame_idx += 1
        
        if self.current_frame_idx >= len(self.ascii_frames):
            if self.loop_var.get():
                self.current_frame_idx = 0
            else:
                self.is_playing = False
                return
        
        delay = int(1000 / self.fps)
        # Use after() instead of blocking - allows UI to respond
        self.after(delay, self._animate)
    
    def _on_config_change(self, *args):
        """Handle configuration changes with debouncing"""
        if not self.gif_frames or self.is_converting:
            return
        
        # Cancel previous timer if exists
        if self.slider_timer:
            self.after_cancel(self.slider_timer)
        
        # Debounce: wait 300ms before re-converting
        self.slider_timer = self.after(300, self._convert_frames)
    
    def _on_font_size_change(self, *args):
        """Handle font size changes"""
        size = self.font_size_var.get()
        self.preview_text.configure(font=("Courier New", size))
    
    def _on_window_resize(self, event=None):
        """Handle window resize to auto-fit ASCII art"""
        if self.ascii_frames and self.current_frame_idx < len(self.ascii_frames):
            ascii_frame, _ = self.ascii_frames[self.current_frame_idx]
            self._auto_fit_display(ascii_frame)
    
    def _export(self):
        """Export ASCII art with format selection and detailed progress tracking"""
        if not self.ascii_frames:
            messagebox.showwarning("Warning", "Convert a GIF first")
            return
        
        # Create export dialog with format selection
        export_window = ctk.CTkToplevel(self)
        export_window.title("Export Options")
        export_window.geometry("400x350")
        export_window.resizable(False, False)
        
        ctk.CTkLabel(export_window, text="Select Export Format", font=("Arial", 14, "bold")).pack(pady=20)
        
        format_var = tk.StringVar(value="ansi")
        
        formats = [
            ("Text - ANSI Colors (fastest)", "ansi"),
            ("Text - Plain (fast)", "txt"),
            ("Animated GIF (colored)", "gif"),
            ("HTML (interactive)", "html"),
        ]
        
        # Add MP4 option only if current file is MP4
        if self.is_mp4:
            formats.append(("MP4 Video (with original audio)", "mp4"))
        
        for label, value in formats:
            ctk.CTkRadioButton(export_window, text=label, variable=format_var, value=value).pack(anchor="w", padx=20, pady=5)
        
        def do_export():
            ext_map = {"gif": ".gif", "ansi": ".txt", "txt": ".txt", "html": ".html", "mp4": ".mp4"}
            filepath = filedialog.asksaveasfilename(
                defaultextension=ext_map[format_var.get()],
                filetypes=[("All files", "*.*")]
            )
            
            if not filepath:
                return
            
            export_window.destroy()
            
            # Create progress window
            progress_window = ctk.CTkToplevel(self)
            progress_window.title("Exporting...")
            progress_window.geometry("450x180")
            progress_window.resizable(False, False)
            
            ctk.CTkLabel(progress_window, text="Exporting, please wait...", font=("Arial", 12, "bold")).pack(pady=10)
            
            progress_bar = ctk.CTkProgressBar(progress_window)
            progress_bar.pack(fill="x", padx=20, pady=10)
            progress_bar.set(0)
            
            percentage_label = ctk.CTkLabel(progress_window, text="0%", font=("Arial", 11))
            percentage_label.pack(pady=5)
            
            status_label = ctk.CTkLabel(progress_window, text="Starting export...", font=("Arial", 10), text_color="#888888")
            status_label.pack(pady=5)
            
            stage_label = ctk.CTkLabel(progress_window, text="", font=("Arial", 9), text_color="#FFA500")
            stage_label.pack(pady=3)
            
            def export_in_thread():
                try:
                    format_choice = format_var.get()
                    
                    def progress_callback(current, total, message=""):
                        if total > 0:
                            percentage = int((current / total) * 100)
                            progress_bar.set(current / total)
                            percentage_label.configure(text=f"{percentage}%")
                        else:
                            progress_bar.set(0)
                            percentage_label.configure(text="0%")
                        
                        if message:
                            stage_label.configure(text=message)
                        
                        self.update_idletasks()
                    
                    if format_choice == "gif":
                        stage_label.configure(text="Stage: Rendering GIF frames")
                        self.update_idletasks()
                        ASCIIExporter.export_gif(self.ascii_frames, self.fps, filepath, self.font_size_var.get(), progress_callback)
                    elif format_choice == "ansi":
                        stage_label.configure(text="Stage: Writing ANSI colored text")
                        self.update_idletasks()
                        ASCIIExporter.export_text_fast(self.ascii_frames, filepath)
                        progress_bar.set(1.0)
                        percentage_label.configure(text="100%")
                    elif format_choice == "txt":
                        stage_label.configure(text="Stage: Writing plain text")
                        self.update_idletasks()
                        ascii_only = [frame[0] for frame in self.ascii_frames]
                        ASCIIExporter.export_text(ascii_only, filepath)
                        progress_bar.set(1.0)
                        percentage_label.configure(text="100%")
                    elif format_choice == "html":
                        stage_label.configure(text="Stage: Generating HTML with colors")
                        self.update_idletasks()
                        ASCIIExporter.export_html(self.ascii_frames, self.fps, filepath)
                        progress_bar.set(1.0)
                        percentage_label.configure(text="100%")
                    elif format_choice == "mp4":
                        stage_label.configure(text="Stage: Rendering MP4 frames")
                        self.update_idletasks()
                        ASCIIExporter.export_mp4(self.ascii_frames, self.fps, filepath, self.audio_path, self.font_size_var.get(), progress_callback)
                    
                    progress_bar.set(1.0)
                    percentage_label.configure(text="100%")
                    status_label.configure(text="Export complete!", text_color="#00FF00")
                    stage_label.configure(text="Stage: Complete")
                    self.after(1500, progress_window.destroy)
                    messagebox.showinfo("Success", f"Exported to {Path(filepath).name}")
                except Exception as e:
                    status_label.configure(text=f"Error: {str(e)}", text_color="#FF0000")
                    stage_label.configure(text="Stage: Error occurred")
                    self.after(2000, progress_window.destroy)
                    messagebox.showerror("Error", f"Export failed: {str(e)}")
            
            thread = threading.Thread(target=export_in_thread, daemon=True)
            thread.start()
        
        ctk.CTkButton(export_window, text="Export", command=do_export).pack(pady=20)
        ctk.CTkButton(export_window, text="Cancel", command=export_window.destroy).pack(pady=5)


if __name__ == "__main__":
    app = GIFToASCIIApp()
    app.mainloop()
