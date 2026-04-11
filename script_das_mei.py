import os
import schedule
import time
from datetime import datetime, timedelta
from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import qrcode
from io import BytesIO
from pyngrok import ngrok
import threading
import logging
from reportlab.lib.utils import ImageReader

# --- Configuração de Logging ---
# Configura o logger para exibir mensagens informativas no console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Variáveis de Configuração (EDITAR AQUI) ---
# Encontre seu Account SID no painel do Twilio (https://www.twilio.com/console)
TWILIO_SID = 'ACcfa76b779914f8feb8991d09641e00d8' 

# Encontre seu Auth Token no painel do Twilio
TWILIO_AUTH_TOKEN = os.environ["TWILIO_ACCOUNT_SID"] 

# Seu número do Sandbox Twilio WhatsApp (ex: whatsapp:+14155238886)
TWILIO_FROM_WHATSAPP = 'whatsapp:+14155238886' 

# ID da sua planilha Google Sheets (já preenchido com o seu ID fornecido)
GOOGLE_SHEETS_ID = os.environ["TWILIO_AUTH_TOKEN"] 

# Defina como True para apenas simular o envio (não gasta créditos Twilio).
# Defina como False para enviar mensagens de WhatsApp de verdade.
TEST_MODE = False 

# --- Fim das Variáveis de Configuração ---

# --- Configuração Google Sheets ---
# Define o escopo de acesso para a API do Google Sheets e Drive
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
# Carrega as credenciais do arquivo JSON para autenticação
CREDS = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
# Autoriza o cliente gspread com as credenciais
CLIENT = gspread.authorize(CREDS)

# --- Configuração Twilio ---
# Inicializa o cliente Twilio com seu SID e Auth Token
TWILIO_CLIENT = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# --- Configuração Flask ---
# Inicializa o aplicativo Flask
app = Flask(__name__)
# Define o diretório onde os PDFs serão temporariamente armazenados
PDF_DIR = 'generated_pdfs'
if not os.path.exists(PDF_DIR):
    os.makedirs(PDF_DIR) # Cria o diretório se ele não existir

# Variável global para armazenar a URL pública do Ngrok
NGROK_PUBLIC_URL = None

