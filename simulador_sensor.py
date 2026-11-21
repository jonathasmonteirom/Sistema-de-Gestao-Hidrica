import time
import threading
import requests
from datetime import datetime

URL_BASE = "http://127.0.0.1:5000"

COMUNIDADES_SIMULADAS = [
    {
        "nome": "Comunidade Cuité",
        "ip": "192.168.1.201",
        "capacidade_litros": 100.0,
        "familias_atendidas": 60,
        "tem_servico_essencial": False,
        "formato_sensor": "litros",       
        "valor_inicial": 100.0,
        "consumo_por_segundo": 3.0
    },
    {
        "nome": "Vila Nova Floresta",
        "ip": "192.168.1.202",
        "capacidade_litros": 100.0,
        "familias_atendidas": 25,
        "tem_servico_essencial": True,
        "formato_sensor": "cm",           
        "valor_inicial": 200.0,
        "consumo_por_segundo": 4.0
    },
    {
        "nome": "Sitío Picuí",
        "ip": "192.168.1.203",
        "capacidade_litros": 100.0,
        "familias_atendidas": 35,
        "tem_servico_essencial": False,
        "formato_sensor": "percentual",   
        "valor_inicial": 1.0,
        "consumo_por_segundo": 0.025
    }
]

def registrar_comunidade(config):
    payload = {
        "nome": config["nome"],
        "endereco_ip_sensor": config["ip"],
        "capacidade_maxima_litros": config["capacidade_litros"],
        "familias_atendidas": config["familias_atendidas"],
        "tem_servico_essencial": config["tem_servico_essencial"]
    }
    try:
        requests.post(f"{URL_BASE}/api/reservatorios", json=payload, timeout=5)
    except Exception as e:
        print(f"Erro ao registrar {config['nome']}: {e}")

def montar_payload_sensor(config, valor_atual):
    formato = config["formato_sensor"]
    payload = {"endereco_ip_sensor": config["ip"]}

    if formato == "litros":
        payload["volume_litros"] = round(valor_atual, 2)
    elif formato == "cm":
        payload["nivel_cm"] = round(valor_atual, 2)
        payload["altura_maxima_cm"] = 200.0
    elif formato == "percentual":
        payload["percentual"] = round(valor_atual, 4)

    return payload

def simular_reservatorio(config):
    nivel = config["valor_inicial"]
    segundos_decorridos = 0
    formato = config["formato_sensor"]

    print(f"[INÍCIO] {config['nome']} ({config['ip']}) | Sensor: {formato.upper()}")

    while nivel > 0:
        time.sleep(1)
        segundos_decorridos += 1
        nivel = max(0.0, nivel - config["consumo_por_segundo"])

        if segundos_decorridos % 5 == 0 or nivel == 0:
            payload = montar_payload_sensor(config, nivel)
            try:
                resposta = requests.post(f"{URL_BASE}/api/medicoes", json=payload, timeout=5)
                dados_resp = resposta.json()
                hora = datetime.now().strftime('%H:%M:%S')
                print(
                    f"[{hora}] {config['nome']} | Enviado ({formato}): {nivel:.2f} "
                    f"API converteu: {dados_resp.get('volume_convertido_litros')}L "
                    f"({dados_resp.get('adapter_utilizado')})"
                )
            except Exception as e:
                print(f"Erro ao enviar dados de {config['nome']}: {e}")

    print(f"[ESGOTADO] {config['nome']} chegou a zero.")

if __name__ == "__main__":
    for comunidade in COMUNIDADES_SIMULADAS:
        registrar_comunidade(comunidade)

    threads = []
    for comunidade in COMUNIDADES_SIMULADAS:
        t = threading.Thread(target=simular_reservatorio, args=(comunidade,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("\nSimulação de todas as comunidades finalizada.")