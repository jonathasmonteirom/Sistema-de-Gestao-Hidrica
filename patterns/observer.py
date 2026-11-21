from abc import ABC, abstractmethod
from datetime import datetime
from models import db, MedicaoHistorico, AtendimentoPipa

class ObservadorAlerta(ABC):
    @abstractmethod
    def atualizar(self, reservatorio, segundos_restantes, taxa_descida, data_esgotamento):
        pass

class AgendadorCarroPipaObserver(ObservadorAlerta):
    def atualizar(self, reservatorio, segundos_restantes, taxa_descida, data_esgotamento):
        chamado_aberto = AtendimentoPipa.query.filter_by(
            reservatorio_id=reservatorio.id,
            status='Pendente'
        ).first()

        if not chamado_aberto:
            novo_atendimento = AtendimentoPipa(
                reservatorio_id=reservatorio.id,
                dias_restantes_estimados=round(segundos_restantes / 86400, 4),
                status='Pendente'
            )
            db.session.add(novo_atendimento)
            db.session.commit()
            print(f"Chamado de carro-pipa agendado para '{reservatorio.nome}' (ID {reservatorio.id}).")

class NotificadorPainelObserver(ObservadorAlerta):
    def atualizar(self, reservatorio, segundos_restantes, taxa_descida, data_esgotamento):
        print(
            f"(Alerta) Reservatório '{reservatorio.nome}' (IP {reservatorio.endereco_ip_sensor}) "
            f"esgotará em {segundos_restantes:.1f}s (Previsão: {data_esgotamento.strftime('%H:%M:%S')}) | "
            f"Consumo: {taxa_descida:.2f} L/s"
        )

class MonitorReservatorio:
    def __init__(self, limite_critico_segundos=25.0):
        self._observadores = []
        self.limite_critico_segundos = limite_critico_segundos

    def anexar(self, observador: ObservadorAlerta):
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desanexar(self, observador: ObservadorAlerta):
        self._observadores.remove(observador)

    def notificar(self, reservatorio, segundos_restantes, taxa_descida, data_esgotamento):
        for observador in self._observadores:
            observador.atualizar(reservatorio, segundos_restantes, taxa_descida, data_esgotamento)

    def avaliar_reservatorio(self, reservatorio):
        medicoes = MedicaoHistorico.query.filter_by(reservatorio_id=reservatorio.id)\
                                         .order_by(MedicaoHistorico.data_hora_medicao.desc())\
                                         .limit(3).all()

        if len(medicoes) < 2:
            return

        medicoes.reverse()

        m1 = medicoes[0]
        x1 = m1.data_hora_medicao.timestamp()
        y1 = m1.volume_litros

        m2 = medicoes[-1]
        x2 = m2.data_hora_medicao.timestamp()
        y2 = m2.volume_litros

        if x2 == x1:
            return

        a = (y2 - y1) / (x2 - x1)
        if a >= 0:
            return 

        b = y1 - (a * x1)
        x_zero = -b / a
        segundos_restantes = x_zero - x2

        if segundos_restantes <= self.limite_critico_segundos:
            data_esgotamento = datetime.fromtimestamp(x_zero)
            self.notificar(reservatorio, max(0.0, segundos_restantes), abs(a), data_esgotamento)