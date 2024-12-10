import time
from PIL import ImageGrab, Image
import socket
from typing import Tuple

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

def capture_screen_area(area: Tuple[int, int, int, int]) -> Image.Image:
    """Capture screen area and return PIL Image"""
    return ImageGrab.grab(bbox=area)

def resize_image(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """Resize image to specified size"""
    return image.resize(size, Image.Resampling.LANCZOS)

def send_frame(ip: str, image: Image.Image, port: int = 80) -> bool:
    """Send a single frame to display and wait for acknowledgment"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Create new connection for each frame
        sock.connect((ip, port))
        sock.settimeout(1.0)  # 设置1秒超时
        
        # Send image dimensions
        width, height = image.size
        sock.send(width.to_bytes(2, byteorder='big'))
        sock.send(height.to_bytes(2, byteorder='big'))
        
        # Send image data
        image_data = image_to_rgb565_bytes(image)
        chunk_size = 1024
        for i in range(0, len(image_data), chunk_size):
            chunk = image_data[i:i + chunk_size]
            sock.send(chunk)
        
        # Wait for acknowledgment
        response = sock.recv(2)
        print(f"Response: {response}")
        return response == b'OK'
        
    except socket.timeout:
        return False
    except Exception:
        return False
        
    finally:
        sock.close()

def main():
    # Configuration
    ESP8266_IP = "192.168.2.206"
    TFT_SIZE = (240, 240)
    CAPTURE_AREA = (100, 100, 800, 800)
    
    print(f"Starting screen mirror...")
    print(f"Capture area: {CAPTURE_AREA}")
    print(f"Press Ctrl+C to stop")
    frames_sent = 0
    try:
        while True:
            # Capture and process frame
            screenshot = capture_screen_area(CAPTURE_AREA)
            resized = resize_image(screenshot, TFT_SIZE)
            # Send frame and check acknowledgment
            send_frame(ESP8266_IP, resized)
    except KeyboardInterrupt:
        print(f"\nStopped after sending {frames_sent} frames")
if __name__ == '__main__':
    main()