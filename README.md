# Gestão Hídrica e Logística de Carros-Pipa

Sistema web para monitoramento em tempo real do nível de água em cisternas comunitárias e gerenciamento automatizado da fila de abastecimento por carros-pipa. A aplicação integra leituras de hardware físico via Arduino (sensor ultrassônico HC-SR04) e sensores simulados, utilizando os padrões de projeto **Adapter** (normalização de medições em litros, centímetros ou percentual), **Observer** (cálculo da taxa de esgotamento e abertura automática de chamados críticos) e **Strategy** (ordenação dinâmica da fila de prioridade por urgência, número de famílias atendidas ou presença de serviços essenciais).

## Pré-requisitos

* Docker e Docker Compose instalados (Docker Desktop em execução).
* Python 3.10 ou superior instalado na máquina local (necessário apenas para comunicação com o Arduino físico via porta serial).

## Como executar

### 1. Subir o servidor web e o banco de dados (Docker)

Na raiz do projeto, inicie os containers do Flask e do PostgreSQL:

```bash
docker compose up --build
```

Acesse o painel de monitoramento no navegador em: `[http://127.0.0.1:5000](http://127.0.0.1:5000)`

### 2. Conectar o sensor físico Arduino (Opcional)

Como containers Docker no Windows não acessam diretamente a porta USB (`COM3`), a ponte serial em FastAPI deve rodar localmente:

1. Grave o código `arduino/sensor_cisterna.ino` na placa Arduino.
2. Instale as dependências Python na máquina local:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Inicie o serviço de leitura serial em um novo terminal (+):
   ```bash
   python -m uvicorn servico_arduino_fastapi:app --port 8000
   ```

### 3. Rodar o simulador de cisternas (Opcional)

Para simular múltiplas comunidades consumindo água simultaneamente sem depender do sensor físico, execute em outro terminal (+):

```bash
docker compose exec web python simulador_sensor.py
```

### 4. Encerrar a aplicação

Para parar e remover os containers em execução:

```bash
docker compose down
```