
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "troque-esta-chave")

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                    id BIGSERIAL PRIMARY KEY,
                    numero INTEGER NOT NULL UNIQUE CHECK (numero BETWEEN 1 AND 1000),
                    nome TEXT NOT NULL,
                    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()

@app.before_request
def startup():
    # Inicializa de forma idempotente.
    if DATABASE_URL:
        try:
            init_db()
        except Exception:
            pass

@app.get("/")
def index():
    with db() as conn:
        reservas = conn.execute("SELECT numero FROM reservas ORDER BY numero").fetchall()
    ocupados = {r["numero"] for r in reservas}
    return render_template("index.html", ocupados=ocupados)

@app.post("/reservar")
def reservar():
    data = request.get_json(silent=True) or request.form
    try:
        numero = int(data.get("numero", 0))
    except (TypeError, ValueError):
        return jsonify(ok=False, mensagem="Número inválido."), 400

    nome = str(data.get("nome", "")).strip()
    if not 1 <= numero <= 1000:
        return jsonify(ok=False, mensagem="Escolha um número entre 1 e 1000."), 400
    if len(nome) < 2 or len(nome) > 120:
        return jsonify(ok=False, mensagem="Digite um nome válido."), 400

    # UNIQUE(numero) + INSERT atômico garante que só o primeiro vencedor fique com o número.
    with db() as conn:
        try:
            row = conn.execute(
                "INSERT INTO reservas (numero, nome) VALUES (%s, %s) "
                "ON CONFLICT (numero) DO NOTHING "
                "RETURNING numero, nome, criado_em",
                (numero, nome)
            ).fetchone()
            if row:
                conn.commit()
                return jsonify(ok=True, mensagem=f"Número {numero:04d} reservado com sucesso!")
            conn.rollback()
            atual = conn.execute(
                "SELECT nome, criado_em FROM reservas WHERE numero=%s", (numero,)
            ).fetchone()
            return jsonify(
                ok=False,
                mensagem="Esse número já foi reservado.",
                reservado_por=atual["nome"] if atual else None
            ), 409
        except Exception:
            conn.rollback()
            raise

@app.get("/admin")
def admin():
    if not session.get("admin"):
        return render_template("admin_login.html")
    with db() as conn:
        rows = conn.execute("""
            SELECT numero, nome,
                   to_char(criado_em AT TIME ZONE 'America/Cuiaba',
                           'DD/MM/YYYY HH24:MI:SS') AS horario
            FROM reservas
            ORDER BY criado_em ASC
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM reservas").fetchone()["c"]
    return render_template("admin.html", rows=rows, total=total)

@app.post("/admin/login")
def admin_login():
    senha = request.form.get("senha", "")
    if senha == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect(url_for("admin"))
    return render_template("admin_login.html", erro="Senha incorreta."), 401

@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin"))

@app.get("/api/reservas")
def api_reservas():
    if not session.get("admin"):
        return jsonify(ok=False), 401
    with db() as conn:
        rows = conn.execute("""
            SELECT numero, nome,
                   to_char(criado_em AT TIME ZONE 'America/Cuiaba',
                           'DD/MM/YYYY HH24:MI:SS') AS horario
            FROM reservas ORDER BY criado_em ASC
        """).fetchall()
    return jsonify(ok=True, reservas=rows)

@app.get("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    init_db()
    app.run(host="0.0.0.0", port=port)
