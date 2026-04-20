from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>PropertyHub is LIVE 🚀</h1>
    <p>Your deployment is working.</p>
    <p>Next step: build features.</p>
    """

if __name__ == "__main__":
    app.run(debug=True)
