from flask import Flask, render_template, request
from flask_socketio import SocketIO, send
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///safichat.db'
db = SQLAlchemy(app)
socketio = SocketIO(app)

class Perfil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    avatar = db.Column(db.String(10), nullable=False)
    canal = db.Column(db.String(20), nullable=False)
    bio = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=True)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/canal/<nome>')
def canal(nome):
    return render_template('chat.html', canal=nome)

@app.route('/perfis')
def mostrar_perfis():
    perfis = Perfil.query.all()
    return render_template('perfis.html', perfis=perfis)

@socketio.on('message')
def handle_message(msg):
    print(f'Mensagem recebida: {msg}')
    if "entrou no chat!" in msg:
        partes = msg.split(" ")
        avatar = partes[0]
        nome = partes[1]
        canal = request.args.get('canal', 'geral')

        existente = Perfil.query.filter_by(nome=nome, canal=canal).first()
        if not existente:
            novo = Perfil(nome=nome, avatar=avatar, canal=canal)
            db.session.add(novo)
            db.session.commit()

    send(msg, broadcast=True)

@socketio.on('perfil')
def salvar_perfil(data):
    existente = Perfil.query.filter_by(nome=data['nome'], canal=data['canal']).first()
    if not existente:
        novo = Perfil(
            nome=data['nome'],
            avatar=data['avatar'],
            canal=data['canal'],
            bio=data['bio'],
            status=data['status']
        )
        db.session.add(novo)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
