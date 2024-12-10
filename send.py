#!/usr/bin/env python3

import time
from PIL import ImageGrab, Image
import socket
from typing import Tuple, List, Optional, NamedTuple, Callable, Literal
import numpy as np
import argparse
import sys

class Region(NamedTuple):
    x: int
    y: int
    width: int
    height: int
    data: bytes

# Image Processing Functions
def rgb888_to_rgb565(r: int, g: int, b: int) -> Tuple[int, int]:
    """Convert RGB888 to RGB565 bytes"""
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return rgb565 & 0xFF, (rgb565 >> 8) & 0xFF

def image_to_rgb565_bytes(image: Image.Image) -> bytes:
    """Convert image to RGB565 format bytes"""
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    pixels = []
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b = image.getpixel((x, y))
            lsb, msb = rgb888_to_rgb565(r, g, b)
            pixels.extend([lsb, msb])
    
    return bytes(pixels)

def get_screen_size() -> Tuple[int, int]:
    """Get the primary screen resolution"""
    screenshot = ImageGrab.grab()
    return screenshot.size

def capture_screen_area(area: Tuple[int, int, int, int]) -> Image.Image:
    """Capture screen area and return PIL Image"""
    return ImageGrab.grab(bbox=area)

def get_region_data(image: Image.Image, x: int, y: int, width: int, height: int) -> bytes:
    """Extract data for a specific region from the image"""
    region = image.crop((x, y, x + width, y + height))
    return image_to_rgb565_bytes(region)

# Display Mode Processors
def process_full(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Full mode: no processing, just resize"""
    return image.resize(target_size, Image.Resampling.LANCZOS)

def process_crop(image: Image.Image, target_size: Tuple[int, int], crop_mode: Literal['both', 'start', 'end'] = 'both') -> Image.Image:
    """Crop mode: crop image to match target ratio
    
    Args:
        image: Input image
        target_size: Target size (width, height)
        crop_mode: 
            - 'both': crop both sides equally
            - 'start': keep start side (left/top)
            - 'end': keep end side (right/bottom)
    """
    width, height = image.size
    target_ratio = target_size[0] / target_size[1]
    current_ratio = width / height
    
    if current_ratio > target_ratio:
        # 图片太宽，需要裁切
        new_width = int(height * target_ratio)
        if crop_mode == 'both':
            x = (width - new_width) // 2
        elif crop_mode == 'start':
            x = 0
        else:  # end
            x = width - new_width
        cropped = image.crop((x, 0, x + new_width, height))
    else:
        # 图片太高，需要裁切
        new_height = int(width / target_ratio)
        if crop_mode == 'both':
            y = (height - new_height) // 2
        elif crop_mode == 'start':
            y = 0
        else:  # end
            y = height - new_height
        cropped = image.crop((0, y, width, y + new_height))
    
    return cropped.resize(target_size, Image.Resampling.LANCZOS)

def process_pad(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Pad mode: pad to match target ratio"""
    width, height = image.size
    target_ratio = target_size[0] / target_size[1]
    current_ratio = width / height
    
    if current_ratio > target_ratio:
        # 图片太宽，上下填充
        new_height = int(width / target_ratio)
        new_image = Image.new('RGB', (width, new_height), (0, 0, 0))
        y_offset = (new_height - height) // 2
        new_image.paste(image, (0, y_offset))
    else:
        # 图片太高，左右填充
        new_width = int(height * target_ratio)
        new_image = Image.new('RGB', (new_width, height), (0, 0, 0))
        x_offset = (new_width - width) // 2
        new_image.paste(image, (x_offset, 0))
    
    return new_image.resize(target_size, Image.Resampling.LANCZOS)

def get_processor(mode: str) -> Callable:
    """Get the appropriate image processor for the given mode"""
    return DISPLAY_MODES.get(mode, process_full)

# Network Functions
def find_changed_regions(current: Image.Image, previous: Optional[Image.Image], chunk_size: int = 32) -> List[Region]:
    """Find regions that have changed between two frames"""
    if previous is None:
        # First frame - send everything
        return [Region(
            x=0, y=0,
            width=current.width,
            height=current.height,
            data=image_to_rgb565_bytes(current)
        )]

    regions = []
    # Convert images to numpy arrays for faster comparison
    curr_array = np.array(current)
    prev_array = np.array(previous)
    
    height, width = curr_array.shape[:2]
    
    # Check each chunk for changes
    for y in range(0, height, chunk_size):
        for x in range(0, width, chunk_size):
            chunk_width = min(chunk_size, width - x)
            chunk_height = min(chunk_size, height - y)
            
            curr_chunk = curr_array[y:y+chunk_height, x:x+chunk_width]
            prev_chunk = prev_array[y:y+chunk_height, x:x+chunk_width]
            
            if not np.array_equal(curr_chunk, prev_chunk):
                region_data = get_region_data(
                    current, x, y, chunk_width, chunk_height)
                regions.append(Region(
                    x=x, y=y,
                    width=chunk_width,
                    height=chunk_height,
                    data=region_data
                ))
    
    return regions

def send_regions(ip: str, regions: List[Region], port: int = 80, timeout: float = 1.0) -> bool:
    """Send update regions to display"""
    if not regions:
        return True

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((ip, port))
            sock.settimeout(timeout)
            # Send number of regions
            sock.send(len(regions).to_bytes(1, byteorder='big'))
            for region in regions:
                # Send region metadata
                sock.send(region.x.to_bytes(2, byteorder='big'))
                sock.send(region.y.to_bytes(2, byteorder='big'))
                sock.send(region.width.to_bytes(2, byteorder='big'))
                sock.send(region.height.to_bytes(2, byteorder='big'))
                
                # Send region data
                chunk_size = 1024
                data = region.data
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i + chunk_size]
                    sock.send(chunk)
            
            # Wait for acknowledgment
            response = sock.recv(2)
            return response == b'OK'
            
    except Exception as e:
        # print(f"Error sending update: {e}")
        return False

