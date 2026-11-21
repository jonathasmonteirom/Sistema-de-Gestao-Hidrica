#include <LiquidCrystal.h>

// Pinagem física da bancada: RS=6, E=7, D4=10, D5=11, D6=12, D7=13
LiquidCrystal lcd(6, 7, 10, 11, 12, 13);

// Sensor HC-SR04: Trig=9, Echo=8
const int trigPin = 9;
const int echoPin = 8;

float ultimaDistanciaCm = -1.0;
unsigned long ultimaAtualizacao = 0;
const unsigned long intervaloLeituraMs = 300;

float medirDistanciaCm() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  unsigned long duracao = pulseIn(echoPin, HIGH, 30000);
  if (duracao == 0) {
    return -1.0;
  }
  return (duracao * 0.0343) / 2.0;
}

void setup() {
  Serial.begin(9600);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  digitalWrite(trigPin, LOW);

  lcd.begin(16, 2);
  lcd.setCursor(0, 0);
  lcd.print("Sensor HC-SR04");
  lcd.setCursor(0, 1);
  lcd.print("Aguardando...");
  delay(1500);
  lcd.clear();
}

void loop() {
  unsigned long agora = millis();
  if (agora - ultimaAtualizacao >= intervaloLeituraMs) {
    ultimaAtualizacao = agora;
    ultimaDistanciaCm = medirDistanciaCm();

    lcd.setCursor(0, 0);
    lcd.print("Distancia:      ");
    lcd.setCursor(0, 1);
    if (ultimaDistanciaCm < 0) {
      lcd.print("Sem leitura     ");
    } else {
      lcd.print(ultimaDistanciaCm, 1);
      lcd.print(" cm          ");
    }
  }

  // Responde ao FastAPI (COM3 a 9600 baud) apenas quando receber 'X'
  if (Serial.available() > 0) {
    char comando = Serial.read();
    if (comando == 'X' || comando == 'x') {
      if (ultimaDistanciaCm < 0) {
        Serial.println("ERRO");
      } else {
        Serial.println(ultimaDistanciaCm, 1);
      }
    }
  }
}