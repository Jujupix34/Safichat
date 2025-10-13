from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, send, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
from sqlalchemy import desc

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "uma_chave_secreta_padrao")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "senha_admin_padrao")


app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL", 
    "sqlite:///safichat.db"
).replace("postgres://", "postgresql://", 1) 

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

LISTA_CANAIS = [
    'geral', 
    'desabafo', 
    'sapamovies', 
    'poesias', 
    'amor', 
    'amizade', 
    'jogos', 
    'musica'
]


class Perfil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    avatar = db.Column(db.String(10), nullable=False)
    canal = db.Column(db.String(20), nullable=False)
    bio = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    foto = db.Column(db.String(200), nullable=True)
    senha = db.Column(db.String(200), nullable=False)

def get_dm_room_name(user1, user2):
    
    users = sorted([user1, user2])
    return f"dm_{users[0]}_{users[1]}"



@app.route("/")
def home():
    

    perfis_vitrine = Perfil.query.order_by(desc(Perfil.id)).limit(4).all()
    
    
    mensagens_teste = [
        {"usuario": "Joana", "texto": "Amei o novo canal Sapamovies! Alguém já viu 'The L Word'?", "tempo": "1 min atrás"},
        {"usuario": "Lia", "texto": "Canal Desabafo me ajudou muito hoje. Gratidão a todas.", "tempo": "3 min atrás"},
        {"usuario": "Marcela", "texto": "Entrem no canal 'Jogos' para uma partida de Among Us!", "tempo": "5 min atrás"},
    ]

    return render_template("home.html", 
                           perfis_vitrine=perfis_vitrine, 
                           mensagens_teste=mensagens_teste, 
                           canais=LISTA_CANAIS)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")

        perfil = Perfil.query.filter_by(nome=nome).first()
        if perfil and check_password_hash(perfil.senha, senha):
            session["autenticado"] = True
            session["usuario"] = nome
            
            return redirect(url_for("mostrar_perfis")) 
        else:
            erro = "Nome ou senha incorretos."
            return render_template("login.html", erro=erro)
    return render_template("login.html")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")
        
    
        avatar_inicial = random.choice(["🌸", "✨", "🌈", "🦋", "🌷", "💜", "🦄", "💖"])

        if not nome or not senha:
            erro = "Preencha todos os campos."
            return render_template("cadastro.html", erro=erro)

        existente = Perfil.query.filter_by(nome=nome).first()
        if existente:
            erro = "Nome de usuário já está em uso."
            return render_template("cadastro.html", erro=erro)

        senha_hash = generate_password_hash(senha)
        novo = Perfil(nome=nome, avatar=avatar_inicial, canal="geral", senha=senha_hash, bio="Olá! Sou nova por aqui.", status="Online")
        
        try:
            db.session.add(novo)
            db.session.commit()
            
            session["autenticado"] = True
            session["usuario"] = nome
            return redirect(url_for("mostrar_perfis")) 
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao cadastrar usuário: {e}")
            return render_template("cadastro.html", erro="Erro interno no servidor ao cadastrar.")

    return render_template("cadastro.html", canais=LISTA_CANAIS)


@app.route("/perfis")
def mostrar_perfis():
    if not session.get("autenticado"):
        return redirect(url_for("login"))
    
    usuario_atual = session.get("usuario")
    perfis = Perfil.query.filter(Perfil.nome != usuario_atual).all()
    
    return render_template("perfis.html", 
                           perfis=perfis, 
                           usuario_atual=usuario_atual,
                           canais=LISTA_CANAIS)

@app.route("/canal/<nome_canal>")
def canal(nome_canal):
    if not session.get("autenticado"):
        return redirect(url_for("login"))
        
    if nome_canal not in LISTA_CANAIS:
        return redirect(url_for("mostrar_perfis"))


    room_name = nome_canal
    
    
    perfil = Perfil.query.filter_by(nome=session.get("usuario")).first()
    avatar = perfil.avatar if perfil else "❓"

    return render_template("chat.html", 
                           canal_nome=nome_canal, 
                           room_id=room_name,
                           canais=LISTA_CANAIS,
                           usuario_avatar=avatar)

