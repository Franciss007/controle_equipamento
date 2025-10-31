import psycopg2
import psycopg2.extras

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

# 🔹 Consulta geral (SELECT)
def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    conn = None
    cur = None
    try:
        conn = conectar()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        if commit:
            conn.commit()
            return True
        if fetchone:
            return cur.fetchone()
        if fetchall:
            return cur.fetchall()
        return None
    except Exception as e:
        print(f"ERRO QUERY: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# 🔹 Execução de comandos (INSERT, UPDATE, DELETE)
def executar_sql(sql, params=None):
    conn = None
    cur = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        conn.commit()
        return True
    except Exception as e:
        print(f"[ERRO EXECUTAR_SQL]: {e}")
        conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()