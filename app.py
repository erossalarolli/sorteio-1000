import os
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave")

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


def init_db():
    with db() as conn:

        # Cria a tabela caso ainda não exista
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservas (
                id BIGSERIAL PRIMARY KEY,
                numero INTEGER UNIQUE NOT NULL
                    CHECK (numero BETWEEN 1 AND 1000),
                nome TEXT NOT NULL,
                criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Atualiza bancos antigos adicionando telefone
        conn.execute("""
            ALTER TABLE reservas
            ADD COLUMN IF NOT EXISTS telefone TEXT
        """)

        # Para registros antigos, coloca um valor temporário
        conn.execute("""
            UPDATE reservas
            SET telefone = 'ANTIGO-' || id
            WHERE telefone IS NULL
        """)

        # Impede o mesmo telefone de reservar mais de um número
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_reservas_telefone
            ON reservas (telefone)
        """)

        conn.commit()


@app.before_request
def ensure_db():
    try:
        init_db()
    except Exception as e:
        print("Erro ao inicializar banco:", e)


def normalizar_telefone(valor):
    return "".join(
        caractere
        for caractere in (valor or "")
        if caractere.isdigit()
    )


@app.get("/")
def index():

    with db() as conn:
        rows = conn.execute("""
            SELECT numero
            FROM reservas
            ORDER BY numero
        """).fetchall()

    ocupados = [r["numero"] for r in rows]

    return render_template(
        "index.html",
        ocupados=ocupados
    )


@app.post("/reservar")
def reservar():

    nome = (request.form.get("nome") or "").strip()

    telefone = normalizar_telefone(
        request.form.get("telefone")
    )

    numero_raw = request.form.get("numero")

    try:
        numero = int(numero_raw)
    except (TypeError, ValueError):

        flash("Número inválido.")

        return redirect(
            url_for("index")
        )

    if not nome or len(nome) < 2:

        flash("Informe seu nome.")

        return redirect(
            url_for("index")
        )

    if len(telefone) < 10 or len(telefone) > 13:

        flash("Informe um WhatsApp/telefone válido.")

        return redirect(
            url_for("index")
        )

    if not 1 <= numero <= 1000:

        flash("Número inválido.")

        return redirect(
            url_for("index")
        )

    try:

        with db() as conn:

            # Verifica se o telefone já possui número
            telefone_existente = conn.execute("""
                SELECT numero
                FROM reservas
                WHERE telefone = %s
                LIMIT 1
            """, (telefone,)).fetchone()

            if telefone_existente:

                flash(
                    f"Este WhatsApp já possui o número "
                    f"{telefone_existente['numero']:04d}."
                )

                return redirect(
                    url_for("index")
                )

            # Reserva atômica:
            # se duas pessoas tentarem o mesmo número
            # praticamente ao mesmo tempo, apenas uma ganha.
            reserva = conn.execute("""
                INSERT INTO reservas (
                    numero,
                    nome,
                    telefone
                )
                VALUES (%s, %s, %s)

                ON CONFLICT (numero)
                DO NOTHING

                RETURNING numero
            """, (
                numero,
                nome,
                telefone
            )).fetchone()

            if reserva:

                conn.commit()

                flash(
                    f"Número {numero:04d} reservado com sucesso!"
                )

            else:

                conn.rollback()

                flash(
                    "Esse número já foi reservado. "
                    "Escolha outro."
                )

    except Exception as e:

        print("ERRO AO RESERVAR:", repr(e))

        flash(
            "Não foi possível concluir a reserva. "
            "Tente novamente."
        )

    return redirect(
        url_for("index")
    )


@app.get("/admin/login")
def admin_login():

    if session.get("admin"):
        return redirect(
            url_for("admin")
        )

    return render_template(
        "admin_login.html"
    )


@app.post("/admin/login")
def admin_login_post():

    senha = request.form.get(
        "senha",
        ""
    )

    if senha == ADMIN_PASSWORD:

        session["admin"] = True

        return redirect(
            url_for("admin")
        )

    flash("Senha incorreta.")

    return redirect(
        url_for("admin_login")
    )


@app.get("/admin/logout")
def admin_logout():

    session.pop(
        "admin",
        None
    )

    return redirect(
        url_for("index")
    )


@app.get("/admin")
def admin():

    if not session.get("admin"):

        return redirect(
            url_for("admin_login")
        )

    with db() as conn:

        rows = conn.execute("""
            SELECT
                id,
                numero,
                nome,
                telefone,
                criado_em
            FROM reservas
            ORDER BY criado_em ASC, id ASC
        """).fetchall()

    timezone = ZoneInfo(
        "America/Cuiaba"
    )

    reservas = []

    for reserva in rows:

        data = reserva["criado_em"]

        if data.tzinfo is None:

            data = data.replace(
                tzinfo=ZoneInfo("UTC")
            )

        reserva["data_hora"] = (
            data
            .astimezone(timezone)
            .strftime("%d/%m/%Y %H:%M:%S")
        )

        reservas.append(
            reserva
        )

    return render_template(
        "admin.html",
        reservas=reservas
    )


@app.get("/api/reservas")
def api_reservas():

    if not session.get("admin"):

        return jsonify({
            "erro": "não autorizado"
        }), 401

    with db() as conn:

        rows = conn.execute("""
            SELECT
                id,
                numero,
                nome,
                telefone,
                criado_em
            FROM reservas
            ORDER BY criado_em ASC, id ASC
        """).fetchall()

    return jsonify(rows)


@app.get("/health")
def health():

    return "OK", 200


if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
