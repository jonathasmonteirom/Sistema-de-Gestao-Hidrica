import os
import time
import threading
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from models import db, Usuario, Reservatorio, MedicaoHistorico, AtendimentoPipa
from patterns.observer import MonitorReservatorio, AgendadorCarroPipaObserver, NotificadorPainelObserver
from patterns.strategy import OrdenadorFilaPipa, ESTRATEGIAS_DISPONIVEIS
from patterns.adapter import resolver_adapter

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///cisternas_teste.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

monitor_agua = MonitorReservatorio(limite_critico_segundos=25.0)
monitor_agua.anexar(AgendadorCarroPipaObserver())
monitor_agua.anexar(NotificadorPainelObserver())


def obter_ou_criar_gestor_padrao():
    usuario = Usuario.query.filter_by(email="teste@prefeitura.gov").first()
    if not usuario:
        usuario = Usuario(nome="Gestor Prefeitura", email="teste@prefeitura.gov")
        db.session.add(usuario)
        db.session.commit()
    return usuario

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/reservatorios', methods=['POST'])
def cadastrar_ou_atualizar_reservatorio():
    dados = request.json
    ip = dados.get('endereco_ip_sensor')
    nome = dados.get('nome')

    if not ip or not nome:
        return jsonify({"erro": "Os campos 'nome' e 'endereco_ip_sensor' são obrigatórios."}), 400

    reservatorio = Reservatorio.query.filter_by(endereco_ip_sensor=ip).first()
    usuario = obter_ou_criar_gestor_padrao()

    if reservatorio:
        reservatorio.nome = nome
        reservatorio.tipo = dados.get('tipo', reservatorio.tipo)
        reservatorio.capacidade_maxima_litros = dados.get('capacidade_maxima_litros', reservatorio.capacidade_maxima_litros)
        reservatorio.familias_atendidas = dados.get('familias_atendidas', reservatorio.familias_atendidas)
        reservatorio.tem_servico_essencial = dados.get('tem_servico_essencial', reservatorio.tem_servico_essencial)
        mensagem = "Reservatório atualizado com sucesso!"
        status_code = 200
    else:
        reservatorio = Reservatorio(
            usuario_id=usuario.id,
            nome=nome,
            tipo=dados.get('tipo', 'Cisterna'),
            capacidade_maxima_litros=dados.get('capacidade_maxima_litros', 100.0),
            endereco_ip_sensor=ip,
            familias_atendidas=dados.get('familias_atendidas', 0),
            tem_servico_essencial=dados.get('tem_servico_essencial', False)
        )
        db.session.add(reservatorio)
        mensagem = "Reservatório cadastrado com sucesso!"
        status_code = 201

    db.session.commit()
    return jsonify({
        "mensagem": mensagem,
        "id": reservatorio.id,
        "nome": reservatorio.nome,
        "endereco_ip_sensor": reservatorio.endereco_ip_sensor,
        "familias_atendidas": reservatorio.familias_atendidas,
        "tem_servico_essencial": reservatorio.tem_servico_essencial
    }), status_code

@app.route('/api/reservatorios', methods=['GET'])
def listar_reservatorios():
    reservatorios = Reservatorio.query.all()
    resultado = []
    for r in reservatorios:
        ultima_medicao = MedicaoHistorico.query.filter_by(reservatorio_id=r.id)\
                                               .order_by(MedicaoHistorico.data_hora_medicao.desc())\
                                               .first()
        resultado.append({
            "id": r.id,
            "nome": r.nome,
            "tipo": r.tipo,
            "ip_sensor": r.endereco_ip_sensor,
            "capacidade_maxima_litros": r.capacidade_maxima_litros,
            "volume_atual_litros": ultima_medicao.volume_litros if ultima_medicao else None,
            "familias_atendidas": r.familias_atendidas,
            "tem_servico_essencial": r.tem_servico_essencial
        })
    return jsonify(resultado), 200

@app.route('/api/medicoes', methods=['POST'])
def receber_medicao():
    dados = request.json or {}
    ip = dados.get('endereco_ip_sensor')

    if not ip:
        return jsonify({"erro": "O campo 'endereco_ip_sensor' é obrigatório."}), 400

    reservatorio = Reservatorio.query.filter_by(endereco_ip_sensor=ip).first()

    if not reservatorio:
        usuario = obter_ou_criar_gestor_padrao()
        reservatorio = Reservatorio(
            usuario_id=usuario.id,
            nome=f"Cisterna {ip}",
            tipo="Cisterna",
            capacidade_maxima_litros=dados.get('capacidade_maxima_litros', 100.0),
            endereco_ip_sensor=ip
        )
        db.session.add(reservatorio)
        db.session.commit()

    try:
        adapter = resolver_adapter(dados)
        volume = adapter.obter_volume_litros(dados, reservatorio)
    except (ValueError, TypeError) as e:
        return jsonify({"erro": str(e)}), 400

    nova_medicao = MedicaoHistorico(
        reservatorio_id=reservatorio.id,
        volume_litros=volume
    )
    db.session.add(nova_medicao)
    db.session.commit()

    monitor_agua.avaliar_reservatorio(reservatorio)

    return jsonify({
        "mensagem": "Dados adaptados e guardados com sucesso.",
        "adapter_utilizado": adapter.__class__.__name__,
        "volume_convertido_litros": volume
    }), 201


