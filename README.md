# GIF to ASCII Art Converter

A modern, feature-rich GUI application that converts animated GIFs into ASCII art with live playback, customizable rendering, and export options.

## Features

### Core Functionality
- **GIF Loading**: Browse and load any GIF file
- **Frame Conversion**: Converts every frame to high-quality ASCII art
- **Live Playback**: Animated ASCII display at original GIF frame rate
- **Playback Controls**: Play, pause, stop, and loop toggle
- **Export Options**: Save as plain text or interactive HTML

### ASCII Conversion Quality
- **70+ Character Ramp**: Full brightness gradient from light to dark
- **Multiple Ramp Styles**: Simple, detailed, blocks-only, or full Unicode
- **Color Support**: Each character colored to match original pixel colors
- **Adjustable Detail**: Slider to control pixels-per-character ratio
- **Image Enhancement**: Contrast and brightness adjustment sliders

### UI Features
- **Live Preview**: Large monospace preview window with real-time updates
- **File Info Panel**: Displays frame count, FPS, and dimensions
- **Responsive Design**: Preview scales with window size
- **Dark Theme**: Modern, easy-on-the-eyes interface
- **Progress Tracking**: Visual progress bar during conversion
- **Font Size Control**: Adjust preview text size from 6pt to 16pt

## Installation

### Requirements
- Python 3.8+
- pip

### Setup

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Application
```bash
python gif_to_ascii.py
```

### Basic Workflow

1. **Load a GIF**: Click "Load GIF" button and select an animated GIF file
2. **Adjust Settings** (optional):
   - **Detail Level**: Higher = sharper output but more characters
   - **Contrast**: Enhance or reduce image contrast
   - **Brightness**: Lighten or darken the output
   - **Character Ramp**: Choose between different character sets
   - **Font Size**: Adjust preview text size
3. **Preview**: Watch the ASCII animation in real-time
4. **Playback Controls**:
   - **Play**: Start animation
   - **Pause**: Pause at current frame
   - **Stop**: Return to first frame
   - **Loop**: Toggle automatic restart
5. **Export**: Save as text or HTML file

### Export Formats

- **Text (.txt)**: Plain ASCII art, one frame per section
- **HTML (.html)**: Interactive HTML with colored ASCII, play/pause controls, and frame counter

## Technical Details

### Architecture

- **GIFLoader**: Extracts frames and metadata from GIF files
- **ASCIIConverter**: Converts images to ASCII with configurable parameters
- **EdgeDetector**: Detects edges for better character selection
- **ASCIIExporter**: Exports to text or HTML formats
- **GIFToASCIIApp**: Main GUI application using customtkinter

### Performance

- **Background Threading**: Frame conversion runs in background thread to keep UI responsive
- **NumPy Optimization**: Fast pixel processing using NumPy arrays
- **Efficient Rendering**: Only updates display when needed

### Supported GIF Features

- Animated GIFs of any length
- Variable frame rates
- Transparency (converted to white background)
- Any resolution

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

## Troubleshooting

### GIF Won't Load
- Ensure the file is a valid GIF
- Check file permissions
- Try a different GIF file

### Conversion is Slow
- Reduce detail level (higher pixels-per-character)
- Use a smaller GIF
- Close other applications

### Preview Text is Too Small/Large
- Use the Font Size slider to adjust
- Resize the window to see more/less content

## Tips for Best Results

1. **Detail Level**: Start at 4-6 for balanced output
2. **Contrast**: Increase for high-contrast images, decrease for subtle details
3. **Character Ramp**: Use "detailed" for photos, "blocks" for graphics
4. **GIF Size**: Smaller GIFs convert faster and display better
5. **Frame Rate**: Original GIF frame rate is preserved in playback

## License

This project is provided as-is for personal and educational use.

## Future Enhancements

Potential features for future versions:
- Video file support (MP4, WebM, etc.)
- Real-time webcam ASCII conversion
- Custom character ramp editor
- Batch processing
- GIF creation from ASCII frames
- Advanced edge detection algorithms
