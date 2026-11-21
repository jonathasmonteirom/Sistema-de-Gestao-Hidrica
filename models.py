from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    reservatorios = db.relationship('Reservatorio', backref='gestor', lazy=True, cascade="all, delete-orphan")

class Reservatorio(db.Model):
    __tablename__ = 'reservatorios'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    capacidade_maxima_litros = db.Column(db.Float, nullable=False)
    endereco_ip_sensor = db.Column(db.String(45), unique=True)
    
    familias_atendidas = db.Column(db.Integer, default=0)
    tem_servico_essencial = db.Column(db.Boolean, default=False)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    medicoes = db.relationship('MedicaoHistorico', backref='reservatorio', lazy=True, cascade="all, delete-orphan")
    atendimentos = db.relationship('AtendimentoPipa', backref='reservatorio', lazy=True, cascade="all, delete-orphan")

class MedicaoHistorico(db.Model):
    __tablename__ = 'medicoes_historico'
    
    id = db.Column(db.Integer, primary_key=True)
    reservatorio_id = db.Column(db.Integer, db.ForeignKey('reservatorios.id'), nullable=False)
    volume_litros = db.Column(db.Float, nullable=False)
    data_hora_medicao = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class AtendimentoPipa(db.Model):
    __tablename__ = 'atendimentos_pipa'
    
    id = db.Column(db.Integer, primary_key=True)
    reservatorio_id = db.Column(db.Integer, db.ForeignKey('reservatorios.id'), nullable=False)
    dias_restantes_estimados = db.Column(db.Float)
    status = db.Column(db.String(30), default='Pendente')
    data_alerta = db.Column(db.DateTime, default=datetime.utcnow)
    data_conclusao = db.Column(db.DateTime, nullable=True)