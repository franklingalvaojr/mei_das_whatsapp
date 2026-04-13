import os
from flask import Flask, request, send_from_directory, jsonify
from twilio.rest import Client
from reportlab.pdfgen import canvas

# ==========================================================
# CONFIGURAÇÃO DO FLASK
# ==========================================================
app = Flask(__name__)

# Pasta onde os PDFs gerados serão armazenados
PDF_DIR = "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)


# ==========================================================
# FUNÇÃO PARA GERAR UM PDF REAL (SEM ERROS DE ASCII)
# ==========================================================
def gerar_pdf(nome_arquivo, texto="Documento gerado automaticamente."):
    caminho = os.path.join(PDF_DIR, nome_arquivo)
    c = canvas.Canvas(caminho)
    c.drawString(100, 750, texto)
    c.save()
    return caminho


# ==========================================================
# ROTA PARA SERVIR PDFs PUBLICAMENTE (Twilio acessa daqui)
# ==========================================================
@app.route('/pdfs/<path:filename>', methods=['GET'])
def serve_pdf(filename):
    return send_from_directory(PDF_DIR, filename, as_attachment=True)


# ==========================================================
# WEBHOOK DO WHATSAPP (Twilio chama esta rota)
# ==========================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.form
    mensagem = data.get("Body", "").strip().lower()
    celular_cliente = data.get("From", "")

    if mensagem == "das":
        nome_pdf = "DAS_MEI.pdf"
        caminho_pdf = gerar_pdf(nome_pdf, "Seu DAS MEI gerado automaticamente.")

        pdf_url = f"{os.environ.get('RAILWAY_URL')}/pdfs/{nome_pdf}"

        enviar_whatsapp(
            to=celular_cliente,
            body="Aqui está o seu DAS MEI deste mês.",
            media_url=pdf_url
        )

        return "PDF enviado", 200

    return "Mensagem recebida", 200


# ==========================================================
# FUNÇÃO PARA ENVIAR MENSAGEM VIA TWILIO
# ==========================================================
def enviar_whatsapp(to, body, media_url=None):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.environ.get("TWILIO_FROM")

    client = Client(account_sid, auth_token)

    mensagem = {
        "from_": from_whatsapp,
        "body": body,
        "to": to
    }

    if media_url:
        mensagem["media_url"] = [media_url]

    client.messages.create(**mensagem)


# ==========================================================
# ROTA PARA TESTAR SE O SERVIDOR ESTÁ ONLINE
# ==========================================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "online", "message": "Servidor MEI DAS rodando!"})


# ==========================================================
# INICIALIZAR APP NO RAILWAY
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
