import os
import threading
import json
from flask import Flask, request, send_from_directory, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from twilio.rest import Client
from reportlab.pdfgen import canvas

# ==========================================================
# CONFIGURAÇÕES INICIAIS
# ==========================================================

app = Flask(__name__)

PDF_DIR = "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)


# ==========================================================
# FUNÇÃO: CARREGAR CLIENTES DO GOOGLE SHEETS
# ==========================================================

def carregar_clientes_google():
    cred_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not cred_json:
        return {"erro": "Variável GOOGLE_CREDENTIALS_JSON não encontrada."}

    info = json.loads(cred_json)

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )

    service = build("sheets", "v4", credentials=credentials)

    SPREADSHEET_ID = "1XvmBdAjl1blUd7FQkQR_IWrKg3UY51nWFup-9i7tiAs"
    RANGE_NAME = "Página1!A:C"

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
        .execute()
    )

    values = result.get("values", [])
    clientes = []

    for linha in values[1:]:
        clientes.append(
            {
                "cnpj": linha[0] if len(linha) > 0 else "",
                "nome": linha[1] if len(linha) > 1 else "",
                "whatsapp": linha[2] if len(linha) > 2 else "",
            }
        )

    return clientes


# ==========================================================
# FUNÇÃO: GERAR PDF
# ==========================================================

def gerar_pdf(nome_pdf, texto):
    caminho = os.path.join(PDF_DIR, nome_pdf)
    c = canvas.Canvas(caminho)
    c.drawString(100, 750, texto)
    c.save()
    return caminho


def gerar_pdf_das(nome_cliente):
    nome_pdf = f"DAS_{nome_cliente.replace(' ', '_')}.pdf"
    caminho = gerar_pdf(nome_pdf, f"DAS MEI gerado automaticamente para {nome_cliente}")
    return nome_pdf


# ==========================================================
# FUNÇÃO: ENVIAR WHATSAPP PELO TWILIO
# ==========================================================

def enviar_pdf_whatsapp(numero, pdf_url, nome_cliente):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    phone = os.environ.get("TWILIO_PHONE_NUMBER")

    client = Client(account_sid, auth_token)

    if pdf_url:
        body = f"*DAS do MEI — {nome_cliente}*\nSegue o documento do mês."
        client.messages.create(
            from_=phone,
            to=f"whatsapp:{numero}",
            body=body,
            media_url=[pdf_url],
        )
    else:
        client.messages.create(
            from_=phone,
            to="whatsapp:+5584999676314",
            body="Todos os DAS foram enviados!",
        )


# ==========================================================
# PROCESSAR CLIENTES AUTOMATICAMENTE
# ==========================================================

def processar_todos_os_clientes():
    clientes = carregar_clientes_google()
    dominio = os.environ.get("RAILWAY_URL")

    for cliente in clientes:
        nome = cliente["nome"]
        numero = cliente["whatsapp"]

        nome_pdf = gerar_pdf_das(nome)
        pdf_url = f"{dominio}/pdfs/{nome_pdf}"

        enviar_pdf_whatsapp(numero, pdf_url, nome)

    enviar_pdf_whatsapp(None, None, None)


# ==========================================================
# ROTAS FLASK
# ==========================================================

@app.route("/clientes")
def rota_clientes():
    return {"clientes": carregar_clientes_google()}


@app.route("/pdfs/<path:filename>")
def serve_pdf(filename):
    return send_from_directory(PDF_DIR, filename, as_attachment=True)


@app.route("/webhook", methods=["POST"])
def webhook():
    mensagem = request.form.get("Body", "").strip().lower()

    if mensagem == "enviar das":
        threading.Thread(target=processar_todos_os_clientes).start()
        return "Envio iniciado!", 200

    return "OK", 200


@app.route("/")
def home():
    return jsonify({"status": "online", "message": "Servidor MEI DAS rodando!"})


# ==========================================================
# INÍCIO DO SERVIDOR
# ==========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
