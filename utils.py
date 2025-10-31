import string
import random
import uuid

def gerar_senha(tamanho=4):
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return ''.join(random.choice(chars) for _ in range(tamanho))

def gerar_id(tipo):
    prefixo = tipo[:3].upper() if tipo else "SOL"
    numeros = str(random.randint(1000, 9999))
    return prefixo + numeros