@app.route('/api/reservatorios/<int:id_reservatorio>/previsao', methods=['GET'])
def prever_esgotamento(id_reservatorio):
    medicoes = MedicaoHistorico.query.filter_by(reservatorio_id=id_reservatorio)\
                                     .order_by(MedicaoHistorico.data_hora_medicao.desc())\
                                     .limit(3).all()
    
    if len(medicoes) < 2:
        return jsonify({"erro": "São necessárias pelo menos 2 medições para calcular a reta."}), 400
        
    medicoes.reverse()
    
    m1 = medicoes[0]
    x1 = m1.data_hora_medicao.timestamp()
    y1 = m1.volume_litros
    
    m2 = medicoes[-1]
    x2 = m2.data_hora_medicao.timestamp()
    y2 = m2.volume_litros
    
    if x2 == x1:
        return jsonify({"erro": "Medições feitas no mesmo instante, impossível calcular a descida."}), 400
        
    a = (y2 - y1) / (x2 - x1)
    
    if a >= 0:
        return jsonify({
            "mensagem": "O nível da água está estável ou subindo.",
            "volume_atual": y2
        }), 200
        
    b = y1 - (a * x1)
    x_zero = -b / a
    data_esgotamento = datetime.fromtimestamp(x_zero)
    
    return jsonify({
        "reservatorio_id": id_reservatorio,
        "volume_atual_litros": y2,
        "taxa_descida_litros_por_segundo": abs(a),
        "previsao_fim_da_agua": data_esgotamento.strftime('%Y-%m-%d %H:%M:%S')
    }), 200


@app.route('/api/atendimentos', methods=['GET'])
def listar_atendimentos():
    criterio = request.args.get('criterio', 'urgencia').lower()
    classe_estrategia = ESTRATEGIAS_DISPONIVEIS.get(criterio)

    if not classe_estrategia:
        return jsonify({
            "erro": f"Critério '{criterio}' inválido. Use: {list(ESTRATEGIAS_DISPONIVEIS.keys())}"
        }), 400

    pendentes = AtendimentoPipa.query.filter_by(status='Pendente').all()

    ordenador = OrdenadorFilaPipa(classe_estrategia())
    fila_ordenada = ordenador.executar_ordenacao(pendentes)

    resultado = []
    for posicao, item in enumerate(fila_ordenada, start=1):
        resultado.append({
            "posicao_fila": posicao,
            "id_atendimento": item.id,
            "reservatorio_id": item.reservatorio.id,
            "reservatorio": item.reservatorio.nome,
            "ip_sensor": item.reservatorio.endereco_ip_sensor,
            "familias_atendidas": item.reservatorio.familias_atendidas,
            "tem_servico_essencial": item.reservatorio.tem_servico_essencial,
            "dias_restantes_estimados": item.dias_restantes_estimados,
            "status": item.status,
            "data_alerta": item.data_alerta.strftime('%Y-%m-%d %H:%M:%S')
        })

    return jsonify({
        "criterio_aplicado": criterio,
        "total_pendentes": len(resultado),
        "fila_prioridade": resultado
    }), 200


@app.route('/api/atendimentos/<int:id_atendimento>/concluir', methods=['PATCH', 'POST'])
def concluir_atendimento(id_atendimento):
    atendimento = AtendimentoPipa.query.get(id_atendimento)

    if not atendimento:
        return jsonify({"erro": "Atendimento não encontrado."}), 404

    if atendimento.status == 'Concluido':
        return jsonify({"mensagem": "Este atendimento já foi concluído anteriormente."}), 200

    atendimento.status = 'Concluido'
    atendimento.data_conclusao = datetime.utcnow()

    reservatorio = atendimento.reservatorio
    reabastecimento = MedicaoHistorico(
        reservatorio_id=reservatorio.id,
        volume_litros=reservatorio.capacidade_maxima_litros
    )
    db.session.add(reabastecimento)
    db.session.commit()

    return jsonify({
        "mensagem": f"Abastecimento concluído para '{reservatorio.nome}'. Tanque restaurado para {reservatorio.capacidade_maxima_litros}L.",
        "id_atendimento": atendimento.id,
        "status": atendimento.status,
        "data_conclusao": atendimento.data_conclusao.strftime('%Y-%m-%d %H:%M:%S')
    }), 200


def monitoramento_em_segundo_plano(intervalo_segundos=10):
    while True:
        time.sleep(intervalo_segundos)
        with app.app_context():
            try:
                reservatorios = Reservatorio.query.all()
                for reservatorio in reservatorios:
                    monitor_agua.avaliar_reservatorio(reservatorio)
            except Exception as e:
                print(f"[MONITOR 2] Erro na verificação periódica: {e}")


if __name__ == '__main__':
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        thread_monitor = threading.Thread(
            target=monitoramento_em_segundo_plano,
            args=(10,),
            daemon=True
        )
        thread_monitor.start()
        print("Monitoramento em segundo plano iniciado (10s).")

    app.run(host='0.0.0.0', port=5000, debug=True)