import sqlite3

connection = sqlite3.connect("database/cnc.db")
cursor = connection.cursor()

# ======================================================
# MAKİNELER
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS machines (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,
    type TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    control_unit TEXT,
    serial_number TEXT,

    status TEXT DEFAULT 'Aktif',

    notes TEXT

)
""")

# ======================================================
# MÜŞTERİLER
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    phone TEXT,
    email TEXT,
    address TEXT,

    notes TEXT

)
""")

# ======================================================
# İŞLER
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    customer_id INTEGER,

    job_name TEXT NOT NULL,

    material TEXT,

    quantity INTEGER,

    production_date TEXT,

    delivery_date TEXT,

    status TEXT DEFAULT 'Devam Ediyor',

    notes TEXT,

    FOREIGN KEY(machine_id) REFERENCES machines(id),

    FOREIGN KEY(customer_id) REFERENCES customers(id)

)
""")

# ======================================================
# TEKNİK RESİMLER
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS drawings (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    job_id INTEGER NOT NULL,

    file_name TEXT,

    file_path TEXT,

    upload_date TEXT,

    FOREIGN KEY(job_id) REFERENCES jobs(id)

)
""")

# ======================================================
# NC PROGRAMLARI
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS programs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    job_id INTEGER NOT NULL,

    file_name TEXT,

    file_path TEXT,

    upload_date TEXT,

    FOREIGN KEY(job_id) REFERENCES jobs(id)

)
""")

# ======================================================
# FOTOĞRAFLAR
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS photos (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    job_id INTEGER NOT NULL,

    file_name TEXT,

    file_path TEXT,

    upload_date TEXT,

    FOREIGN KEY(job_id) REFERENCES jobs(id)

)
""")

# ======================================================
# NOTLAR
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS notes (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    job_id INTEGER NOT NULL,

    note TEXT NOT NULL,

    created_at TEXT,

    FOREIGN KEY(job_id) REFERENCES jobs(id)

)
""")

connection.commit()
connection.close()

print("✅ CNC Manager veritabanı başarıyla oluşturuldu.")