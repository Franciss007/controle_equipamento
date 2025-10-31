import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from lojas import listar_lojas_db

# CONFIGURAÇÕES GERAIS DE E-MAIL

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_REMETENTE = 'solicitacoes.aberta@gmail.com'    
EMAIL_SENHA = 'znlc irwh yxyl iegi'  #generica

def enviar_email(destinatario, assunto, corpo):
    """
    Envia um e-mail simples via servidor SMTP do Gmail.
    """
    msg = MIMEMultipart()
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls() 
            server.login(EMAIL_REMETENTE, EMAIL_SENHA)
            server.send_message(msg)
        print(f"✅ E-mail enviado com sucesso para {destinatario}")
    except smtplib.SMTPAuthenticationError:
        print("❌ Erro de autenticação. Verifique o e-mail e a senha de app do Gmail.")
    except smtplib.SMTPConnectError:
        print("❌ Erro de conexão com o servidor SMTP.")
    except Exception as e:
        print(f"❌ Erro inesperado ao enviar e-mail: {e}")

# FUNÇÃO: E-MAIL DE NOVA SOLICITAÇÃO ABERTA

def enviar_email_solicitacao_aberta(solicitacao):
    """
    Envia um e-mail automático para notificar sobre uma nova solicitação aberta.
    """
    filial = listar_lojas_db()
    nome_filial = next((l['nome'] for l in filial if l['codigo'] == solicitacao['filial']), solicitacao['filial'])
    
    destinatario = "solicitacoes.controle@gmail.com"
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

    enviar_email(destinatario, assunto, corpo)

# FUNÇÃO: E-MAIL PARA O APROVADOR

def enviar_email_para_aprovador(email, solicitacao_id):
    """
    Envia um e-mail ao aprovador responsável pela solicitação.
    """
    assunto = f"Nova solicitação para aprovação - ID {solicitacao_id}"
    corpo = (
        f"Você foi designado como aprovador responsável pela solicitação {solicitacao_id}.\n\n"
        f"Link para visualização da solicitação:\n"
        f"http://localhost:5000/solicitacoes/ver/{solicitacao_id}\n\n"
        f"Por favor, realize a análise o quanto antes."
    )

    enviar_email(email, assunto, corpo)
