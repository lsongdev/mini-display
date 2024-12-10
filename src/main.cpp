#include <ESP8266WiFi.h>
#include <TFT_eSPI.h>
#include <SPI.h>

// Initialize display
TFT_eSPI tft = TFT_eSPI();

// WiFi configuration
const char* ssid = "wifi@lsong.org";
const char* password = "song940@163.com";

// Server port
WiFiServer server(80);

// Buffer for receiving data
const int MAX_CHUNK_SIZE = 32;  // Maximum size of update regions
uint16_t updateBuffer[MAX_CHUNK_SIZE * MAX_CHUNK_SIZE];

void setup() {
  Serial.begin(115200);
  
  // Initialize display
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  
  server.begin();
}

bool readExactBytes(WiFiClient& client, uint8_t* buffer, size_t length) {
  size_t received = 0;
  unsigned long timeout = millis() + 1000;  // 1 second timeout
  
  while (received < length && millis() < timeout) {
    if (client.available()) {
      buffer[received++] = client.read();
    }
    yield();
  }
  
  return received == length;
}

void loop() {
  WiFiClient client = server.accept();
  if (!client) {
    return;
  }
  
  Serial.println("New client connected");
  
  // Wait for data
  unsigned long timeout = millis() + 5000;
  while (!client.available() && millis() < timeout) {
    delay(10);
  }
  
  if (!client.available()) {
    Serial.println("Client timeout");
    client.stop();
    return;
  }
  
  // Read number of update regions
  uint8_t numRegions = client.read();
  if (numRegions == 0 || numRegions > 100) {  // Sanity check
    Serial.println("Invalid number of regions");
    client.stop();
    return;
  }
  
  Serial.printf("Receiving %d update regions\n", numRegions);
  
  // Process each region
  for (int i = 0; i < numRegions; i++) {
    // Read region metadata
    uint8_t metaData[8];
    if (!readExactBytes(client, metaData, 8)) {
      Serial.println("Failed to read region metadata");
      client.stop();
      return;
    }
    
    uint16_t x = (metaData[0] << 8) | metaData[1];
    uint16_t y = (metaData[2] << 8) | metaData[3];
    uint16_t width = (metaData[4] << 8) | metaData[5];
    uint16_t height = (metaData[6] << 8) | metaData[7];
    
    // Validate dimensions
    if (x + width > 240 || y + height > 240 || 
        width > MAX_CHUNK_SIZE || height > MAX_CHUNK_SIZE) {
      Serial.println("Invalid region dimensions");
      client.stop();
      return;
    }
    
    // Read region data
    size_t pixelCount = width * height;
    // Read data row by row
    for (int row = 0; row < height; row++) {
      uint16_t* rowBuffer = &updateBuffer[row * width];
      uint8_t* byteBuffer = (uint8_t*)rowBuffer;
      
      if (!readExactBytes(client, byteBuffer, width * 2)) {
        Serial.printf("Failed to read row %d of region %d\n", row, i);
        client.stop();
        return;
      }
      
      // Convert byte order if needed
      for (int j = 0; j < width; j++) {
        uint8_t temp = byteBuffer[j*2];
        byteBuffer[j*2] = byteBuffer[j*2 + 1];
        byteBuffer[j*2 + 1] = temp;
      }
    }
    
    // Update display with region data
    tft.pushImage(x, y, width, height, updateBuffer);
    yield();  // Give time to WiFi tasks
  }
  
  // Send acknowledgment
  client.write("OK");
  delay(10);
  
  // Clean up connection
  while (client.available()) {
    client.read();
  }
  client.stop();
}