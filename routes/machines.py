from flask import Blueprint, render_template
import sqlite3

machines_bp = Blueprint("machines", __name__)


def get_connection():
    conn = sqlite3.connect("database/cnc.db")
    conn.row_factory = sqlite3.Row
    return conn


@machines_bp.route("/machines")
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