@app.route("/dm/<nome_alvo>")
def dm(nome_alvo):
    if not session.get("autenticado"):
        return redirect(url_for("login"))
        
    usuario_atual = session.get("usuario")
    

    alvo = Perfil.query.filter_by(nome=nome_alvo).first()
    if not alvo:
        return redirect(url_for("mostrar_perfis"))

    
    room_name = get_dm_room_name(usuario_atual, nome_alvo)

    perfil = Perfil.query.filter_by(nome=usuario_atual).first()
    avatar = perfil.avatar if perfil else "❓"
    
    return render_template("chat.html", 
                           canal_nome=f"DM com {nome_alvo}", 
                           room_id=room_name,
                           canais=LISTA_CANAIS,
                           usuario_avatar=avatar)


@app.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    if not session.get("autenticado"):
        return redirect(url_for("login"))

    nome = session.get("usuario")
    perfil = Perfil.query.filter_by(nome=nome).first()

    if not perfil:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        acao = request.form.get("acao")
        
        if acao == "excluir":
        
            db.session.delete(perfil)
            db.session.commit()
            session.clear()
            return redirect(url_for("login"))
        
        elif acao == "atualizar":
        
            perfil.bio = request.form.get("bio")
            perfil.status = request.form.get("status")

            file = request.files.get("foto")
            if file and allowed_file(file.filename):
        
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])
                    
                filename = secure_filename(file.filename)
                
                path = os.path.join(app.config['UPLOAD_FOLDER'], f"{perfil.id}_{filename}")
                file.save(path)
                perfil.foto = f"/static/uploads/{perfil.id}_{filename}"
            
            db.session.commit()
            return redirect(url_for("configuracoes"))

    return render_template("configuracoes.html", perfil=perfil)




@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        senha = request.form.get("senha")
        if senha == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("painel"))
        else:
            return render_template("admin_login.html", erro="Senha incorreta.")
    return render_template("admin_login.html")

@app.route("/painel")
def painel():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    
    canal_filtro = request.args.get("canal")
    
    
    if canal_filtro and canal_filtro != 'todos':
        perfis = Perfil.query.filter_by(canal=canal_filtro).all()
    else:
        perfis = Perfil.query.all()
    
    
    canais_db = db.session.query(Perfil.canal).distinct().all()
    canais_listados = list(set([c[0] for c in canais_db] + LISTA_CANAIS))

    denuncias_simuladas = [
        {'id': 1, 'usuario_reportado': 'JoanaTeste', 'motivo': 'Discurso de Ódio', 'status': 'Pendente'},
        {'id': 2, 'usuario_reportado': 'UsuarioDM', 'motivo': 'Assédio em DM', 'status': 'Pendente'},
    ]

    return render_template("painel.html", 
                           perfis=perfis, 
                           canais_listados=canais_listados, 
                           canal_selecionado=canal_filtro,
                           denuncias=denuncias_simuladas)

@app.route("/logout-admin")
def logout_admin():
    session.pop("admin", None)
    return redirect(url_for("admin"))

@app.route("/excluir/<int:id>")
def excluir(id):
    if not session.get("admin"):
        return redirect(url_for("admin"))
    perfil = Perfil.query.get(id)
    if perfil:
        db.session.delete(perfil)
        db.session.commit()
    return redirect(url_for("painel"))


@socketio.on('join')
def on_join(data):
    
    username = data['username']
    room = data['room']
    join_room(room)
    send({'msg': f'✨ {username} entrou na sala!', 'type': 'system'}, room=room)
    print(f"{username} entrou na sala: {room}")

@socketio.on('message')
def handle_message(data):
    
    room = data['room']
    username = data['username']
    message = data['msg']
    send({'msg': message, 'username': username, 'type': 'user'}, room=room)
    print(f"[{room}] {username}: {message}")

@socketio.on('signal')
def handle_signal(data):
    
    room = data['room']
    target_user = data['target']
    sender_user = data['sender']
    

    socketio.emit('signal', data, room=room, skip_sid=request.sid)
    print(f"Sinal WebRTC enviado de {sender_user} para {target_user} na sala {room}")



if __name__ == '__main__':
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        

    with app.app_context():
        db.create_all()
    
    
    port = int(os.environ.get("PORT", 10000))
    
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True) 


