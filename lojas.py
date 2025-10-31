from db import query

def listar_lojas_db():
    """
    Retorna a lista de lojas cadastradas no banco de dados.
    """
    sql = "SELECT codigo, nome FROM lojas ORDER BY nome"
    return query(sql, fetchall=True) or []
