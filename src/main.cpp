#include <ESP8266WiFi.h>
#include <TFT_eSPI.h>
#include <SPI.h>

// 初始化显示屏
TFT_eSPI tft = TFT_eSPI();

// WiFi配置
const char* ssid = "wifi@lsong.one";
const char* password = "song940@163.com";

// 服务器端口
WiFiServer server(80);

// 使用更小的缓冲区，每次处理一行数据
const int BUFFER_HEIGHT = 1;  // 每次处理一行
const int SCREEN_WIDTH = 240;
uint16_t lineBuffer[SCREEN_WIDTH * BUFFER_HEIGHT];

void setup() {
  Serial.begin(115200);
  
  // 初始化显示屏
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);
  
  // 连接WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  
  // 启动服务器
  server.begin();
}

void loop() {
  WiFiClient client = server.available();
  if (!client) {
    return;
  }
  
  Serial.println("New client connected");
  
  // 等待客户端发送数据
  unsigned long timeout = millis() + 5000;  // 5秒超时
  while (!client.available() && millis() < timeout) {
    delay(10);
  }
  
  if (!client.available()) {
    Serial.println("Client timeout");
    client.stop();
    return;
  }
  
  // 等待积累足够的数据
  delay(100);
  
  // 读取图像尺寸信息
  if (client.available() < 4) {
    Serial.println("Invalid header");
    client.stop();
    return;
  }
  
  uint16_t width = (client.read() << 8) | client.read();
  uint16_t height = (client.read() << 8) | client.read();
  
  if (width != 240 || height != 240) {
    Serial.printf("Invalid dimensions: %dx%d\n", width, height);
    client.stop();
    return;
  }
  
  Serial.printf("Receiving image: %dx%d\n", width, height);
  
  // 逐行接收和显示图像
  for (int y = 0; y < height; y++) {
    // 读取一行数据
    int bytesRead = 0;
    unsigned long lineTimeout = millis() + 1000;  // 每行1秒超时
    
    while (bytesRead < width * 2) {  // *2 因为每个像素2字节
      if (client.available()) {
        // 直接以高字节在前接收
        uint8_t msb = client.read();
        uint8_t lsb = client.read();
        lineBuffer[bytesRead/2] = (msb << 8) | lsb;
        bytesRead += 2;
      } else if (millis() > lineTimeout) {
        Serial.printf("Timeout reading line %d\n", y);
        client.stop();
        return;
      }
      yield();  // 让出CPU给WiFi任务
    }
    
    // 显示这一行数据
    tft.pushImage(0, y, width, 1, lineBuffer);
    
    // 每10行让出一次CPU时间
    if (y % 10 == 0) {
      yield();
    }
  }
  
  // 发送成功确认信息
  Serial.println("Image received successfully");
  client.write("OK");  // 发送简短的确认消息
  delay(10);  // 短暂延迟确保消息发送
  
  // 清理连接
  while (client.available()) {
    client.read();  // 清空任何剩余数据
  }
  client.stop();
}