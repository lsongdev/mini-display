import time
from PIL import ImageGrab, Image
import socket
from typing import Tuple, List, Dict, Optional, NamedTuple
import numpy as np

class Region(NamedTuple):
    x: int
    y: int
    width: int
    height: int
    data: bytes

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

def get_region_data(image: Image.Image, x: int, y: int, width: int, height: int) -> bytes:
    """Extract data for a specific region from the image"""
    region = image.crop((x, y, x + width, y + height))
    return image_to_rgb565_bytes(region)

def find_changed_regions(
    current: Image.Image,
    previous: Optional[Image.Image],
    chunk_size: int = 32
) -> List[Region]:
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

def send_regions(
    ip: str,
    regions: List[Region],
    port: int = 80,
    timeout: float = 1.0
) -> bool:
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
        print(f"Error sending update: {e}")
        return False

def capture_screen_area(area: Tuple[int, int, int, int]) -> Image.Image:
    """Capture screen area and return PIL Image"""
    return ImageGrab.grab(bbox=area)

def resize_image(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """Resize image to specified size"""
    return image.resize(size, Image.Resampling.LANCZOS)

def main():
    # Configuration
    ESP8266_IP = "192.168.2.206"
    TFT_SIZE = (240, 240)
    CAPTURE_AREA = (100, 100, 800, 800)
    previous_frame = None
    
    print(f"Starting screen mirror with differential updates...")
    print(f"Capture area: {CAPTURE_AREA}")
    print(f"Press Ctrl+C to stop")
    
    try:
        while True:
            # Capture and process frame
            screenshot = capture_screen_area(CAPTURE_AREA)
            current_frame = resize_image(screenshot, TFT_SIZE)
            
            # Find changed regions and send updates
            regions = find_changed_regions(current_frame, previous_frame)
            if regions:
                print(f"Sending {len(regions)} updated regions")
                send_regions(ESP8266_IP, regions)
            
            previous_frame = current_frame
            time.sleep(0.033)  # Cap at ~30fps
            
    except KeyboardInterrupt:
        print("\nStopped screen mirror")

if __name__ == '__main__':
    main()