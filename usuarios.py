from werkzeug.security import generate_password_hash
from db import query

def listar_usuarios_db():
    return query("SELECT id, username, role, filial, must_change_password FROM usuarios ORDER BY username", fetchall=True) or []

def buscar_usuario(username):
    return query("SELECT username, email, senha, role, filial, must_change_password FROM usuarios WHERE username = %s", (username,), fetchone=True)

def adicionar_usuario_db(username, email, senha_hash, role, filial, must_change_password=True):
    sql = ("INSERT INTO usuarios (username,email, senha, role, filial, must_change_password) "
           "VALUES (%s, %s, %s, %s, %s, %s)")
    query(sql, (username, email,senha_hash, role, filial, must_change_password), commit=True)

def atualizar_senha_usuario(username, senha_hash):
    query("UPDATE usuarios SET senha = %s, must_change_password = FALSE WHERE username = %s", (senha_hash, username), commit=True)

def resetar_senha_usuario(username):
    senha_inicial = "123456"
    hash_senha = generate_password_hash(senha_inicial)
    query("UPDATE usuarios SET senha = %s, must_change_password = TRUE WHERE username = %s", (hash_senha, username), commit=True)
    return senha_inicial

def atualizar_filial_usuario(username, nova_filial):
    query("UPDATE usuarios SET filial = %s WHERE username = %s", (nova_filial, username), commit=True)
