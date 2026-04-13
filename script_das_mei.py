import os
from flask import Flask, request, send_from_directory, jsonify
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Pasta onde os PDFs gerados ficam
PDF_FOLDER = "generated_pdfs"
os.makedirs(PDF_FOLDER, exist_ok=True)

# ---------------------------------------------------------
# ROTA DE TESTE
# ---------------------------------------------------------
@app.route("/")
def home():
    return "Servidor Flask rodando no Railway 💼"


# ---------------------------------------------------------
# ROTA PARA SERVIR PDFs VIA URL
# Exemplo: https://seuapp.up.railway.app/pdfs/arquivo.pdf
# ---------------------------------------------------------
@app.route("/pdfs/<path:filename>")
def servir_pdf(filename):
    return send_from_directory(PDF_FOLDER, filename)


# ---------------------------------------------------------
# WEBHOOK DO TWILIO (RECEBE MENSAGENS)
# Twilio chama esse endpoint e você responde direto por aqui.
# ---------------------------------------------------------
@app.route("/webhook", methods=["POST"])
def webhook_twilio():
    sender = request.form.get("From", "")
    msg_body = request.form.get("Body", "").strip()

    print(f"Mensagem recebida de {sender}: {msg_body}")

    resp = MessagingResponse()

    # Exemplo simples: responder automaticamente
    if msg_body.lower() in ["oi", "ola", "olá"]:
        resp.message("Olá! Sou o assistente contábil automatizado do Franklin 😊.")
        return str(resp)

    resp.message("Mensagem recebida! Em breve o Franklin responderá.")
    return str(resp)


# ---------------------------------------------------------
# ROTA EXEMPLO PARA ENVIAR UM PDF AUTOMATICAMENTE
# Útil para testar no navegador sem Twilio
# ---------------------------------------------------------
@app.route("/teste-pdf")
def teste_pdf():
    exemplo_pdf = "exemplo.pdf"
    caminho_pdf = os.path.join(PDF_FOLDER, exemplo_pdf)

    # cria PDF se não existir
    if not os.path.exists(caminho_pdf):
        with open(caminho_pdf, "wb") as f:
            f.write(b"%PDF-1.4 exemplo vazio só para testar")

    url_publica = f"{request.url_root}pdfs/{exemplo_pdf}"
    return jsonify({"pdf_url": url_publica})


# ---------------------------------------------------------
# START DO SERVIDOR (OBRIGATÓRIO PARA O RAILWAY)
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)