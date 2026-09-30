# ParkEase - Parking Management Web App

A browser-based upgrade of the original Python console Parking Management System.

## Features
- Vehicle entry with automatic parking slot assignment
- Vehicle exit and fee calculation
- Printable parking receipt
- Search parked vehicles by vehicle number
- Live total, occupied and available slot counters
- Bike, Car and Bus statistics
- Recent receipts
- SQLite database persistence
- Responsive HTML/CSS dashboard

## Parking Rates
- Scooty: 10₹/hour
- Bike: ₹15/hour
- Car: ₹30/hour
- Bus: ₹40/hour

## Run

```bash
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The SQLite database (`parking.db`) is created automatically on first run.
