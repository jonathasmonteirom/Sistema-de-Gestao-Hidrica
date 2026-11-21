from abc import ABC, abstractmethod

class EstrategiaPriorizacao(ABC):
    @abstractmethod
    def ordenar(self, atendimentos: list) -> list:
        pass

class PrioridadeUrgenciaTempo(EstrategiaPriorizacao):
    def ordenar(self, atendimentos: list) -> list:
        return sorted(
            atendimentos,
            key=lambda item: item.dias_restantes_estimados if item.dias_restantes_estimados is not None else float('inf')
        )

class PrioridadeImpactoSocial(EstrategiaPriorizacao):
    def ordenar(self, atendimentos: list) -> list:
        return sorted(
            atendimentos,
            key=lambda item: (
                -(item.reservatorio.familias_atendidas or 0),
                item.dias_restantes_estimados if item.dias_restantes_estimados is not None else float('inf')
            )
        )

class PrioridadeServicoEssencial(EstrategiaPriorizacao):
    def ordenar(self, atendimentos: list) -> list:
        return sorted(
            atendimentos,
            key=lambda item: (
                not bool(item.reservatorio.tem_servico_essencial),
                -(item.reservatorio.familias_atendidas or 0),
                item.dias_restantes_estimados if item.dias_restantes_estimados is not None else float('inf')
            )
        )

class OrdenadorFilaPipa:
    def __init__(self, estrategia: EstrategiaPriorizacao = None):
        self._estrategia = estrategia or PrioridadeUrgenciaTempo()

    def definir_estrategia(self, estrategia: EstrategiaPriorizacao):
        self._estrategia = estrategia

    def executar_ordenacao(self, atendimentos: list) -> list:
        return self._estrategia.ordenar(atendimentos)

ESTRATEGIAS_DISPONIVEIS = {
    'urgencia': PrioridadeUrgenciaTempo,
    'familias': PrioridadeImpactoSocial,
    'essencial': PrioridadeServicoEssencial
}