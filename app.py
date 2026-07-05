from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_from_directory,
    abort,
    jsonify
)

import sqlite3
import os
import shutil

from datetime import datetime
from werkzeug.utils import secure_filename


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


FILE_TABLES = {
    "drawing": "drawings",
    "program": "programs",
    "photo": "photos"
}


MONTH_NAMES = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık"
}


def get_connection():
    conn = sqlite3.connect("database/cnc.db")
    conn.row_factory = sqlite3.Row

    return conn


def ensure_database_updates():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(jobs)")

    columns = [
        row["name"]
        for row in cursor.fetchall()
    ]

    if "start_date" not in columns:
        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN start_date TEXT
            """
        )

    if "end_date" not in columns:
        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN end_date TEXT
            """
        )

    if "folder_id" not in columns:
        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN folder_id INTEGER
            """
        )

    if "production_date" in columns:
        cursor.execute(
            """
            UPDATE jobs

            SET start_date = production_date

            WHERE
                (
                    start_date IS NULL
                    OR start_date = ''
                )

                AND production_date IS NOT NULL
                AND production_date != ''
            """
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_folders
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            customer_id INTEGER NOT NULL,

            name TEXT NOT NULL,

            created_at TEXT,

            FOREIGN KEY(customer_id)
                REFERENCES customers(id)
        )
        """
    )

    conn.commit()
    conn.close()


def build_date(prefix):
    day = request.form.get(
        f"{prefix}_day",
        ""
    ).strip()

    month = request.form.get(
        f"{prefix}_month",
        ""
    ).strip()

    year = request.form.get(
        f"{prefix}_year",
        ""
    ).strip()

    if not day or not month or not year:
        return ""

    try:
        date_value = datetime(
            int(year),
            int(month),
            int(day)
        )

        return date_value.strftime(
            "%Y-%m-%d"
        )

    except ValueError:
        return ""


def get_date_parts(date_value):
    if not date_value:
        return {
            "day": "",
            "month": "",
            "year": ""
        }

    try:
        parsed_date = datetime.strptime(
            date_value,
            "%Y-%m-%d"
        )

        return {
            "day": parsed_date.day,
            "month": parsed_date.month,
            "year": parsed_date.year
        }

    except ValueError:
        return {
            "day": "",
            "month": "",
            "year": ""
        }


def get_form_folder_id(customer_id):
    folder_id = request.form.get(
        "folder_id",
        ""
    ).strip()

    if not folder_id or not customer_id:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM customer_folders
        WHERE
            id=?
            AND customer_id=?
        """,
        (
            folder_id,
            customer_id
        )
    )

    folder = cursor.fetchone()

    conn.close()

    if folder is None:
        return None

    return folder_id


def delete_physical_file(file_path):
    upload_root = os.path.abspath(
        app.config["UPLOAD_FOLDER"]
    )

    absolute_file_path = os.path.abspath(
        file_path
    )

    if os.path.commonpath(
        [upload_root, absolute_file_path]
    ) != upload_root:
        return

    if os.path.isfile(absolute_file_path):
        os.remove(absolute_file_path)


def delete_job_folder(job_id):
    upload_root = os.path.abspath(
        app.config["UPLOAD_FOLDER"]
    )

    job_folder = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            f"job_{job_id}"
        )
    )

    if os.path.commonpath(
        [upload_root, job_folder]
    ) != upload_root:
        return

    if os.path.isdir(job_folder):
        shutil.rmtree(job_folder)


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/")
def home():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM machines"
    )

    machine_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM customers"
    )

    customer_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM jobs"
    )

    job_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE status=?
        """,
        ("Devam Ediyor",)
    )

    pending_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        machine_count=machine_count,
        customer_count=customer_count,
        job_count=job_count,
        pending_count=pending_count
    )


# =====================================================
# ARAMA
# =====================================================

