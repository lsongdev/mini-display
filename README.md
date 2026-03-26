# Mini Display

A WiFi-based screen mirroring project that streams your computer display to an ESP8266-driven TFT display in real-time.

## Overview

This project consists of two components:
- **ESP8266 Firmware** (PlatformIO): Receives display data over WiFi and renders it to a TFT screen
- **Python Sender**: Captures screen regions and streams them to the ESP8266

## Features

- **Real-time screen mirroring** over WiFi
- **Differential updates**: Only sends changed screen regions for efficiency
- **Multiple display modes**:
  - `full`: No processing, just resize
  - `crop-both`: Crop both sides equally
  - `crop-start`: Keep start side (left/top)
  - `crop-end`: Keep end side (right/bottom)
  - `pad`: Add black padding to match aspect ratio
- **Configurable FPS** (default: 30)
- **RGB565 color format** for efficient transmission

## Hardware Requirements

- ESP8266 (NodeMCU v2 tested)
- TFT display (240x240, ST7789/ILI9341 compatible via TFT_eSPI)
- WiFi network

## Software Requirements

### ESP8266 Firmware

- [PlatformIO](https://platformio.org/)
- [TFT_eSPI library](https://github.com/lsongdev/TFT_eSPI)

### Python Sender

- Python 3
- Dependencies:
  ```bash
  pip3 install numpy pillow
  ```

## Installation

### ESP8266 Firmware

1. Clone the repository
2. Open in PlatformIO (VS Code recommended)
3. Configure your WiFi credentials in `src/main.cpp`:
   ```cpp
   const char* ssid = "your-wifi-ssid";
   const char* password = "your-wifi-password";
   ```
4. Build and upload:
   ```bash
   pio run --target upload
   ```

### Python Sender

1. Install dependencies:
   ```bash
   pip3 install numpy pillow
   ```
2. Run the sender:
   ```bash
   python3 send.py --ip <esp8266-ip-address>
   ```

## Usage

### Basic Usage

```bash
# Default settings (pad mode, 30 FPS)
python3 send.py --ip 192.168.2.206

# Custom display mode
python3 send.py --ip 192.168.2.206 --mode crop-both

# Custom FPS
python3 send.py --ip 192.168.2.206 --fps 60
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ip` | 192.168.2.206 | ESP8266 IP address |
| `--width` | Full screen | Capture area width |
| `--height` | Full screen | Capture area height |
| `--fps` | 30.0 | Target frames per second |
| `--mode` | pad | Display mode (full/crop-both/crop-start/crop-end/pad) |

### Display Modes

- **full**: Stretches the entire screen to fit the display (may distort)
- **crop-both**: Crops equally from both sides to maintain aspect ratio
- **crop-start**: Crops from the end, keeping the start visible
- **crop-end**: Crops from the start, keeping the end visible
- **pad**: Adds black bars to maintain aspect ratio (recommended)

## Configuration

### PlatformIO (`platformio.ini`)

```ini
[env:nodemcuv2]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps =
    https://github.com/lsongdev/TFT_eSPI
monitor_speed = 115200
```

### Display Settings

The firmware is configured for a **240x240** display. To change this, modify the validation in `src/main.cpp`:

```cpp
if (x + width > 240 || y + height > 240 || ...)
```

## Protocol

The communication protocol uses TCP port 80:

1. Client sends number of update regions (1 byte)
2. For each region:
   - X coordinate (2 bytes, big-endian)
   - Y coordinate (2 bytes, big-endian)
   - Width (2 bytes, big-endian)
   - Height (2 bytes, big-endian)
   - Pixel data (width × height × 2 bytes, RGB565)
3. Server responds with "OK" acknowledgment

## Troubleshooting

### Connection Issues

- Ensure ESP8266 and computer are on the same WiFi network
- Check the ESP8266 IP address via Serial Monitor
- Verify firewall settings allow TCP port 80

### Display Issues

- Verify TFT_eSPI library is properly configured for your display
- Check wiring connections
- Adjust `monitor_speed` if serial output is garbled

### Performance Issues

- Reduce FPS for slower networks
- Use a smaller capture area with `--width` and `--height`
- Try different display modes for better performance

## License

This project is open source. Feel free to modify and distribute.

## Contributing

Issues and pull requests are welcome!
