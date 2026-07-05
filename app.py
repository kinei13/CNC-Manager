from flask import Flask, render_template, request, redirect
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# =========================
# DOSYA AYARLARI
# =========================

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def get_connection():
    conn = sqlite3.connect("database/cnc.db")
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# DASHBOARD
# =========================

@app.route("/")
def home():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM machines")
    machine_count = cursor.fetchone()[0]

    conn.close()

    return render_template("index.html", machine_count=machine_count)


# =========================
# MAKİNELER
# =========================

@app.route("/machines")
def machines():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM machines ORDER BY id")
    machines = cursor.fetchall()

    conn.close()

    return render_template("machines.html", machines=machines)


# =========================
# MAKİNE DETAYI
# =========================

@app.route("/machine/<int:id>")
def machine_detail(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM machines WHERE id=?", (id,))
    machine = cursor.fetchone()

    cursor.execute("SELECT * FROM jobs WHERE machine_id=?", (id,))
    jobs = cursor.fetchall()

    conn.close()

    return render_template(
        "machine_detail.html",
        machine=machine,
        jobs=jobs
    )


# =========================
# MAKİNE EKLE
# =========================

@app.route("/add-machine", methods=["GET", "POST"])
def add_machine():

    if request.method == "POST":

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO machines
            (name, type, brand, model, control_unit, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form["type"],
            request.form["brand"],
            request.form["model"],
            request.form["control_unit"],
            "Aktif"
        ))

        conn.commit()
        conn.close()

        return redirect("/machines")

    return render_template("add_machine.html")


# =========================
# YENİ İŞ EKLE
# =========================

@app.route("/machine/<int:machine_id>/add-job", methods=["GET", "POST"])
def add_job(machine_id):

    if request.method == "POST":

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO jobs
            (
                machine_id,
                job_name,
                material,
                quantity,
                production_date,
                delivery_date,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            machine_id,
            request.form["job_name"],
            request.form["material"],
            request.form["quantity"],
            request.form["production_date"],
            request.form["delivery_date"],
            "Devam Ediyor",
            request.form["notes"]
        ))

        conn.commit()
        conn.close()

        return redirect(f"/machine/{machine_id}")

    return render_template(
        "add_job.html",
        machine_id=machine_id
    )


# =========================
# İŞ DETAYI
# =========================

@app.route("/job/<int:id>")
def job_detail(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs WHERE id=?", (id,))
    job = cursor.fetchone()

    conn.close()

    return render_template(
        "job_detail.html",
        job=job
    )


# =========================
# PROGRAMI BAŞLAT
# =========================

if __name__ == "__main__":
    app.run(debug=True)