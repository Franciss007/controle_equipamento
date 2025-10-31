from db import query
from datetime import datetime

def inserir_equipamento_db(eqp):
    sql = ("INSERT INTO equipamentos (id, nome, patrimonio, tipo, setor, filial, data_abertura, status, criada_por) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
    params = (eqp["id"], eqp["nome"], eqp.get("patrimonio",""), eqp.get("tipo",""),
              eqp.get("setor",""), eqp.get("filial",""), eqp["data_abertura"], eqp["status"], eqp["criada_por"])
    query(sql, params, commit=True)


def listar_equipamentos_db():
    return query("SELECT * FROM equipamentos WHERE ativo = TRUE ORDER BY data_abertura DESC", fetchall=True) or []

def buscar_equipamento_por_id(equipamento_id):
    result = query("SELECT * FROM equipamentos WHERE id = %s", (equipamento_id,), fetchone=True)
    return result

# def remover_equipamento_db(equipamento_id): ANTIGA FUNÇÃO DE REMOVER EQUIPAMENTOS
    query("DELETE FROM equipamentos WHERE id = %s", (equipamento_id,), commit=True) #

def inativar_equipamento_db(equipamento_id, motivo):
    query(
        """
        UPDATE equipamentos
        SET ativo = FALSE,
            motivo_inativacao = %s,
            data_inativacao = %s
        WHERE id = %s
        """,
        (motivo,datetime.now(), equipamento_id), commit=True
    )
