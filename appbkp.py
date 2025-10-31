import os
import string
import random
import uuid
import psycopg2
import psycopg2.extras
from collections import defaultdict
from datetime import datetime
from functools import wraps
from flask import send_from_directory, Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.utils import secure_filename
from flask import send_file, abort
from werkzeug.security import check_password_hash, generate_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "supersecret-change-me")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ----------------- Conexão com o banco -----------------
def conectar():
    conn = psycopg2.connect(
        host="localhost", 
        user="postgres",
        password="020313",
        database="postgres",
        port=5432
    )
    
    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_schema();")
    print("Conectado em:", cur.fetchone())
    cur.close()
    return conn

def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    conn = None
    cur = None
    try:
        conn = conectar()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        if commit:
            conn.commit()
            return None
        if fetchone:
            return cur.fetchone()
        if fetchall:
            return cur.fetchall()
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def gerar_senha(tamanho=4):
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return ''.join(random.choice(chars) for _ in range(tamanho))

def gerar_id(tipo):
    prefixo = tipo[:3].upper() if tipo else "SOL"
    numeros = str(random.randint(1000, 9999))
    return prefixo + numeros

def inicializar_admin_db():
    row = query("SELECT COUNT(*) as cnt FROM usuarios", fetchone=True)
    if row is None or row.get("cnt", 0) == 0:
        senha_plain = "123456"
        hash_senha = generate_password_hash(senha_plain)
        sql = ("INSERT INTO usuarios (username, senha, role, filial, must_change_password) "
               "VALUES (%s, %s, %s, %s, %s)")
        query(sql, ("admin", hash_senha, "admin", "999", True), commit=True)
        print("Admin inicializado: user=admin senha=123456")

try:
    inicializar_admin_db()
except Exception as e:
    print("Inicialização do admin falhou (verifique as tabelas):", e)

# ----------------- Usuário -----------------
def buscar_usuario(username):
    sql = "SELECT username, senha, role, filial, must_change_password FROM usuarios WHERE username = %s"
    return query(sql, (username,), fetchone=True)

def listar_usuarios_db():
    sql = "SELECT id, username, role, filial, must_change_password FROM usuarios ORDER BY username"
    return query(sql, fetchall=True) or []

def adicionar_usuario_db(username, senha_hash, role, filial, must_change_password=True):
    sql = ("INSERT INTO usuarios (username, senha, role, filial, must_change_password) "
           "VALUES (%s, %s, %s, %s, %s)")
    query(sql, (username, senha_hash, role, filial, must_change_password), commit=True)

def atualizar_senha_usuario(username, senha_hash):
    sql = "UPDATE usuarios SET senha = %s, must_change_password = FALSE WHERE username = %s"
    query(sql, (senha_hash, username), commit=True)

def resetar_senha_usuario(username):
    senha_inicial = "123456"
    hash_senha = generate_password_hash(senha_inicial)
    sql = "UPDATE usuarios SET senha = %s, must_change_password = TRUE WHERE username = %s"
    query(sql, (hash_senha, username), commit=True)
    return senha_inicial


def listar_lojas_db():
    rows = query("SELECT codigo, nome FROM lojas ORDER BY codigo", fetchall=True)
    return rows or []

def atualizar_filial_usuario(username, nova_filial):
    sql = "UPDATE usuarios SET filial = %s WHERE username = %s"
    query(sql, (nova_filial, username), commit=True)

