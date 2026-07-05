from flask import Flask, render_template, request, redirect
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

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

    cursor.execute("SELECT COUNT(*) FROM customers")
    customer_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs")
    job_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        machine_count=machine_count,
        customer_count=customer_count,
        job_count=job_count
    )


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

    return render_template(
        "machines.html",
        machines=machines
    )


# =========================
# TÜM İŞLER
# =========================

@app.route("/jobs")
def jobs():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT

        jobs.*,

        machines.name AS machine_name,

        customers.name AS customer_name

    FROM jobs

    LEFT JOIN machines

        ON jobs.machine_id = machines.id

    LEFT JOIN customers

        ON jobs.customer_id = customers.id

    ORDER BY jobs.id DESC

    """)

    jobs = cursor.fetchall()

    conn.close()

    return render_template(
        "jobs.html",
        jobs=jobs
    )


# =========================
# MAKİNE DETAYI
# =========================

@app.route("/machine/<int:id>")
def machine_detail(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM machines WHERE id=?",
        (id,)
    )

    machine = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM jobs WHERE machine_id=? ORDER BY id DESC",
        (id,)
    )

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
            (
                name,
                type,
                brand,
                model,
                control_unit,
                status
            )
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
# MÜŞTERİLER
# =========================

@app.route("/customers")
def customers():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers ORDER BY name")

    customers = cursor.fetchall()

    conn.close()

    return render_template(
        "customers.html",
        customers=customers
    )


# =========================
# MÜŞTERİ EKLE
# =========================

@app.route("/add-customer", methods=["GET", "POST"])
def add_customer():

    if request.method == "POST":

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO customers
            (
                name,
                phone,
                email,
                address,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
        """, (

            request.form["name"],
            request.form["phone"],
            request.form["email"],
            request.form["address"],
            request.form["notes"]

        ))

        conn.commit()
        conn.close()

        return redirect("/customers")

    return render_template("add_customer.html")


# =========================
# YENİ İŞ EKLE
# =========================

@app.route("/machine/<int:machine_id>/add-job", methods=["GET", "POST"])
def add_job(machine_id):

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        customer_id = request.form.get("customer_id")

        if customer_id == "":
            customer_id = None

        cursor.execute("""
            INSERT INTO jobs
            (
                machine_id,
                customer_id,
                job_name,
                material,
                quantity,
                production_date,
                delivery_date,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            machine_id,
            customer_id,
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

    cursor.execute("SELECT * FROM customers ORDER BY name")

    customers = cursor.fetchall()

    conn.close()

    return render_template(
        "add_job.html",
        machine_id=machine_id,
        customers=customers
    )


# =========================
# İŞ DETAYI
# =========================

@app.route("/job/<int:id>")
def job_detail(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT

        jobs.*,

        machines.name AS machine_name,

        customers.name AS customer_name

    FROM jobs

    LEFT JOIN machines

        ON jobs.machine_id = machines.id

    LEFT JOIN customers

        ON jobs.customer_id = customers.id

    WHERE jobs.id=?

    """, (id,))

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