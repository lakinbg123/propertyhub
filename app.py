from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PropertyHub</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #f5f7fb; color: #1f2937; }
    header { background: white; padding: 18px 24px; border-bottom: 1px solid #e5e7eb; }
    .wrap { max-width: 1000px; margin: 0 auto; }
    .hero { padding: 48px 24px; }
    .card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 8px 30px rgba(0,0,0,.06); }
    h1 { margin: 0 0 12px; font-size: 40px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap: 16px; margin-top: 24px; }
    .box { background: #eef4ff; border-radius: 14px; padding: 18px; }
    .chat {
      position: fixed; right: 20px; bottom: 20px; width: 64px; height: 64px;
      border-radius: 999px; border: none; background: #2563eb; color: white;
      font-size: 28px; box-shadow: 0 8px 24px rgba(37,99,235,.35);
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap"><strong>PropertyHub</strong></div>
  </header>
  <section class="hero">
    <div class="wrap">
      <div class="card">
        <h1>Property management, simplified.</h1>
        <p>Manage properties, tenants, maintenance, payments, and screening in one clean platform.</p>
        <div class="grid">
          <div class="box"><strong>Owner Dashboard</strong><br>Upload and manage properties.</div>
          <div class="box"><strong>Tenant Portal</strong><br>Pay rent, request maintenance, message support.</div>
          <div class="box"><strong>Maintenance</strong><br>Track and resolve work orders.</div>
          <div class="box"><strong>AI Helper</strong><br>Answers tenant questions before escalation.</div>
        </div>
      </div>
    </div>
  </section>
  <button class="chat">💬</button>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
