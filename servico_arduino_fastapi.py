import asyncio
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import requests
import serial
import serial.tools.list_ports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

PORTA_SERIAL_PADRAO = "COM3"
BAUD_RATE = 9600
INTERVALO_LEITURA_SEGUNDOS = 3.0

DISTANCIA_FUNDO_CM = 100.0
ALTURA_MAXIMA_AGUA_CM = 80.0

ENVIAR_PARA_FLASK = True
URL_BASE_FLASK = "http://127.0.0.1:5000"
ENDERECO_IP_SENSOR = "192.168.1.204"
NOME_RESERVATORIO = "Cisterna Bancada (Arduino)"
CAPACIDADE_MAXIMA_LITROS = 100.0
FAMILIAS_ATENDIDAS = 45
TEM_SERVICO_ESSENCIAL = True

historico_leituras: deque[dict] = deque(maxlen=50)
ultima_leitura: Optional[dict] = None
reservatorio_registrado = False
status_serial = {
    "conectado": False,
    "porta": PORTA_SERIAL_PADRAO,
    "ultimo_erro": None,
}

def detectar_porta_arduino() -> str:
    """Usa a porta padrão configurada ou tenta localizar um Arduino na USB."""
    portas = list(serial.tools.list_ports.comports())
    for p in portas:
        if p.device.upper() == PORTA_SERIAL_PADRAO.upper():
            return p.device
    for p in portas:
        descricao = f"{p.description} {p.manufacturer}".lower()
        if any(termo in descricao for termo in ("arduino", "ch340", "usb serial", "usb-serial")):
            return p.device
    return PORTA_SERIAL_PADRAO

def calcular_nivel(distancia_cm: float) -> dict:
    """Converte a distância medida pelo HC-SR04 no formato esperado pelo SensorUltrassonicoCmAdapter."""
    coluna_agua_cm = max(0.0, min(ALTURA_MAXIMA_AGUA_CM, DISTANCIA_FUNDO_CM - distancia_cm))
    percentual = (
        round((coluna_agua_cm / ALTURA_MAXIMA_AGUA_CM) * 100.0, 1)
        if ALTURA_MAXIMA_AGUA_CM > 0
        else 0.0
    )
    return {
        "endereco_ip_sensor": ENDERECO_IP_SENSOR,
        "tipo_sensor": "ultrassonico_hcsr04",
        "distancia_cm": round(distancia_cm, 1),
        "nivel_cm": round(coluna_agua_cm, 1),
        "altura_maxima_cm": ALTURA_MAXIMA_AGUA_CM,
        "percentual": percentual,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

def garantir_cadastro_reservatorio() -> None:
    """Cadastra ou atualiza a cisterna física no Flask antes de enviar medições."""
    global reservatorio_registrado
    if reservatorio_registrado or not ENVIAR_PARA_FLASK:
        return
    payload = {
        "nome": NOME_RESERVATORIO,
        "tipo": "Cisterna Física",
        "endereco_ip_sensor": ENDERECO_IP_SENSOR,
        "capacidade_maxima_litros": CAPACIDADE_MAXIMA_LITROS,
        "familias_atendidas": FAMILIAS_ATENDIDAS,
        "tem_servico_essencial": TEM_SERVICO_ESSENCIAL,
    }
    try:
        resp = requests.post(f"{URL_BASE_FLASK}/api/reservatorios", json=payload, timeout=2.0)
        if resp.status_code in (200, 201):
            reservatorio_registrado = True
    except requests.RequestException:
        pass

def enviar_para_backend_flask(payload: dict) -> None:
    """Envia a leitura para o Flask sem interromper o FastAPI caso o Flask esteja offline."""
    if not ENVIAR_PARA_FLASK:
        return
    garantir_cadastro_reservatorio()
    try:
        resp = requests.post(f"{URL_BASE_FLASK}/api/medicoes", json=payload, timeout=2.0)
        if resp.status_code == 201:
            dados = resp.json()
            print(
                f"   -> [Flask] {dados.get('volume_convertido_litros')} L "
                f"({dados.get('adapter_utilizado')})"
            )
    except requests.RequestException:
        pass

def consultar_sensor_serial(conexao: serial.Serial) -> Optional[float]:
    """Envia 'X' pela porta Serial e lê a resposta numérica do Arduino."""
    conexao.reset_input_buffer()
    conexao.write(b"X")
    resposta = conexao.readline().decode("utf-8", errors="ignore").strip()

    if not resposta or resposta.upper() == "ERRO":
        return None
    try:
        return float(resposta)
    except ValueError:
        return None


async def loop_leitura_arduino() -> None:
    """Tarefa em segundo plano que mantém a comunicação contínua com o Arduino."""
    global ultima_leitura
    conexao: Optional[serial.Serial] = None

    while True:
        try:
            if conexao is None or not conexao.is_open:
                porta = detectar_porta_arduino()
                status_serial["porta"] = porta
                conexao = await asyncio.to_thread(
                    serial.Serial, porta, BAUD_RATE, timeout=2.0
                )
                await asyncio.sleep(2.0)
                status_serial["conectado"] = True
                status_serial["ultimo_erro"] = None
                print(f"[Serial] Conectado ao Arduino na porta {porta}")

            distancia_cm = await asyncio.to_thread(consultar_sensor_serial, conexao)

            if distancia_cm is not None:
                registro = calcular_nivel(distancia_cm)
                ultima_leitura = registro
                historico_leituras.append(registro)
                print(
                    f"[Leitura] Distância: {registro['distancia_cm']} cm | "
                    f"Nível: {registro['nivel_cm']} cm ({registro['percentual']}%)"
                )
                await asyncio.to_thread(enviar_para_backend_flask, registro)
            else:
                print("[Aviso] Sensor retornou sem leitura válida.")

        except serial.SerialException as erro:
            status_serial["conectado"] = False
            status_serial["ultimo_erro"] = str(erro)
            print(f"[Erro Serial] {erro}. Tentando reconectar...")
            if conexao is not None:
                try:
                    conexao.close()
                except Exception:
                    pass
                conexao = None
        except asyncio.CancelledError:
            if conexao is not None and conexao.is_open:
                conexao.close()
            break

        await asyncio.sleep(INTERVALO_LEITURA_SEGUNDOS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    tarefa = asyncio.create_task(loop_leitura_arduino())
    yield
    tarefa.cancel()
    await tarefa

app = FastAPI(
    title="Serviço Serial Arduino - Monitoramento de Reservatório",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def raiz():
    return {
        "servico": "FastAPI Arduino Serial Bridge",
        "serial": status_serial,
        "total_leituras_memoria": len(historico_leituras),
        "ultima_leitura": ultima_leitura,
    }

@app.get("/distancia")
def obter_ultima_distancia():
    if ultima_leitura is None:
        raise HTTPException(
            status_code=503,
            detail="Aguardando primeira leitura válida do sensor HC-SR04.",
        )
    return ultima_leitura

@app.get("/leituras")
def obter_historico_leituras():
    return {
        "total": len(historico_leituras),
        "leituras": list(historico_leituras),
    }