# Display Mode Registry
DISPLAY_MODES = {
    'full': process_full,
    'crop-both': lambda img, size: process_crop(img, size, 'both'),
    'crop-start': lambda img, size: process_crop(img, size, 'start'),
    'crop-end': lambda img, size: process_crop(img, size, 'end'),
    'pad': process_pad,
}

# Main Functions
def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Screen mirror with differential updates')
    parser.add_argument('--ip', type=str, default="192.168.2.206", help='IP address')
    parser.add_argument('--width', type=int, help='Capture area width (default: full screen)')
    parser.add_argument('--height', type=int, help='Capture area height (default: full screen)')
    parser.add_argument('--fps', type=float, default=30.0, help='Target frames per second (default: 30)')
    parser.add_argument('--mode', type=str, choices=['full', 'crop-both', 'crop-start', 'crop-end', 'pad'],  default='pad', 
        help=
        'Display mode: full (no processing), crop-both (crop both sides), '
        'crop-start (keep start side), crop-end (keep end side), '
        'pad (add black padding)')

    return parser.parse_args()

def clear_line():
    """Clear the current line"""
    sys.stdout.write('\033[2K\033[1G')
    sys.stdout.flush()

def print_progress(current: int, total: int, width: int = 50):
    """Print a simple progress bar with color"""
    progress = current / total
    bar_width = int(width * progress)
    # Use red for completed part only, with spaces for padding
    bar = '\033[31m' + '━' * bar_width + ' ' * (width - bar_width) + '\033[0m'
    percent = int(progress * 100)
    # Move cursor to the start of the progress bar and clear to end of line
    sys.stdout.write('\033[1G\033[K')
    # Print the progress bar with new format
    sys.stdout.write(f'Sending {bar} {percent:3d}% ({current}/{total})')
    sys.stdout.flush()

def main():
    args = parse_args()
    
    # Hide cursor
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()
    
    # Configuration
    TFT_SIZE = (240, 240)
    screen_width, screen_height = get_screen_size()
    frame_delay = 1.0 / args.fps
    
    # Get capture area
    capture_area = (0, 0, screen_width, screen_height)
    if args.width is not None and args.height is not None:
        capture_area = (0, 0, args.width, args.height)
    
    # Get image processor
    process_image = get_processor(args.mode)
    
    previous_frame = None
    
    # Print initial info
    print(f"Screen resolution: {screen_width}x{screen_height}")
    print(f"Capture area: {capture_area}")
    print(f"Display mode: {args.mode}")
    print(f"Target FPS: {args.fps}")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            start_time = time.time()
            # Capture screen
            screenshot = capture_screen_area(capture_area)
            # Process image according to display mode
            current_frame = process_image(screenshot, TFT_SIZE)
            # Find changed regions and send updates
            regions = find_changed_regions(current_frame, previous_frame)
            for i, region in enumerate(regions, 1):
                print_progress(i, len(regions))
                send_regions(args.ip, [region])
            
            previous_frame = current_frame
            # Calculate sleep time to maintain target FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_delay - elapsed)
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        clear_line()
        print("\nStopped screen mirror")
    finally:
        # Show cursor
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()

if __name__ == '__main__':
    main()