@app.route("/search")
def search():
    query = request.args.get(
        "q",
        ""
    ).strip()

    results = []

    if query:
        conn = get_connection()
        cursor = conn.cursor()

        search_value = f"%{query}%"

        cursor.execute(
            """
            SELECT DISTINCT
                jobs.*,
                machines.name AS machine_name,
                customers.name AS customer_name,
                customer_folders.name AS folder_name

            FROM jobs

            LEFT JOIN machines
                ON jobs.machine_id = machines.id

            LEFT JOIN customers
                ON jobs.customer_id = customers.id

            LEFT JOIN customer_folders
                ON jobs.folder_id = customer_folders.id

            WHERE
                jobs.job_name LIKE ?

                OR jobs.material LIKE ?

                OR jobs.notes LIKE ?

                OR jobs.status LIKE ?

                OR machines.name LIKE ?

                OR customers.name LIKE ?

                OR customer_folders.name LIKE ?

                OR EXISTS
                (
                    SELECT 1
                    FROM drawings
                    WHERE
                        drawings.job_id = jobs.id
                        AND drawings.file_name LIKE ?
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM programs
                    WHERE
                        programs.job_id = jobs.id
                        AND programs.file_name LIKE ?
                )

                OR EXISTS
                (
                    SELECT 1
                    FROM photos
                    WHERE
                        photos.job_id = jobs.id
                        AND photos.file_name LIKE ?
                )

            ORDER BY jobs.id DESC
            """,
            (
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value
            )
        )

        results = cursor.fetchall()

        conn.close()

    return render_template(
        "search_results.html",
        query=query,
        results=results
    )


# =====================================================
# MAKİNELER
# =====================================================

@app.route("/machines")
def machines():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM machines ORDER BY id"
    )

    machines = cursor.fetchall()

    conn.close()

    return render_template(
        "machines.html",
        machines=machines
    )


# =====================================================
# MAKİNE DETAY
# =====================================================

@app.route("/machine/<int:id>")
def machine_detail(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM machines
        WHERE id=?
        """,
        (id,)
    )

    machine = cursor.fetchone()

    if machine is None:
        conn.close()
        abort(404)

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE machine_id=?
        ORDER BY id DESC
        """,
        (id,)
    )

    jobs = cursor.fetchall()

    conn.close()

    return render_template(
        "machine_detail.html",
        machine=machine,
        jobs=jobs
    )


# =====================================================
# MAKİNE EKLE
# =====================================================

@app.route(
    "/add-machine",
    methods=["GET", "POST"]
)
def add_machine():
    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
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
            """,
            (
                request.form["name"],
                request.form["type"],
                request.form["brand"],
                request.form["model"],
                request.form["control_unit"],
                "Aktif"
            )
        )

        conn.commit()
        conn.close()

        return redirect("/machines")

    return render_template(
        "add_machine.html"
    )


# =====================================================
# MÜŞTERİLER
# =====================================================

@app.route("/customers")
def customers():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            customers.*,
            COUNT(jobs.id) AS job_count

        FROM customers

        LEFT JOIN jobs
            ON jobs.customer_id = customers.id

        GROUP BY customers.id

        ORDER BY customers.name
        """
    )

    customers = cursor.fetchall()

    conn.close()

    return render_template(
        "customers.html",
        customers=customers
    )


# =====================================================
# MÜŞTERİ EKLE
# =====================================================

@app.route(
    "/add-customer",
    methods=["GET", "POST"]
)
def add_customer():
    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO customers
            (
                name,
                phone,
                email,
                address,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.form["name"],
                request.form["phone"],
                request.form["email"],
                request.form["address"],
                request.form["notes"]
            )
        )

        conn.commit()
        conn.close()

        return redirect("/customers")

    return render_template(
        "add_customer.html"
    )


# =====================================================
# HIZLI MÜŞTERİ EKLE
# =====================================================

