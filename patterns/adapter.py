from abc import ABC, abstractmethod

class LeitorSensorAdapter(ABC):
    @abstractmethod
    def obter_volume_litros(self, dados: dict, reservatorio) -> float:
        pass

class SensorLitrosAdapter(LeitorSensorAdapter):
    def obter_volume_litros(self, dados: dict, reservatorio) -> float:
        return round(float(dados['volume_litros']), 2)

class SensorUltrassonicoCmAdapter(LeitorSensorAdapter):
    def obter_volume_litros(self, dados: dict, reservatorio) -> float:
        nivel_cm = float(dados['nivel_cm'])
        altura_maxima_cm = float(dados.get('altura_maxima_cm', 200.0))

        if altura_maxima_cm <= 0:
            raise ValueError("A altura máxima do reservatório em cm deve ser maior que zero.")

        proporcao = max(0.0, min(1.0, nivel_cm / altura_maxima_cm))
        return round(proporcao * reservatorio.capacidade_maxima_litros, 2)

class SensorPercentualAdapter(LeitorSensorAdapter):
    def obter_volume_litros(self, dados: dict, reservatorio) -> float:
        valor = float(dados['percentual'])
        if valor > 1.0:
            valor = valor / 100.0

        proporcao = max(0.0, min(1.0, valor))
        return round(proporcao * reservatorio.capacidade_maxima_litros, 2)

ADAPTADORES_SENSOR = {
    'volume_litros': SensorLitrosAdapter,
    'nivel_cm': SensorUltrassonicoCmAdapter,
    'percentual': SensorPercentualAdapter
}

def resolver_adapter(dados: dict) -> LeitorSensorAdapter:
    for chave, classe_adapter in ADAPTADORES_SENSOR.items():
        if chave in dados and dados[chave] is not None:
            return classe_adapter()
    raise ValueError(
        f"Formato de leitura não suportado. Envie uma das chaves: {list(ADAPTADORES_SENSOR.keys())}"
    )