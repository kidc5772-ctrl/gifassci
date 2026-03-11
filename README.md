# GIF to ASCII Art Converter

A modern, feature-rich GUI application that converts animated GIFs and MP4 videos into ASCII art with live playback, customizable rendering, and multiple export options.

## Features

### Core Functionality
- **GIF & MP4 Loading**: Load animated GIFs or MP4 videos
- **Frame Conversion**: Converts every frame to high-quality ASCII art
- **Live Playback**: Animated ASCII display at original frame rate
- **Playback Controls**: Play, pause, stop, and loop toggle
- **Multiple Export Formats**: GIF, MP4 (with audio), HTML, ANSI text, plain text

### ASCII Conversion Quality
- **70+ Character Ramp**: Full brightness gradient from light to dark
- **Multiple Ramp Styles**: Simple, detailed, blocks-only, or full Unicode
- **Color Support**: Each character colored to match original pixel colors
- **Adjustable Detail**: Slider to control pixels-per-character ratio
- **Image Enhancement**: Contrast and brightness adjustment sliders

### Performance & Optimization
- **Multi-threading**: Uses CPU threads for fast frame processing
- **GPU Acceleration**: Numba JIT compilation for AMD GPU support
- **Background Processing**: All conversions run in background threads
- **Efficient Rendering**: Optimized pixel processing with NumPy

### UI Features
- **Live Preview**: Large monospace preview window with real-time updates
- **File Info Panel**: Displays frame count, FPS, and dimensions
- **Responsive Design**: Preview auto-scales to fit window
- **Dark Theme**: Modern, easy-on-the-eyes interface
- **Detailed Progress Tracking**: Multi-stage progress with percentages
- **Font Size Control**: Adjust preview text size from 6pt to 16pt

## Installation

### Requirements
- Python 3.8+
- pip
- ffmpeg (for MP4 audio extraction and muxing)

### Setup

1. Clone or download this repository
2. Install ffmpeg:
   - **Windows**: `winget install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`
3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Application
```bash
python gif_to_ascii.py
```

Or run the compiled executable:
```bash
dist/gif_to_ascii.exe
```

### Basic Workflow

1. **Load Media**: Click "Load GIF/MP4" button and select an animated GIF or MP4 file
2. **Adjust Settings** (optional):
   - **Detail Level**: Higher = sharper output but more characters (1-20)
   - **Contrast**: Enhance or reduce image contrast (0.5-2.0)
   - **Brightness**: Lighten or darken the output (-1.0 to 1.0)
   - **Character Ramp**: Choose between different character sets
   - **Font Size**: Adjust preview text size (6-16pt)
3. **Preview**: Watch the ASCII animation in real-time
4. **Playback Controls**:
   - **Play**: Start animation
   - **Pause**: Pause at current frame
   - **Stop**: Return to first frame
   - **Loop**: Toggle automatic restart
5. **Export**: Choose format and save

### Export Formats

- **Animated GIF (.gif)**: Colored ASCII frames as animated GIF
- **MP4 Video (.mp4)**: Colored ASCII video with original audio (MP4 files only)
- **ANSI Text (.txt)**: Fast colored text with ANSI codes
- **Plain Text (.txt)**: Simple ASCII without colors
- **HTML (.html)**: Interactive web player with controls and frame counter

## Technical Details

### Architecture

- **GIFLoader**: Extracts frames and metadata from GIF files
- **MP4Loader**: Extracts frames from MP4 videos with audio extraction
- **ASCIIConverter**: Converts images to ASCII with multi-threading support
- **EdgeDetector**: Detects edges for better character selection
- **ASCIIExporter**: Exports to GIF, MP4, HTML, ANSI text, and plain text formats
- **GIFToASCIIApp**: Main GUI application using customtkinter

### Performance Optimizations

- **Multi-threading**: Uses ThreadPoolExecutor for parallel frame processing (up to 16 threads)
- **GPU Acceleration**: Numba JIT compilation for fast brightness calculations on AMD GPUs
- **NumPy Vectorization**: Fast pixel processing using vectorized operations
- **Background Threading**: All conversions and exports run in background threads
- **Selective GPU Usage**: Only uses GPU for large frames (>10,000 pixels) to avoid overhead

### Supported Media

- **GIF**: Animated GIFs of any length, variable frame rates, any resolution
- **MP4**: Video files with audio extraction and re-muxing support

## Customization

### Character Ramps

The app includes four built-in character ramps:

- **Simple**: ` .:-=+*#%@` - Basic brightness gradient
- **Detailed**: 70+ characters for maximum detail
- **Blocks**: Unicode block characters for smooth gradients
- **Full**: Minimal character set for bold contrast

### Color Modes

- **ANSI Colors**: 256-color palette for terminal output
- **HTML Colors**: Full RGB color support in HTML export
- **GIF/MP4 Colors**: Full RGB rendering in video exports

## Troubleshooting

### Media Won't Load
- Ensure the file is a valid GIF or MP4
- Check file permissions
- Try a different media file

### Conversion is Slow
- Reduce detail level (higher pixels-per-character)
- Use smaller media files
- Close other applications

### MP4 Export Has No Audio
- Ensure ffmpeg is installed and in PATH
- Check that the source MP4 has audio
- Try exporting as GIF instead

### Preview Text is Too Small/Large
- Use the Font Size slider to adjust
- Resize the window to see more/less content

### Sliders Are Glitchy
- Wait for conversion to complete before adjusting sliders
- Sliders have 300ms debounce to prevent rapid re-conversions

## Tips for Best Results

1. **Detail Level**: Start at 4-6 for balanced output
2. **Contrast**: Increase for high-contrast images, decrease for subtle details
3. **Character Ramp**: Use "detailed" for photos, "blocks" for graphics
4. **Media Size**: Smaller files convert faster and display better
5. **Frame Rate**: Original frame rate is preserved in playback and exports
6. **MP4 Export**: Best for preserving audio from source videos

## License

This project is provided as-is for personal and educational use.

## Future Enhancements

Potential features for future versions:
- WebP export format (faster than GIF)
- Frame sampling/decimation for faster exports
- GPU batch rendering for MP4 export
- Real-time webcam ASCII conversion
- Custom character ramp editor
- Batch processing
- Advanced edge detection algorithms
- Video codec selection for MP4 export