@app.route(
    "/api/customers/create",
    methods=["POST"]
)
def quick_add_customer():
    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    if not name:
        return jsonify(
            {
                "success": False,
                "message": "Müşteri adı boş bırakılamaz."
            }
        ), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE LOWER(name)=LOWER(?)
        """,
        (name,)
    )

    existing_customer = cursor.fetchone()

    if existing_customer:
        conn.close()

        return jsonify(
            {
                "success": True,
                "customer": {
                    "id": existing_customer["id"],
                    "name": existing_customer["name"]
                }
            }
        )

    cursor.execute(
        """
        INSERT INTO customers
        (
            name,
            phone,
            email,
            address,
            notes
        )
        VALUES (?, '', '', '', '')
        """,
        (name,)
    )

    customer_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify(
        {
            "success": True,
            "customer": {
                "id": customer_id,
                "name": name
            }
        }
    )


# =====================================================
# MÜŞTERİ KLASÖRLERİ API
# =====================================================

@app.route(
    "/api/customer/<int:customer_id>/folders"
)
def customer_folders_api(customer_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            name

        FROM customer_folders

        WHERE customer_id=?

        ORDER BY name
        """,
        (customer_id,)
    )

    folders = cursor.fetchall()

    conn.close()

    return jsonify(
        [
            {
                "id": folder["id"],
                "name": folder["name"]
            }

            for folder in folders
        ]
    )


# =====================================================
# MÜŞTERİ DETAY - KLASÖRLER
# =====================================================

@app.route(
    "/customer/<int:id>",
    methods=["GET", "POST"]
)
def customer_detail(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        conn.close()
        abort(404)

    if request.method == "POST":
        folder_name = request.form.get(
            "folder_name",
            ""
        ).strip()

        if folder_name:
            cursor.execute(
                """
                SELECT id
                FROM customer_folders

                WHERE
                    customer_id=?
                    AND LOWER(name)=LOWER(?)
                """,
                (
                    id,
                    folder_name
                )
            )

            existing_folder = cursor.fetchone()

            if existing_folder is None:
                cursor.execute(
                    """
                    INSERT INTO customer_folders
                    (
                        customer_id,
                        name,
                        created_at
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        id,
                        folder_name,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )
                )

                conn.commit()

        conn.close()

        return redirect(
            f"/customer/{id}"
        )

    cursor.execute(
        """
        SELECT
            customer_folders.*,
            COUNT(jobs.id) AS job_count

        FROM customer_folders

        LEFT JOIN jobs
            ON jobs.folder_id = customer_folders.id

        WHERE customer_folders.customer_id=?

        GROUP BY customer_folders.id

        ORDER BY customer_folders.name
        """,
        (id,)
    )

    folders = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs

        WHERE
            customer_id=?
            AND folder_id IS NULL
        """,
        (id,)
    )

    general_job_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "customer_detail.html",
        customer=customer,
        folders=folders,
        general_job_count=general_job_count
    )


# =====================================================
# MÜŞTERİ KLASÖRÜ - YILLAR
# =====================================================