# ----------------- Solicitações -----------------
def inserir_solicitacao_db(solic):
    sql = ("INSERT INTO solicitacoes "
           "(id, filial, solicitante_nome, contato, tipo, setor, descricao, prioridade, status, data_abertura, criada_por) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
    params = (
        solic["id"], solic["filial"], solic["solicitante_nome"], solic["contato"],
        solic["tipo"], solic["setor"], solic["descricao"], solic["prioridade"],
        solic["status"], solic["data_abertura"], solic["criada_por"]
    )
    query(sql, params, commit=True)

def listar_solicitacoes_db():
    return query("SELECT * FROM solicitacoes ORDER BY data_abertura DESC", fetchall=True) or []

def buscar_solicitacao_por_id(id_):
    return query("SELECT * FROM solicitacoes WHERE id = %s", (id_,), fetchone=True)

def atualizar_status_solicitacao_db(id_, novo_status, usuario="sistema", patrimonio=None):
    if novo_status == "Em análise":
        sql = "UPDATE solicitacoes SET status = %s, responsavel_analise = %s WHERE id = %s"
        query(sql, (novo_status, usuario, id_), commit=True)
    elif novo_status == "Aprovada":
        sql = "UPDATE solicitacoes SET status = %s, aprovador = %s WHERE id = %s"
        query(sql, (novo_status, usuario, id_), commit=True)
    else:
        sql = "UPDATE solicitacoes SET status = %s WHERE id = %s"
        query(sql, (novo_status, id_), commit=True)

    if novo_status == "Atendida":
        solic = buscar_solicitacao_por_id(id_)
        if solic:
            lojas = listar_lojas_db()
            loja = next(
                (l for l in lojas if l["codigo"] == solic.get("filial")),
                {"codigo": solic.get("filial"), "nome": "Filial desconhecida"}
            )

            equipamento = {
                "id": str(uuid.uuid4())[:8],
                "nome": solic.get("solicitante_nome", "Equipamento sem usuário"),
                "patrimonio": patrimonio or "",
                "tipo": solic.get("tipo", ""),
                "setor": solic.get("setor", ""),
                "filial": loja["codigo"], 
                "data_abertura": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Aberta",
                "criada_por": usuario or solic.get("criada_por", "sistema")
            }
            inserir_equipamento_db(equipamento)



# ----------------- Equipamentos -----------------
def inserir_equipamento_db(eqp):
    sql = ("INSERT INTO equipamentos (id, nome, patrimonio, tipo, setor, filial, data_abertura, status, criada_por) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
    params = (eqp["id"], eqp["nome"], eqp.get("patrimonio",""), eqp.get("tipo",""),
              eqp.get("setor",""), eqp.get("filial",""), eqp["data_abertura"], eqp["status"], eqp["criada_por"])
    query(sql, params, commit=True)

def listar_equipamentos_db():
    return query("SELECT * FROM equipamentos ORDER BY data_abertura DESC", fetchall=True) or []

def remover_equipamento_db(equipamento_id):
    sql = "DELETE FROM equipamentos WHERE id = %s"
    query(sql, (equipamento_id,), commit=True)

# ----------------- Configurações e Anexos -----------------
def adicionar_configuracoes_solicitacao(id_, modelo, marca, info_tecnicas):
    sql = "UPDATE solicitacoes SET modelo = %s, marca = %s, info_tecnicas = %s WHERE id = %s"
    query(sql, (modelo, marca, info_tecnicas, id_), commit=True)

def adicionar_anexo_solicitacao(id_, nome_arquivo):
    sql = "INSERT INTO anexos (solicitacao_id, arquivo_nome) VALUES (%s, %s)"
    query(sql, (id_, nome_arquivo), commit=True)

def listar_anexos_solicitacao(id_):
    rows = query("SELECT arquivo_nome FROM anexos WHERE solicitacao_id = %s ORDER BY id", (id_,), fetchall=True) or []
    return [r.get("arquivo_nome") for r in rows]


# ----------------- Autenticação -----------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            flash("Faça login para continuar.", "erro")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "usuario" not in session:
                flash("Faça login para continuar.", "erro")
                return redirect(url_for("login", next=request.path))
            if session.get("role") not in roles:
                return abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ----------------- Rotas -----------------
@app.route("/usuarios", methods=["GET", "POST"])
@roles_required("admin")
def usuarios():
    lojas = listar_lojas_db()
    usuarios = listar_usuarios_db()
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        role = request.form.get("role", "").strip()
        filial = request.form.get("filial", "").strip() or None

        if not username or not role:
            flash("Preencha ao menos o nome de usuário e a função.", "erro")
            return render_template("usuarios.html", lojas=lojas, usuarios=usuarios)

        if buscar_usuario(username):
            flash(f"Usuário '{username}' já existe!", "erro")
            return render_template("usuarios.html", lojas=lojas, usuarios=usuarios)

        senha_inicial = "123456"
        hash_senha = generate_password_hash(senha_inicial)
        adicionar_usuario_db(username, hash_senha, role, filial, must_change_password=True)
        flash(f"Usuário '{username}' criado com sucesso! Senha: {senha_inicial}", "sucesso")
        return redirect(url_for("usuarios"))

    return render_template("usuarios.html", lojas=lojas, usuarios=usuarios)

@app.route("/usuarios/resetar/<username>")
@roles_required("admin")
def usuarios_resetar(username):
    nova = resetar_senha_usuario(username)
    flash(f"Senha do usuário '{username}' foi resetada para: {nova}", "sucesso")
    return redirect(url_for("usuarios"))

@app.route("/usuarios/trocar_filial/<username>", methods=["POST"])
@roles_required("admin")
def usuarios_trocar_filial(username):
    nova_filial = request.form.get("nova_filial")
    if not nova_filial:
        flash("Selecione uma filial válida.", "erro")
    else:
        atualizar_filial_usuario(username, nova_filial)
        flash(f"Filial do usuário '{username}' atualizada para {nova_filial}.", "sucesso")
    return redirect(url_for("usuarios"))



@app.route("/")
def index():
    if session.get("role") == "admin" or session.get("role") == "aprovador":
        return redirect(url_for("dashboard"))
    elif session.get("role") == "filial":
        return redirect(url_for("minhas_solicitacoes"))
    return render_template("home.html")

@app.route("/minhas-solicitacoes")
@roles_required("filial")
def minhas_solicitacoes():
    todas = listar_solicitacoes_db()  # busca todas do banco
    minha_filial = session.get("filial")
    minhas = [s for s in todas if s.get("filial") == minha_filial] #filtra pela filial do usuário
    return render_template("minhas_solicitacoes.html", solicitacoes=minhas)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")
        u = buscar_usuario(username)
        if not u or not check_password_hash(u.get("senha", ""), senha):
            flash("Usuário ou senha inválidos.", "erro")
            return render_template("login.html")
        session["usuario"] = u["username"]
        session["role"] = u["role"]
        session["filial"] = u.get("filial")
        if u.get("must_change_password"):
            flash("Você precisa alterar sua senha no primeiro login.", "info")
            return redirect(url_for("trocar_senha"))
        prox = request.args.get("next")
        return redirect(prox or url_for("index"))
    return render_template("login.html")

@app.route("/trocar_senha", methods=["GET", "POST"])
def trocar_senha():
    username = session.get("usuario")
    if not username:
        return redirect(url_for("login"))
    if request.method == "POST":
        nova_senha = request.form.get("new_password")
        confirmar_senha = request.form.get("confirm_password")
        if nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "erro")
        else:
            hash_senha = generate_password_hash(nova_senha)
            atualizar_senha_usuario(username, hash_senha)
            flash("Senha alterada com sucesso!", "sucesso")
            return redirect(url_for("index"))
    return render_template("trocar_senha.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sessão.", "sucesso")
    return redirect(url_for("index"))

# ----------------- Solicitações sem login -----------------
@app.route("/solicitacao", methods=["GET", "POST"])
def solicitacao():
    lojas = listar_lojas_db()
    if request.method == "POST":
        filial = request.form.get("filial", "").strip()
        if session.get("role") == "filial":
            filial = session.get("filial") or filial
        tipo = request.form.get("tipo", "").strip()
        nova = {
            "id": gerar_id(tipo),
            "filial": filial,
            "solicitante_nome": request.form.get("solicitante_nome", "").strip(),
            "contato": request.form.get("contato", "").strip(),
            "tipo": tipo,
            "setor": request.form.get("setor", "").strip(),
            "descricao": request.form.get("descricao", "").strip(),
            "prioridade": request.form.get("prioridade", "Média"),
            "status": "Aberta",
            "data_abertura": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "criada_por": session.get("usuario") or "publico"
        }
        if not nova["descricao"]:
            flash("Preencha ao menos a descrição.", "erro")
            return render_template("solicitacao.html", lojas=lojas)
        inserir_solicitacao_db(nova)

        try:
            enviar_email_solicitacao_aberta(nova)
        except Exception as e:
            print("Falha no envio de e-mail:", e)

        flash(f"Solicitação registrada com sucesso! ID: {nova['id']}", "sucesso")
        return redirect(url_for("solicitacao"))
    return render_template("solicitacao.html", lojas=lojas)

# ----------------- Enviar email -----------------
def enviar_email_solicitacao_aberta(solicitacao):
    filial = listar_lojas_db()
    nome_filial = next((l['nome'] for l in filial if l['codigo'] == solicitacao['filial']), solicitacao['filial'])
    remetente = "lucas.franciss@fribal.com.br"
    destinatario = "lucas.franciss@fribal.com.br"
    assunto = f"Nova solicitação aberta: {solicitacao['id']}"
    corpo = (
        f"Uma nova solicitação foi aberta.\n\n"
        f"Filial: {nome_filial}\n"
        f"Solicitante: {solicitacao['solicitante_nome']}\n"
        f"Tipo: {solicitacao['tipo']}\n"
        f"Setor: {solicitacao['setor']}\n"
        f"Descrição: {solicitacao['descricao']}\n"
        f"Data de abertura: {solicitacao['data_abertura']}\n"
        f"Criada por: {solicitacao['criada_por']}\n"
    )

    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain'))

    server = smtplib.SMTP('mail.fribal.com.br', 587)
    server.login("lucas.franciss@fribal.com.br", "lucas.franciss") #alterar dominio e remetente
    server.send_message(msg)
    server.quit()
    print("E-mail enviado para TI com sucesso!")

# ----------------- Rotas administrativas -----------------
@app.route("/dashboard")
@roles_required("admin","aprovador")
def dashboard():
    dados = listar_solicitacoes_db()
    totais = {
        "total": len(dados),
        "abertas": sum(1 for s in dados if s.get("status") == "Aberta"),
        "analise": sum(1 for s in dados if s.get("status") == "Em análise"),
        "aprovadas": sum(1 for s in dados if s.get("status") == "Aprovada"),
        "reprovadas": sum(1 for s in dados if s.get("status") == "Reprovada"),
        "atendidas": sum(1 for s in dados if s.get("status") == "Atendida"),
    }
    ultimas = sorted(dados, key=lambda x: x.get("data_abertura", ""), reverse=True)[:20]
    for s in ultimas:
        s['anexos'] = listar_anexos_solicitacao(s['id'])

    return render_template("dashboard.html", totais=totais, ultimas=ultimas)


@app.route("/solicitacoes/configuracoes/<id>", methods=["POST"])
@roles_required("admin")
def configuracoes_equipamento(id):
    modelo = request.form.get("modelo", "").strip()
    marca = request.form.get("marca", "").strip()
    info_tecnicas = request.form.get("info_tecnicas", "").strip()
    
    adicionar_configuracoes_solicitacao(id, modelo, marca, info_tecnicas)
    flash("Configurações atualizadas com sucesso!", "sucesso")
    return redirect(url_for("dashboard"))


@app.route("/solicitacoes/anexar/<id>", methods=["POST"])
@roles_required("admin")
def anexar_arquivos(id):
    arquivo = request.files.get("arquivo")
    if arquivo and arquivo.filename:
        original = arquivo.filename
        seguro = secure_filename(original)
        nome_arquivo = f"{id}_{seguro}"
        caminho = os.path.join(UPLOADS_DIR, nome_arquivo)
        try:
            arquivo.save(caminho)
            adicionar_anexo_solicitacao(id, nome_arquivo)
            flash("Arquivo anexado com sucesso!", "sucesso")
        except Exception as e:
            print("Erro ao salvar arquivo:", e)
            flash("Falha ao salvar arquivo no servidor.", "erro")
    else:
        flash("Nenhum arquivo selecionado.", "erro")
    return redirect(url_for("dashboard"))

@app.route("/uploads/<path:nome_arquivo>")
@roles_required("admin")
def ver_anexo(nome_arquivo):
    return send_from_directory(UPLOADS_DIR, nome_arquivo)


@app.route("/relatorios/<tipo>")
@roles_required("admin")
def relatorios(tipo):
    solicitacoes = listar_solicitacoes_db()
    if tipo == "analitico":
        return render_template("relatorio_analitico.html", solicitacoes=solicitacoes)
    elif tipo == "sintetico":
        lojas = listar_lojas_db()
        lojas_dict = {loja.get("codigo"): loja.get("nome") for loja in lojas}
        resumo = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        for s in solicitacoes:
            cod_filial = s.get("filial", "Sem Filial")
            nome_filial = lojas_dict.get(cod_filial, "Sem Nome")
            filial_exibicao = f"{cod_filial} - {nome_filial}"
            tipo_ = s.get("tipo", "Sem Tipo")
            status = s.get("status", "Sem Status")
            resumo[filial_exibicao][tipo_][status] += 1
        return render_template("relatorio_sintetico.html", resumo=resumo)
    else:
        return "Tipo de relatório inválido", 404

# ----------------- Equipamentos -----------------
@app.route("/equipamentos/adicionar", methods=["GET", "POST"])
@roles_required("admin")
def equipamentos_adicionar():
    lojas = listar_lojas_db()
    if request.method == "POST":
        novo = {
            "id": str(uuid.uuid4())[:8],
            "nome": request.form.get("nome", "").strip(),
            "patrimonio": request.form.get("patrimonio", "").strip(),
            "tipo": request.form.get("tipo", "").strip(),
            "setor": request.form.get("setor", "").strip(),
            "filial": request.form.get("filial", "").strip(),
            "data_abertura": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Aberta",
            "criada_por": session.get("usuario") or "publico"
        }
        inserir_equipamento_db(novo)
        flash("Equipamento adicionado com sucesso!", "sucesso")
        return redirect(url_for("equipamentos_adicionar"))
    return render_template("equipamentos_adicionar.html", lojas=lojas)

@app.route("/equipamentos/listar")
@roles_required("admin")
def equipamentos_listar():
    equipamentos = listar_equipamentos_db()
    return render_template("listagem.html", equipamentos=equipamentos)

@app.route("/equipamentos/remover/<equipamento_id>")
@roles_required("admin")
def equipamentos_remover(equipamento_id):
    remover_equipamento_db(equipamento_id)
    flash("Equipamento removido com sucesso.", "sucesso")
    return redirect(url_for("equipamentos_listar"))

# ----------------- Atualizar status -----------------
@app.route("/solicitacoes/atualizar_status/<id>", methods=["POST", "GET"])
@roles_required("admin","aprovador")
def atualizar_status(id):
    if request.method == "POST":
        novo_status = request.form.get("novo_status")
        if novo_status == "Atendida":
            patrimonio = request.form.get("patrimonio", "").strip()
            if not patrimonio:
                solic = buscar_solicitacao_por_id(id)
                return render_template("inserir_patrimonio.html", solicitacao=solic)
            atualizar_status_solicitacao_db(id, novo_status, usuario=session.get("usuario"), patrimonio=patrimonio)
            flash("Solicitação atendida e equipamento registrado com sucesso!", "sucesso")
            return redirect(url_for("dashboard"))
        if novo_status:
            atualizar_status_solicitacao_db(id, novo_status, usuario=session.get("usuario"))
            flash("Status atualizado com sucesso!", "sucesso")
        else:
            flash("Status inválido.", "erro")
        return redirect(url_for("dashboard"))

@app.route("/solicitacoes/ver/<id>")
@login_required
def ver_descricao(id):
    solic = buscar_solicitacao_por_id(id)
    if not solic:
        flash("Solicitação não encontrada.", "erro")
        return redirect(url_for("dashboard"))

    anexos = listar_anexos_solicitacao(id)
    return render_template("ver_descricao.html", solicitacao=solic, anexos=anexos)

# ----------------- Inicialização do app -----------------
@app.errorhandler(403)
def proibido(e):
    return render_template("403.html"), 403

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
