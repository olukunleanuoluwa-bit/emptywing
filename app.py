from flask import Flask, request, redirect, render_template_string
import sqlite3, os, requests
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
def db():
    conn = sqlite3.connect('emptywing.db')
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = db()
    conn.execute('CREATE TABLE IF NOT EXISTS flights (id INTEGER PRIMARY KEY, operator TEXT, from_city TEXT, to_city TEXT, date TEXT, aircraft TEXT, seats INTEGER, normal_price INTEGER, dead_price INTEGER, per_seat INTEGER, status TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY, flight_id INTEGER, name TEXT, phone TEXT, email TEXT, seats_booked INTEGER, amount INTEGER, ref TEXT, status TEXT)')
    if conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0] == 0:
        conn.execute("INSERT INTO flights VALUES (1,'EAN Aviation','Lagos (LOS)','Abuja (ABV)','Tomorrow 9:00 AM','Challenger 604 - 8 Seats',8,12000000,4500000,650000,'LIVE')")
        conn.execute("INSERT INTO flights VALUES (2,'Caverton','Abuja (ABV)','Lagos (LOS)','Tomorrow 4:00 PM','Hawker 800 - 7 Seats',7,11000000,3800000,600000,'LIVE')")
    conn.commit()
    conn.close()
TEMPLATE = """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>EmptyWing</title><style>*{font-family:sans-serif;margin:0;padding:0;box-sizing:border-box}body{background:#0a0a0a;color:white;padding:18px}.logo{font-weight:900;font-size:22px}.logo span{color:#22c55e}.hero{padding:30px 0}.hero h1{font-size:32px}.card{background:#151515;border:1px solid #222;border-radius:18px;padding:18px;margin:18px 0}.badge{background:#22c55e;color:black;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700}.route{font-size:20px;font-weight:800;margin:10px 0}.price{color:#22c55e;font-size:18px;font-weight:800}.btn{display:block;text-align:center;background:white;color:black;padding:14px;border-radius:12px;font-weight:800;text-decoration:none;margin-top:10px}input{width:100%;padding:14px;margin:8px 0;border-radius:12px;border:1px solid #333;background:#111;color:white}</style></head><body><div style="display:flex;justify-content:space-between"><div class="logo">EMPTY<span>WING</span></div><div style="font-size:12px;border:1px solid #333;padding:6px 10px;border-radius:20px">PAYSTACK SECURED</div></div>{% if page == 'home' %}<div class="hero"><h1>Private jets fly empty everyday.<br>Fly them for 60% off.</h1><p style="color:#999;margin-top:8px">Operated by NCAA-licensed airlines. Paystack escrow protected.</p></div>{% for f in flights %}<div class="card"><span class="badge">LIVE - {{f['seats']}} SEATS</span><div class="route">{{f['from_city']}} -> {{f['to_city']}}</div><div style="color:#888;font-size:13px">{{f['date']}} - {{f['aircraft']}} - {{f['operator']}}</div><div style="margin-top:10px"><span style="text-decoration:line-through;color:#666">N{{f['normal_price']}}</span> <span class="price">N{{f['dead_price']}} full jet</span> <br><span class="price">N{{f['per_seat']}} per seat</span></div><a class="btn" href="/book/{{f['id']}}">Book with Paystack</a></div>{% endfor %}{% else %}<h2 style="margin:20px 0">{{f['from_city']}} -> {{f['to_city']}}</h2><form method="POST"><input name="name" placeholder="Full Name" required><input name="phone" placeholder="WhatsApp Number" required><input name="email" type="email" placeholder="Email" required><input name="seats" type="number" min="1" max="{{f['seats']}}" value="1" required><button class="btn" style="width:100%;border:none">Pay with Paystack</button></form>{% endif %}</body></html>"""
@app.route("/")
def home():
    init_db()
    conn=db()
    flights=conn.execute("SELECT * FROM flights WHERE status='LIVE'").fetchall()
    conn.close()
    return render_template_string(TEMPLATE, page='home', flights=flights)
@app.route("/book/<int:fid>", methods=["GET","POST"])
def book(fid):
    conn=db()
    f=conn.execute("SELECT * FROM flights WHERE id=?", (fid,)).fetchone()
    if not f: return "Not found"
    if request.method=="POST":
        name=request.form['name']; phone=request.form['phone']; email=request.form['email']; seats=int(request.form['seats'])
        amount=f['per_seat']*seats
        conn.execute("INSERT INTO bookings (flight_id,name,phone,email,seats_booked,amount,ref,status) VALUES (?,?,?,?,?,?,?,?)",(fid,name,phone,email,seats,amount,'temp','PENDING'))
        conn.commit()
        bid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}
        payload={"email": email, "amount": amount*100, "reference": f"EW-{bid}-{fid}", "callback_url": request.host_url+"verify", "metadata": {"flight_id": fid, "name": name, "phone": phone}}
        r=requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers).json()
        if r.get('status'):
            conn=db()
            conn.execute("UPDATE bookings SET ref=? WHERE id=?", (r['data']['reference'], bid))
            conn.commit()
            conn.close()
            return redirect(r['data']['authorization_url'])
        else:
            return f"Paystack Error: {r}"
    conn.close()
    return render_template_string(TEMPLATE, page='book', f=f)
@app.route("/verify")
def verify():
    ref=request.args.get('reference')
    headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}
    r=requests.get(f"https://api.paystack.co/transaction/verify/{ref}", headers=headers).json()
    if r.get('status') and r['data']['status']=='success':
        conn=db()
        conn.execute("UPDATE bookings SET status='PAID' WHERE ref=?", (ref,))
        conn.commit()
        conn.close()
        return f"<body style='background:#0a0a0a;color:white;text-align:center;padding:30px;font-family:sans-serif'><h1>Payment Confirmed</h1><p>Ref: {ref}</p><p>We will WhatsApp you within 30 mins.</p><a href='/' style='color:#22c55e'>Home</a></body>"
    return f"Not confirmed: {r}"
if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
