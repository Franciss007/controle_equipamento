from flask import render_template, request, redirect, url_for, flash, session, send_from_directory
from datetime import datetime
import uuid
from collections import defaultdict
from config import UPLOADS_DIR
from auth import login_required, roles_required
from usuarios import listar_usuarios_db, buscar_usuario, adicionar_usuario_db, resetar_senha_usuario, atualizar_filial_usuario, atualizar_senha_usuario
from equipamentos import listar_equipamentos_db, inserir_equipamento_db, inativar_equipamento_db, buscar_equipamento_por_id
from solicitacoes import adicionar_configuracoes_solicitacao,listar_solicitacoes_db, inserir_solicitacao_db, buscar_solicitacao_por_id, atualizar_status_solicitacao_db, adicionar_anexo_solicitacao, listar_anexos_solicitacao
from utils import gerar_id
from db import query, executar_sql
from email_service import enviar_email_solicitacao_aberta
from email_service import enviar_email_para_aprovador
from lojas import listar_lojas_db
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import os

def register_routes(app):

    @app.route("/usuarios", methods=["GET", "POST"])
    @roles_required("admin")
    def usuarios():
        lojas = listar_lojas_db()
        usuarios = listar_usuarios_db()
        email = request.form.get("email", "").strip()
        
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()
            filial = request.form.get("filial", "").strip() or None

            if not username or not role or not email:
                flash("Preencha ao menos o nome de usuário, o email e a função.", "erro")
                return render_template("usuarios.html", lojas=lojas, usuarios=usuarios)

            if buscar_usuario(username):
                flash(f"Usuário '{username}' já existe!", "erro")
                return render_template("usuarios.html", lojas=lojas, usuarios=usuarios)

            senha_inicial = "123456"
            hash_senha = generate_password_hash(senha_inicial)
            adicionar_usuario_db(username, email, hash_senha, role, filial, must_change_password=True)
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
    @roles_required("filial","admin","aprovador")
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

            # Definir responsável de forma unificada
            if s['status'] == "Aberta":
                s['responsavel_nome'] = s.get('criada_por')
            elif s['status'] == "Em análise":
                s['responsavel_nome'] = s.get('responsavel_analise')
            elif s['status'] in ["Aprovada", "Reprovada"]:
                if s.get('aprovador'):
                    # Buscar nome completo do usuário aprovador
                    user = query("SELECT username FROM usuarios WHERE username = %s", (s['aprovador'],), fetchone=True)
                    s['responsavel_nome'] = user['username'] if user else s['aprovador']
                else:
                    s['responsavel_nome'] = None
            else:
                s['responsavel_nome'] = None

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

    @app.route("/inativar_equipamento/<equipamento_id>", methods=["GET", "POST"])
    def inativar_equipamento(equipamento_id):
        if request.method == "POST":
            motivo = request.form.get("motivo")
            inativar_equipamento_db(equipamento_id, motivo)
            flash("Equipamento inativado com sucesso.", "sucesso")
            return redirect(url_for("equipamentos_listar"))
        
        equipamento = buscar_equipamento_por_id(equipamento_id)
        return render_template("confirmar_inativacao.html", equipamento=equipamento)


    # ----------------- Atualizar status -----------------
    @app.route("/solicitacoes/atualizar_status/<id>", methods=["POST"])
    @roles_required("admin", "aprovador")
    def atualizar_status(id):
        novo_status = request.form.get("novo_status", "").strip()
        usuario_acao = session.get("username")  # pega quem está logado
        aprovador_form = request.form.get("aprovador")  # usado se status == "Em análise"

        # Busca solicitação
        solicitacao = buscar_solicitacao_por_id(id)
        if not solicitacao:
            flash("Solicitação não encontrada.", "danger")
            return redirect(url_for("dashboard"))
        
        if novo_status == "Em análise":
            if not aprovador_form:
                # renderiza seleção de aprovador
                usuarios = listar_usuarios_db()
                aprovadores = [u for u in usuarios if u.get("role") == "aprovador"]
                return render_template("selecionar_aprovador.html", aprovadores=aprovadores, solicitacao=solicitacao)
            atualizar_status_solicitacao_db(id, novo_status, usuario=aprovador_form)
            # Enviar email para o aprovador
            usuario_aprovador = buscar_usuario(aprovador_form)
            if usuario_aprovador and usuario_aprovador.get("email"):
                enviar_email_para_aprovador(usuario_aprovador["email"], id)
            flash(f"Solicitação enviada para análise ({aprovador_form}).", "info")
            return redirect(url_for("dashboard"))

        # 🔹 Caso Aprovada ou Reprovada
        elif novo_status in ["Aprovada", "Reprovada"]:
            atualizar_status_solicitacao_db(id, novo_status, usuario=usuario_acao)
            flash(f"Solicitação {novo_status.lower()} com sucesso!", "success")

        # 🔹 Outros status
        else:
            atualizar_status_solicitacao_db(id, novo_status)

        # 🔹 Envio de email ao solicitante
        email_solicitante = solicitacao.get("email_solicitante")
        if email_solicitante:
            assunto = f"Solicitação #{id} Atualizada"
            mensagem = f"O status da solicitação #{id} foi alterado para {novo_status} por {usuario_acao}."
            try:
                enviar_email(email_solicitante, assunto, mensagem)
            except Exception as e:
                print(f"Erro ao enviar email: {e}")

        return redirect(url_for("dashboard"))

    @app.route("/solicitacoes/ver/<id>")
    @login_required
    def ver_descricao(id):
        solic = buscar_solicitacao_por_id(id)
        if not solic:
            flash("Solicitação não encontrada.", "erro")
            return redirect(url_for("dashboard"))

        anexos = listar_anexos_solicitacao(id)
        return render_template('ver_descricao.html', solicitacao=solic, anexos=anexos)
    
    @app.route("/solicitacoes/<id>")
    @login_required
    def ver_descricao_filial(id):
        solic = buscar_solicitacao_por_id(id)
        if not solic:
            flash("Solicitação não encontrada.", "erro")
            return redirect(url_for("dashboard"))

        anexos = listar_anexos_solicitacao(id)
        return render_template('ver_minha_solicitacao.html', solicitacao=solic, anexos=anexos)

    # ----------------- Inicialização do app -----------------
    @app.errorhandler(403)
    def proibido(e):
        return render_template("403.html"), 403

