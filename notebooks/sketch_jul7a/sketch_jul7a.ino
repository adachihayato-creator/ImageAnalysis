// =============================================================
//  SK6812 フルカラーテープLED (1m / 30LED) 2系統制御スケッチ
//  対象ボード : Arduino Nano
//  ライブラリ : Adafruit NeoPixel
//
//  動作:
//    D6 のテープ -> レインボーが流れるアニメーション(従来どおり)
//    D5 のテープ -> 全LEDを白色で固定点灯
//
//  配線:
//    [D6テープ] DIN -> Arduino D6 (330Ω推奨), 5V -> 5V, GND -> GND
//    [D5テープ] DIN -> Arduino D5 (330Ω推奨), 5V -> 5V, GND -> GND
//  ※ どちらも「矢印の根元(DIN側)」を Arduino につなぐこと
//  ※ GND は全て共通にする
// =============================================================

#include <Adafruit_NeoPixel.h>

// ----- 設定 -----
#define LED_PIN_RGB    6    // レインボー側テープのデータピン(D6)
#define LED_PIN_WHITE  5    // 白色固定側テープのデータピン(D5)
#define LED_COUNT      30   // 各テープのLED数(どちらも30個)
#define BRIGHTNESS     150   // 明るさ 0〜255。USB給電なので低めに設定(電力対策)
                            // 2本に増えた分、電流も増えるので注意(下のメモ参照)

// 2本のテープをそれぞれ別オブジェクトとして生成
//   SK6812(RGB)は NEO_GRB + NEO_KHZ800 で動作する
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN_RGB, NEO_GRB + NEO_KHZ800);        // D6: レインボー
Adafruit_NeoPixel stripWhite(LED_COUNT, LED_PIN_WHITE, NEO_GRB + NEO_KHZ800); // D5: 白固定

void setup() {
  // --- D6テープ(レインボー)の初期化 ---
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  strip.show();  // いったん全消灯

  // --- D5テープ(白固定)の初期化 ---
  stripWhite.begin();
  stripWhite.setBrightness(BRIGHTNESS);
  // 全LEDを白色(R=G=B=255)で点灯。SK6812はデータを保持するので一度だけ送ればよい
  for (int i = 0; i < stripWhite.numPixels(); i++) {
    stripWhite.setPixelColor(i, stripWhite.Color(255, 255, 255));
  }
  stripWhite.show();

  // --- 起動時の動作確認(D6のみ): 赤→緑→青を順番に全点灯 ---
  colorWipe(strip.Color(255, 0, 0), 30); // 赤
  colorWipe(strip.Color(0, 255, 0), 30); // 緑
  colorWipe(strip.Color(0, 0, 255), 30); // 青
}

void loop() {
  // D6のテープだけレインボーを流し続ける
  // (D5の白はsetupで点灯済み。保持されるのでloopで触らなくてよい)
  rainbow(10);
}

// 1個ずつ指定色で塗りつぶしていく(D6用)
void colorWipe(uint32_t color, int wait) {
  for (int i = 0; i < strip.numPixels(); i++) {
    strip.setPixelColor(i, color);
    strip.show();
    delay(wait);
  }
}

// テープ全体に虹色を流す(D6用)
void rainbow(int wait) {
  // 色相を一周(65536)させる
  for (long firstPixelHue = 0; firstPixelHue < 65536; firstPixelHue += 256) {
    for (int i = 0; i < strip.numPixels(); i++) {
      // 各LEDに少しずつ色相をずらして割り当てる
      int pixelHue = firstPixelHue + (i * 65536L / strip.numPixels());
      strip.setPixelColor(i, strip.gamma32(strip.ColorHSV(pixelHue)));
    }
    strip.show();
        delay(wait);
  }
}