import uuid
from db import query, executar_sql
from equipamentos import inserir_equipamento_db
from datetime import datetime

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

def atualizar_status_solicitacao_db(id_, novo_status, usuario="sistema", patrimonio=None, aprovador=None):
    if novo_status == "Em análise":
        query(
            "UPDATE solicitacoes SET status = %s, responsavel_analise = %s WHERE id = %s",
            (novo_status, usuario, id_),
            commit=True
        )
    elif novo_status == "Aprovada":
        query(
            "UPDATE solicitacoes SET status = %s, aprovador = %s WHERE id = %s",
            (novo_status, aprovador or usuario, id_),
            commit=True
        )
    else:
        query(
            "UPDATE solicitacoes SET status = %s WHERE id = %s",
            (novo_status, id_),
            commit=True
        )
    if novo_status == "Atendida":
        solic = buscar_solicitacao_por_id(id_)
        if solic:
            equipamento = {
                "id": solic.get("id",""),
                "nome": solic.get("solicitante_nome", "Equipamento sem usuário"),
                "patrimonio": patrimonio or "",
                "tipo": solic.get("tipo", ""),
                "setor": solic.get("setor", ""),
                "filial": solic.get("filial", ""),
                "data_abertura": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Aberta",
                "criada_por": usuario or solic.get("criada_por", "sistema")
            }
            inserir_equipamento_db(equipamento)

def adicionar_anexo_solicitacao(id_, nome_arquivo):
    query("INSERT INTO anexos (solicitacao_id, arquivo_nome) VALUES (%s, %s)", (id_, nome_arquivo), commit=True)

def listar_anexos_solicitacao(id_):
    rows = query("SELECT arquivo_nome FROM anexos WHERE solicitacao_id = %s ORDER BY id", (id_,), fetchall=True) or []
    return [r.get("arquivo_nome") for r in rows]


def adicionar_configuracoes_solicitacao(id_, modelo, marca, info_tecnicas):
    sql = "UPDATE solicitacoes SET modelo = %s, marca = %s, info_tecnicas = %s WHERE id = %s"
    query(sql, (modelo, marca, info_tecnicas, id_), commit=True)
