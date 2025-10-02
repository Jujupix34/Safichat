from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, send
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    foto = db.Column(db.String(200), nullable=True)
    senha = db.Column(db.String(200), nullable=False)

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
    
    canal = request.args.get("canal")
    if canal:
        perfis = Perfil.query.filter_by(canal=canal).all()
    else:
        perfis = Perfil.query.all()
    
    canais = db.session.query(Perfil.canal).distinct().all()
    return render_template("painel.html", perfis=perfis, canais=canais, canal_selecionado=canal)

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

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")
        canal = "geral"

        if not nome or not senha:
            erro = "Preencha todos os campos."
            return render_template("cadastro.html", erro=erro)

        existente = Perfil.query.filter_by(nome=nome, canal=canal).first()
        if existente:
            erro = "Nome já está em uso."
            return render_template("cadastro.html", erro=erro)

        senha_hash = generate_password_hash(senha)
        novo = Perfil(nome=nome, avatar="🙂", canal=canal, senha=senha_hash)
        db.session.add(novo)
        db.session.commit()

        session["autenticado"] = True
        session["usuario"] = nome
        return redirect(url_for("canal", nome="geral"))

    return render_template("cadastro.html")

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")

        perfil = Perfil.query.filter_by(nome=nome, canal="geral").first()
        if perfil and check_password_hash(perfil.senha, senha):
            session["autenticado"] = True
            session["usuario"] = nome
            return redirect(url_for("canal", nome="geral"))
        else:
            erro = "Nome ou senha incorretos."
            return render_template("login.html", erro=erro)
    return render_template("login.html")

@app.route("/canal/<nome>")
def canal(nome):
    if not session.get("autenticado"):
        return redirect(url_for("login"))
    return render_template("chat.html", canal=nome)

@app.route("/perfis")
def mostrar_perfis():
    perfis = Perfil.query.all()
    return render_template("perfis.html", perfis=perfis)

@app.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    if not session.get("autenticado"):
        return redirect(url_for("login"))

    nome = session.get("usuario")
    canal = "geral"
    perfil = Perfil.query.filter_by(nome=nome, canal=canal).first()

    if request.method == "POST":
        if request.form.get("acao") == "excluir":
            if perfil:
                db.session.delete(perfil)
                db.session.commit()
            session.clear()
            return redirect(url_for("login"))
        else:
            perfil.bio = request.form.get("bio")
            perfil.status = request.form.get("status")

            file = request.files.get("foto")
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                perfil.foto = f"/static/uploads/{filename}"

            db.session.commit()
        return redirect(url_for("configuracoes"))

    return render_template("configuracoes.html", perfil=perfil)

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
            novo = Perfil(nome=nome, avatar=avatar, canal=canal, senha="")  
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
            status=data['status'],
            foto=data['foto'],
            senha=""  
        )
        db.session.add(novo)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
