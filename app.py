from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "parking-management-demo-key"

DATABASE = "parking.db"
TOTAL_SLOTS = 50

RATES = {
    "Scooty": 10,
    "Bike": 15,
    "Car": 30,
    "Bus": 40
}

PREFIXES = {
    "Scooty": "S",
    "Bike": "B",
    "Car": "C",
    "Bus": "BUS"
}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS parking_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT UNIQUE NOT NULL,
            vehicle_type TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            slot TEXT UNIQUE NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            slot TEXT NOT NULL,
            duration REAL NOT NULL,
            rate REAL NOT NULL,
            total_fee REAL NOT NULL,
            exit_time TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def next_slot(vehicle_type):
    conn = get_db()

    used = {
        row["slot"]
        for row in conn.execute("SELECT slot FROM parking_records")
    }

    conn.close()

    prefix = PREFIXES[vehicle_type]

    for number in range(1, TOTAL_SLOTS + 1):
        slot = f"{prefix}-{number:02d}"

        if slot not in used:
            return slot

    return None


def dashboard_data(search=""):
    conn = get_db()

    if search:
        vehicles = conn.execute(
            "SELECT * FROM parking_records WHERE vehicle_number LIKE ? ORDER BY id DESC",
            (f"%{search.upper()}%",)
        ).fetchall()
    else:
        vehicles = conn.execute(
            "SELECT * FROM parking_records ORDER BY id DESC"
        ).fetchall()

    occupied = conn.execute(
        "SELECT COUNT(*) AS count FROM parking_records"
    ).fetchone()["count"]

    stats_rows = conn.execute(
        "SELECT vehicle_type, COUNT(*) AS count FROM parking_records GROUP BY vehicle_type"
    ).fetchall()

    recent_receipts = conn.execute(
        "SELECT * FROM receipts ORDER BY id DESC LIMIT 5"
    ).fetchall()

    conn.close()

    stats = {
        "Scooty": 0,
        "Bike": 0,
        "Car": 0,
        "Bus": 0
    }

    for row in stats_rows:
        stats[row["vehicle_type"]] = row["count"]

    return vehicles, occupied, stats, recent_receipts


@app.route("/")
def index():
    search = request.args.get("search", "").strip()

    vehicles, occupied, stats, recent_receipts = dashboard_data(search)

    return render_template(
        "index.html",
        vehicles=vehicles,
        occupied=occupied,
        available=TOTAL_SLOTS - occupied,
        total_slots=TOTAL_SLOTS,
        stats=stats,
        search=search,
        recent_receipts=recent_receipts
    )


@app.route("/entry", methods=["POST"])
def vehicle_entry():
    vehicle_number = request.form.get(
        "vehicle_number", ""
    ).strip().upper()

    vehicle_type = request.form.get(
        "vehicle_type", ""
    ).strip().capitalize()

    entry_time = request.form.get(
        "entry_time", ""
    ).strip()

    pattern = r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$"

    if not re.match(pattern, vehicle_number):
        flash(
            "Invalid vehicle number. Example: MP09AB1234",
            "error"
        )
        return redirect(url_for("index"))

    if vehicle_type not in RATES or not entry_time:
        flash(
            "Please enter valid vehicle details.",
            "error"
        )
        return redirect(url_for("index"))

    conn = get_db()

    occupied = conn.execute(
        "SELECT COUNT(*) AS count FROM parking_records"
    ).fetchone()["count"]

    existing = conn.execute(
        "SELECT id FROM parking_records WHERE vehicle_number = ?",
        (vehicle_number,)
    ).fetchone()

    conn.close()

    if existing:
        flash(
            "This vehicle is already parked.",
            "error"
        )
        return redirect(url_for("index"))

    if occupied >= TOTAL_SLOTS:
        flash(
            "Parking is full.",
            "error"
        )
        return redirect(url_for("index"))

    slot = next_slot(vehicle_type)

    if not slot:
        flash(
            "No slot is available for this vehicle type.",
            "error"
        )
        return redirect(url_for("index"))

    conn = get_db()

    conn.execute(
        """
        INSERT INTO parking_records
        (vehicle_number, vehicle_type, entry_time, slot)
        VALUES (?, ?, ?, ?)
        """,
        (
            vehicle_number,
            vehicle_type,
            entry_time,
            slot
        )
    )

    conn.commit()
    conn.close()

    flash(
        f"Vehicle parked successfully. Slot: {slot}",
        "success"
    )

    return redirect(url_for("index"))


@app.route("/exit", methods=["POST"])
def vehicle_exit():
    vehicle_number = request.form.get(
        "vehicle_number", ""
    ).strip().upper()

    try:
        duration = float(
            request.form.get("duration", "0")
        )
    except ValueError:
        duration = 0

    if not vehicle_number or duration <= 0:
        flash(
            "Enter a valid vehicle number and parking duration.",
            "error"
        )
        return redirect(url_for("index"))

    conn = get_db()

    vehicle = conn.execute(
        "SELECT * FROM parking_records WHERE vehicle_number = ?",
        (vehicle_number,)
    ).fetchone()

    if not vehicle:
        conn.close()

        flash(
            "Vehicle not found.",
            "error"
        )

        return redirect(url_for("index"))

    rate = RATES[vehicle["vehicle_type"]]

    total_fee = round(
        duration * rate,
        2
    )

    exit_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )

    cursor = conn.execute(
        """
        INSERT INTO receipts
        (vehicle_number, vehicle_type, slot, duration, rate, total_fee, exit_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vehicle["vehicle_number"],
            vehicle["vehicle_type"],
            vehicle["slot"],
            duration,
            rate,
            total_fee,
            exit_time
        )
    )

    receipt_id = cursor.lastrowid

    conn.execute(
        "DELETE FROM parking_records WHERE id = ?",
        (vehicle["id"],)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "receipt",
            receipt_id=receipt_id
        )
    )


@app.route("/receipt/<int:receipt_id>")
def receipt(receipt_id):
    conn = get_db()

    item = conn.execute(
        "SELECT * FROM receipts WHERE id = ?",
        (receipt_id,)
    ).fetchone()

    conn.close()

    if not item:
        flash(
            "Receipt not found.",
            "error"
        )
        return redirect(url_for("index"))

    return render_template(
        "receipt.html",
        receipt=item
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)