@app.route(
    "/customer/<int:customer_id>/folder/<int:folder_id>"
)
def customer_folder(customer_id, folder_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (customer_id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        conn.close()
        abort(404)

    if folder_id == 0:
        folder = {
            "id": 0,
            "name": "Genel İşler"
        }

        cursor.execute(
            """
            SELECT
                CAST(
                    strftime('%Y', delivery_date)
                    AS INTEGER
                ) AS year,

                COUNT(*) AS job_count

            FROM jobs

            WHERE
                customer_id=?
                AND folder_id IS NULL
                AND delivery_date IS NOT NULL
                AND delivery_date != ''

            GROUP BY
                strftime('%Y', delivery_date)

            ORDER BY year DESC
            """,
            (customer_id,)
        )

    else:
        cursor.execute(
            """
            SELECT *
            FROM customer_folders

            WHERE
                id=?
                AND customer_id=?
            """,
            (
                folder_id,
                customer_id
            )
        )

        folder = cursor.fetchone()

        if folder is None:
            conn.close()
            abort(404)

        cursor.execute(
            """
            SELECT
                CAST(
                    strftime('%Y', delivery_date)
                    AS INTEGER
                ) AS year,

                COUNT(*) AS job_count

            FROM jobs

            WHERE
                customer_id=?
                AND folder_id=?
                AND delivery_date IS NOT NULL
                AND delivery_date != ''

            GROUP BY
                strftime('%Y', delivery_date)

            ORDER BY year DESC
            """,
            (
                customer_id,
                folder_id
            )
        )

    years = cursor.fetchall()

    conn.close()

    return render_template(
        "customer_folder.html",
        customer=customer,
        folder=folder,
        years=years
    )


# =====================================================
# MÜŞTERİ KLASÖR YILI - AYLAR
# =====================================================

@app.route(
    "/customer/<int:customer_id>/folder/<int:folder_id>/year/<int:year>"
)
def customer_folder_year(
    customer_id,
    folder_id,
    year
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (customer_id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        conn.close()
        abort(404)

    if folder_id == 0:
        folder = {
            "id": 0,
            "name": "Genel İşler"
        }

        cursor.execute(
            """
            SELECT
                CAST(
                    strftime('%m', delivery_date)
                    AS INTEGER
                ) AS month,

                COUNT(*) AS job_count

            FROM jobs

            WHERE
                customer_id=?
                AND folder_id IS NULL
                AND strftime('%Y', delivery_date)=?

            GROUP BY
                strftime('%m', delivery_date)

            ORDER BY month DESC
            """,
            (
                customer_id,
                str(year)
            )
        )

    else:
        cursor.execute(
            """
            SELECT *
            FROM customer_folders

            WHERE
                id=?
                AND customer_id=?
            """,
            (
                folder_id,
                customer_id
            )
        )

        folder = cursor.fetchone()

        if folder is None:
            conn.close()
            abort(404)

        cursor.execute(
            """
            SELECT
                CAST(
                    strftime('%m', delivery_date)
                    AS INTEGER
                ) AS month,

                COUNT(*) AS job_count

            FROM jobs

            WHERE
                customer_id=?
                AND folder_id=?
                AND strftime('%Y', delivery_date)=?

            GROUP BY
                strftime('%m', delivery_date)

            ORDER BY month DESC
            """,
            (
                customer_id,
                folder_id,
                str(year)
            )
        )

    month_rows = cursor.fetchall()

    months = []

    for month_row in month_rows:
        month_number = month_row["month"]

        months.append(
            {
                "month": month_number,
                "month_name": MONTH_NAMES.get(
                    month_number,
                    str(month_number)
                ),
                "job_count": month_row["job_count"]
            }
        )

    conn.close()

    return render_template(
        "customer_folder_year.html",
        customer=customer,
        folder=folder,
        year=year,
        months=months
    )


# =====================================================
# MÜŞTERİ KLASÖR AYI - İŞLER
# =====================================================

@app.route(
    "/customer/<int:customer_id>/folder/<int:folder_id>/year/<int:year>/month/<int:month>"
)
def customer_folder_month(
    customer_id,
    folder_id,
    year,
    month
):
    if month not in MONTH_NAMES:
        abort(404)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (customer_id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        conn.close()
        abort(404)

    if folder_id == 0:
        folder = {
            "id": 0,
            "name": "Genel İşler"
        }

        cursor.execute(
            """
            SELECT
                jobs.*,
                machines.name AS machine_name

            FROM jobs

            LEFT JOIN machines
                ON jobs.machine_id = machines.id

            WHERE
                jobs.customer_id=?
                AND jobs.folder_id IS NULL
                AND strftime('%Y', jobs.delivery_date)=?
                AND strftime('%m', jobs.delivery_date)=?

            ORDER BY
                jobs.delivery_date DESC,
                jobs.id DESC
            """,
            (
                customer_id,
                str(year),
                f"{month:02d}"
            )
        )

    else:
        cursor.execute(
            """
            SELECT *
            FROM customer_folders

            WHERE
                id=?
                AND customer_id=?
            """,
            (
                folder_id,
                customer_id
            )
        )

        folder = cursor.fetchone()

        if folder is None:
            conn.close()
            abort(404)

        cursor.execute(
            """
            SELECT
                jobs.*,
                machines.name AS machine_name

            FROM jobs

            LEFT JOIN machines
                ON jobs.machine_id = machines.id

            WHERE
                jobs.customer_id=?
                AND jobs.folder_id=?
                AND strftime('%Y', jobs.delivery_date)=?
                AND strftime('%m', jobs.delivery_date)=?

            ORDER BY
                jobs.delivery_date DESC,
                jobs.id DESC
            """,
            (
                customer_id,
                folder_id,
                str(year),
                f"{month:02d}"
            )
        )

    jobs = cursor.fetchall()

    conn.close()

    return render_template(
        "customer_folder_month.html",
        customer=customer,
        folder=folder,
        year=year,
        month=month,
        month_name=MONTH_NAMES[month],
        jobs=jobs
    )


# =====================================================
# TÜM İŞLER
# =====================================================

@app.route("/jobs")
def jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            jobs.*,
            machines.name AS machine_name,
            customers.name AS customer_name,
            customer_folders.name AS folder_name

        FROM jobs

        LEFT JOIN machines
            ON jobs.machine_id = machines.id

        LEFT JOIN customers
            ON jobs.customer_id = customers.id

        LEFT JOIN customer_folders
            ON jobs.folder_id = customer_folders.id

        ORDER BY jobs.id DESC
        """
    )

    jobs = cursor.fetchall()

    conn.close()

    return render_template(
        "jobs.html",
        jobs=jobs
    )


# =====================================================
# YENİ İŞ - GLOBAL
# =====================================================

@app.route(
    "/add-job",
    methods=["GET", "POST"]
)
def add_job_global():
    return handle_add_job()


# =====================================================
# YENİ İŞ - MAKİNE İÇİNDEN
# =====================================================

@app.route(
    "/machine/<int:machine_id>/add-job",
    methods=["GET", "POST"]
)
def add_job(machine_id):
    return handle_add_job(
        selected_machine_id=machine_id
    )


def handle_add_job(selected_machine_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM machines
        ORDER BY name
        """
    )

    machines = cursor.fetchall()

    if selected_machine_id is not None:
        cursor.execute(
            """
            SELECT id
            FROM machines
            WHERE id=?
            """,
            (selected_machine_id,)
        )

        machine = cursor.fetchone()

        if machine is None:
            conn.close()
            abort(404)

    if request.method == "POST":
        machine_id = request.form.get(
            "machine_id",
            ""
        ).strip()

        customer_id = request.form.get(
            "customer_id",
            ""
        ).strip()

        if not machine_id:
            conn.close()

            return redirect(
                request.path
            )

        if not customer_id:
            customer_id = None

        folder_id = get_form_folder_id(
            customer_id
        )

        start_date = build_date(
            "start"
        )

        end_date = build_date(
            "end"
        )

        delivery_date = build_date(
            "delivery"
        )

        cursor.execute(
            """
            INSERT INTO jobs
            (
                machine_id,
                customer_id,
                folder_id,
                job_name,
                material,
                quantity,
                start_date,
                end_date,
                delivery_date,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                machine_id,
                customer_id,
                folder_id,
                request.form["job_name"],
                request.form["material"],
                request.form["quantity"],
                start_date,
                end_date,
                delivery_date,
                "Devam Ediyor",
                request.form["notes"]
            )
        )

        job_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return redirect(
            f"/job/{job_id}"
        )

    cursor.execute(
        """
        SELECT *
        FROM customers
        ORDER BY name
        """
    )

    customers = cursor.fetchall()

    conn.close()

    current_year = datetime.now().year

    years = range(
        current_year - 10,
        current_year + 6
    )

    return render_template(
        "add_job.html",
        machines=machines,
        selected_machine_id=selected_machine_id,
        customers=customers,
        years=years,
        months=MONTH_NAMES
    )


# =====================================================
# İŞ DETAY
# =====================================================

@app.route("/job/<int:id>")
def job_detail(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            jobs.*,
            machines.name AS machine_name,
            customers.name AS customer_name,
            customer_folders.name AS folder_name

        FROM jobs

        LEFT JOIN machines
            ON jobs.machine_id = machines.id

        LEFT JOIN customers
            ON jobs.customer_id = customers.id

        LEFT JOIN customer_folders
            ON jobs.folder_id = customer_folders.id

        WHERE jobs.id=?
        """,
        (id,)
    )

    job = cursor.fetchone()

    if job is None:
        conn.close()
        abort(404)

    cursor.execute(
        """
        SELECT *
        FROM drawings
        WHERE job_id=?
        ORDER BY id DESC
        """,
        (id,)
    )

    drawings = cursor.fetchall()

    cursor.execute(
        """
        SELECT *
        FROM programs
        WHERE job_id=?
        ORDER BY id DESC
        """,
        (id,)
    )

    programs = cursor.fetchall()

    cursor.execute(
        """
        SELECT *
        FROM photos
        WHERE job_id=?
        ORDER BY id DESC
        """,
        (id,)
    )

    photos = cursor.fetchall()

    conn.close()

    return render_template(
        "job_detail.html",
        job=job,
        drawings=drawings,
        programs=programs,
        photos=photos
    )


# =====================================================
# İŞ DÜZENLE
# =====================================================

@app.route(
    "/job/<int:id>/edit",
    methods=["GET", "POST"]
)
def edit_job(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE id=?
        """,
        (id,)
    )

    job = cursor.fetchone()

    if job is None:
        conn.close()
        abort(404)

    if request.method == "POST":
        customer_id = request.form.get(
            "customer_id",
            ""
        ).strip()

        if not customer_id:
            customer_id = None

        folder_id = get_form_folder_id(
            customer_id
        )

        start_date = build_date(
            "start"
        )

        end_date = build_date(
            "end"
        )

        delivery_date = build_date(
            "delivery"
        )

        cursor.execute(
            """
            UPDATE jobs

            SET
                customer_id=?,
                folder_id=?,
                job_name=?,
                material=?,
                quantity=?,
                start_date=?,
                end_date=?,
                delivery_date=?,
                status=?,
                notes=?

            WHERE id=?
            """,
            (
                customer_id,
                folder_id,
                request.form["job_name"],
                request.form["material"],
                request.form["quantity"],
                start_date,
                end_date,
                delivery_date,
                request.form["status"],
                request.form["notes"],
                id
            )
        )

        conn.commit()
        conn.close()

        return redirect(
            f"/job/{id}"
        )

    cursor.execute(
        """
        SELECT *
        FROM customers
        ORDER BY name
        """
    )

    customers = cursor.fetchall()

    folders = []

    if job["customer_id"]:
        cursor.execute(
            """
            SELECT *
            FROM customer_folders

            WHERE customer_id=?

            ORDER BY name
            """,
            (job["customer_id"],)
        )

        folders = cursor.fetchall()

    conn.close()

    current_year = datetime.now().year

    years = range(
        current_year - 10,
        current_year + 6
    )

    return render_template(
        "edit_job.html",
        job=job,
        customers=customers,
        folders=folders,
        years=years,
        months=MONTH_NAMES,
        start_parts=get_date_parts(
            job["start_date"]
        ),
        end_parts=get_date_parts(
            job["end_date"]
        ),
        delivery_parts=get_date_parts(
            job["delivery_date"]
        )
    )


# =====================================================
# İŞ SİL
# =====================================================

@app.route(
    "/job/<int:id>/delete",
    methods=["POST"]
)
def delete_job(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE id=?
        """,
        (id,)
    )

    job = cursor.fetchone()

    if job is None:
        conn.close()
        abort(404)

    machine_id = job["machine_id"]

    try:
        cursor.execute(
            "DELETE FROM drawings WHERE job_id=?",
            (id,)
        )

        cursor.execute(
            "DELETE FROM programs WHERE job_id=?",
            (id,)
        )

        cursor.execute(
            "DELETE FROM photos WHERE job_id=?",
            (id,)
        )

        cursor.execute(
            "DELETE FROM notes WHERE job_id=?",
            (id,)
        )

        cursor.execute(
            "DELETE FROM jobs WHERE id=?",
            (id,)
        )

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        conn.close()

        raise

    conn.close()

    delete_job_folder(id)

    return redirect(
        f"/machine/{machine_id}"
    )


# =====================================================
# TEKNİK RESİM YÜKLE
# =====================================================

@app.route(
    "/job/<int:job_id>/upload-drawing",
    methods=["GET", "POST"]
)
def upload_drawing(job_id):
    if request.method == "POST":
        file = request.files.get(
            "drawing"
        )

        if not file or file.filename == "":
            return redirect(
                f"/job/{job_id}"
            )

        filename = secure_filename(
            file.filename
        )

        folder_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            f"job_{job_id}",
            "drawings"
        )

        os.makedirs(
            folder_path,
            exist_ok=True
        )

        file_path = os.path.join(
            folder_path,
            filename
        )

        file.save(file_path)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO drawings
            (
                job_id,
                file_name,
                file_path,
                upload_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                filename,
                file_path,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()
        conn.close()

        return redirect(
            f"/job/{job_id}"
        )

    return render_template(
        "upload_drawing.html",
        job_id=job_id
    )


# =====================================================
# NC PROGRAMI YÜKLE
# =====================================================

@app.route(
    "/job/<int:job_id>/upload-program",
    methods=["GET", "POST"]
)
def upload_program(job_id):
    if request.method == "POST":
        file = request.files.get(
            "program"
        )

        if not file or file.filename == "":
            return redirect(
                f"/job/{job_id}"
            )

        filename = secure_filename(
            file.filename
        )

        folder_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            f"job_{job_id}",
            "programs"
        )

        os.makedirs(
            folder_path,
            exist_ok=True
        )

        file_path = os.path.join(
            folder_path,
            filename
        )

        file.save(file_path)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO programs
            (
                job_id,
                file_name,
                file_path,
                upload_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                filename,
                file_path,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()
        conn.close()

        return redirect(
            f"/job/{job_id}"
        )

    return render_template(
        "upload_program.html",
        job_id=job_id
    )


# =====================================================
# FOTOĞRAF YÜKLE
# =====================================================

@app.route(
    "/job/<int:job_id>/upload-photo",
    methods=["GET", "POST"]
)
def upload_photo(job_id):
    if request.method == "POST":
        files = request.files.getlist(
            "photos"
        )

        conn = get_connection()
        cursor = conn.cursor()

        folder_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            f"job_{job_id}",
            "photos"
        )

        os.makedirs(
            folder_path,
            exist_ok=True
        )

        for file in files:
            if not file or file.filename == "":
                continue

            filename = secure_filename(
                file.filename
            )

            file_path = os.path.join(
                folder_path,
                filename
            )

            file.save(file_path)

            cursor.execute(
                """
                INSERT INTO photos
                (
                    job_id,
                    file_name,
                    file_path,
                    upload_date
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    job_id,
                    filename,
                    file_path,
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )
            )

        conn.commit()
        conn.close()

        return redirect(
            f"/job/{job_id}"
        )

    return render_template(
        "upload_photo.html",
        job_id=job_id
    )


# =====================================================
# DOSYA SİL
# =====================================================

@app.route(
    "/delete-file/<file_type>/<int:file_id>",
    methods=["POST"]
)
def delete_file(file_type, file_id):
    table_name = FILE_TABLES.get(
        file_type
    )

    if table_name is None:
        abort(404)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT *
        FROM {table_name}
        WHERE id=?
        """,
        (file_id,)
    )

    file_record = cursor.fetchone()

    if file_record is None:
        conn.close()
        abort(404)

    job_id = file_record["job_id"]
    file_path = file_record["file_path"]

    delete_physical_file(
        file_path
    )

    cursor.execute(
        f"""
        DELETE FROM {table_name}
        WHERE id=?
        """,
        (file_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        f"/job/{job_id}"
    )


# =====================================================
# YÜKLENEN DOSYALAR
# =====================================================

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(
        ".",
        filename
    )


# =====================================================
# PROGRAMI BAŞLAT
# =====================================================

if __name__ == "__main__":
    ensure_database_updates()

    app.run(debug=True)