# --- Rotas Flask ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint para receber callbacks do Twilio.
    Usado para confirmar o status de envio das mensagens.
    """
    from_number = request.values.get('From', '')
    message_body = request.values.get('Body', '')
    logging.info(f"Webhook recebido de {from_number}: {message_body}")
    
    # Cria uma resposta TwiML (pode ser vazia ou com uma mensagem de confirmação)
    resp = MessagingResponse()
    # resp.message("Confirmação recebida.") # Opcional: enviar uma resposta de volta
    return str(resp)

@app.route('/pdfs/', methods=['GET'])
def serve_pdf(filename):
    """
    Endpoint para servir os arquivos PDF gerados.
    Permite que o Twilio acesse o PDF para anexar à mensagem.
    """
    logging.info(f"Servindo arquivo PDF: {filename}")
    return send_from_directory(PDF_DIR, filename)

# --- Funções de Automação ---
def ler_clientes():
    """
    Lê os dados dos clientes da planilha Google Sheets.
    Retorna uma lista de dicionários com CNPJ, Nome e WhatsApp.
    """
    try:
        # Abre a primeira aba da planilha pelo ID
        sheet = CLIENT.open_by_key(GOOGLE_SHEETS_ID).sheet1
        # Obtém todos os registros como uma lista de dicionários
        data = sheet.get_all_records()
        clientes = []
        for row in data:
            # Adiciona cada cliente à lista
            clientes.append({
                'cnpj': str(row['CNPJ']).strip(),  # Garante que CNPJ é string e remove espaços
                'nome': str(row['Nome']).strip(),  # Garante que Nome é string e remove espaços
                'whatsapp': str(row['WhatsApp']).strip() # Garante que WhatsApp é string e remove espaços
            })
        logging.info(f"Clientes lidos da planilha: {len(clientes)}")
        return clientes
    except Exception as e:
        logging.error(f"Erro ao ler planilha: {e}")
        return []

def gerar_pdf_das(cnpj, nome):
    """
    Gera um PDF simulado do DAS MEI com dados básicos.
    Retorna o caminho completo do arquivo PDF gerado.
    """
    try:
        # Gera um timestamp para garantir nome de arquivo único
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = os.path.join(PDF_DIR, f"DAS_{cnpj}_{timestamp}.pdf")
        
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        
        # Cabeçalho
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width / 2.0, height - 50, "Documento de Arrecadação do Simples Nacional (DAS)")
        c.setFont("Helvetica", 12)
        c.drawCentredString(width / 2.0, height - 70, "Microempreendedor Individual (MEI)")
        
        # Dados do Boleto
        y_pos = height - 120
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_pos, "Dados do Contribuinte:")
        c.setFont("Helvetica", 12)
        c.drawString(120, y_pos - 20, f"CNPJ: {cnpj}")
        c.drawString(120, y_pos - 40, f"Nome: {nome}")
        
        y_pos -= 80
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_pos, "Detalhes do Pagamento:")
        c.setFont("Helvetica", 12)
        c.drawString(120, y_pos - 20, "Período de Apuração: Mês Anterior")
        c.drawString(120, y_pos - 40, "Valor Total: R$ 70,00")
        
        # Calcula a data de vencimento (30 dias a partir de hoje)
        vencimento = (datetime.now() + timedelta(days=30)).strftime('%d/%m/%Y')
        c.drawString(120, y_pos - 60, f"Vencimento: {vencimento}")
        
        # Linha digitável e QR Code (simulados)
        y_pos -= 100
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_pos, "Linha Digitável (Simulada):")
        c.setFont("Helvetica", 10)
        c.drawString(120, y_pos - 20, "34191.00008 00000.000000 00000.000000 1 88880000000000")
        
        y_pos -= 60
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_pos, "QR Code para Pagamento (Simulado):")
        
        # Gera um QR Code fake (pode ser um link genérico ou texto)
        qr_data = f"SimulacaoDAS_{cnpj}_{vencimento}"
        qr = qrcode.make(qr_data)
        qr_img_buffer = BytesIO()
        qr.save(qr_img_buffer, format="PNG")
        qr_img_buffer.seek(0)
        
        # Desenha o QR Code no PDF
        c.drawImage(ImageReader(qr_img_buffer), 120, y_pos - 150, width=120, height=120)
        
        c.save() # Salva o PDF
        logging.info(f"PDF DAS gerado para {nome} ({cnpj}): {filename}")
        return filename
    except Exception as e:
        logging.error(f"Erro ao gerar PDF para {nome} ({cnpj}): {e}")
        return None

def enviar_whatsapp(client_data, pdf_path):
    """
    Envia a mensagem de WhatsApp com o PDF do DAS.
    Se TEST_MODE for True, apenas imprime a mensagem no console.
    """
    client_name = client_data['nome']
    client_whatsapp = client_data['whatsapp']
    client_cnpj = client_data['cnpj']

    if not NGROK_PUBLIC_URL:
        logging.error("Ngrok URL não disponível. Não é possível enviar WhatsApp com anexo.")
        return

    # Constrói a URL pública do PDF
    pdf_url = f"{NGROK_PUBLIC_URL}/pdfs/{os.path.basename(pdf_path)}"

    # Corpo da mensagem com quebras de linha corretas
    message_body = (
    f"Olá, {client_name}!\n"
    "Segue em anexo o Documento de Arrecadação do Simples Nacional (DAS) referente ao seu MEI.\n"
    "Por favor, verifique o documento e realize o pagamento até a data de vencimento.\n"
    "Qualquer dúvida, estou à disposição.\n"
    "Atenciosamente,\n"
    "Seu Contador Franklin"
)

    if TEST_MODE:
        logging.info(f"--- MODO DE TESTE ---")
        logging.info(f"Simulando envio para {client_name} ({client_whatsapp}):")
        logging.info(f"Mensagem: {message_body}")
        logging.info(f"Anexo PDF: {pdf_url}")
        logging.info(f"--------------------")
    else:
        try:
            # Envia a mensagem com o anexo PDF
            message = TWILIO_CLIENT.messages.create(
                from_=TWILIO_FROM_WHATSAPP,
                to=f'whatsapp:{client_whatsapp}',
                body=message_body,
                media_url=[pdf_url] # Anexa o PDF
            )
            logging.info(f"Mensagem enviada para {client_name} ({client_whatsapp}). SID: {message.sid}")
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem para {client_name} ({client_whatsapp}): {e}")

def enviar_das_diario():
    """
    Função principal que orquestra a leitura dos clientes,
    geração dos PDFs e envio das mensagens.
    """
    logging.info("Iniciando processo de envio diário de DAS MEI...")
    clientes = ler_clientes()
    if not clientes:
        logging.warning("Nenhum cliente encontrado na planilha. Encerrando.")
        return

    for cliente in clientes:
        pdf_path = gerar_pdf_das(cliente['cnpj'], cliente['nome'])
        if pdf_path:
            enviar_whatsapp(cliente, pdf_path)
            # Opcional: remover o PDF após o envio (se não precisar manter)
            # os.remove(pdf_path)
            # logging.info(f"PDF {pdf_path} removido após envio.")
        else:
            logging.error(f"Não foi possível gerar PDF para {cliente['nome']}.")
    logging.info("Processo de envio diário de DAS MEI concluído.")

# --- Funções de Inicialização ---
def run_flask():
    """
    Inicia o servidor Flask.
    """
    # Desativa o log de acesso padrão do Flask para não poluir o console
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    logging.info("Servidor Flask iniciado na porta 5000.")
    app.run(port=5000, debug=False, use_reloader=False)

def run_ngrok():
    """
    Inicia o Ngrok e obtém a URL pública.
    """
    global NGROK_PUBLIC_URL
    try:
        # Tenta se conectar ao Ngrok. Se já estiver rodando, reusa a sessão.
        # Se não, inicia uma nova.
        tunnel = ngrok.connect(5000)
        NGROK_PUBLIC_URL = tunnel.public_url
        logging.info(f"Ngrok iniciado. URL pública: {NGROK_PUBLIC_URL}")
        
        # Atualiza o webhook do Twilio Sandbox automaticamente
        # (Isso é um exemplo, você pode fazer manualmente se preferir)
        # logging.info("Atualizando webhook do Twilio Sandbox...")
        # TWILIO_CLIENT.api.accounts(TWILIO_SID).incoming_phone_numbers.list(
        #     sms_url=f"{NGROK_PUBLIC_URL}/webhook",
        #     sms_method="POST"
        # )
        # logging.info("Webhook do Twilio Sandbox atualizado.")

    except Exception as e:
        logging.error(f"Erro ao iniciar Ngrok: {e}")
        logging.error("Verifique se o Ngrok está configurado corretamente (ngrok config add-authtoken SEU_TOKEN).")
        logging.error("O script continuará, mas o envio de anexos pode falhar sem a URL pública.")

# --- Bloco Principal de Execução ---
if __name__ == '__main__':
    # Inicia o Ngrok em uma thread separada para não bloquear o Flask
    ngrok_thread = threading.Thread(target=run_ngrok)
    ngrok_thread.daemon = True # Garante que a thread Ngrok fecha com o programa principal
    ngrok_thread.start()

    # Dá um pequeno tempo para o Ngrok inicializar e obter a URL
    time.sleep(5) 

    # Inicia o Flask em uma thread separada
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True # Garante que a thread Flask fecha com o programa principal
    flask_thread.start()

    # Agendamento da tarefa diária
    # schedule.every().day.at("09:00").do(enviar_das_diario)
    logging.info("Agendamento diário para envio de DAS MEI configurado para 09:00.")
    logging.info("Pressione Ctrl+C para parar o script a qualquer momento.")
    
    while True:
     comando = input(">>> ").strip().lower()
     if comando == "enviar":
        enviar_das_diario()
     elif comando == "sair":
        break

    # Para testes, você pode chamar a função diretamente uma vez:
    # enviar_das_diario() 

    # Loop principal para executar as tarefas agendadas
    while True:
        schedule.run_pending()
        time.sleep(1)