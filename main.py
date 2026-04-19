import os
import telebot
import google.generativeai as genai
import json
import time
from flask import Flask, request
from threading import Lock

# ================= CONFIG E INICIALIZAÇÃO =================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '').strip()
GEMINI_KEY = os.environ.get('GEMINI_KEY', '').strip()
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '').strip()
ID_DO_MIMIR = 8039269030 # TROCA DEPOIS QUE O /id FUNCIONAR

print(f">>> INICIANDO VLAGOD...", flush=True)
print(f">>> TOKEN USADO: {TELEGRAM_TOKEN[:10]}...{TELEGRAM_TOKEN[-4:]}", flush=True)
print(f">>> WEBHOOK_URL: {WEBHOOK_URL}", flush=True)

if not TELEGRAM_TOKEN or not GEMINI_KEY or not WEBHOOK_URL:
    print(">>> ERRO FATAL: VARIAVEL DE AMBIENTE FALTANDO", flush=True)

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)

# Config Gemini
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print(">>> GEMINI CONFIGURADO", flush=True)
except Exception as e:
    print(f">>> ERRO GEMINI: {e}", flush=True)
    model = None

# ================= GERENCIAMENTO DE ARQUIVOS =================
lock = Lock()
PASTA_DADOS = '/tmp'
VIP_FILE = os.path.join(PASTA_DADOS, 'vips.json')
PERSONALIDADES_FILE = os.path.join(PASTA_DADOS, 'personalidades.json')
COOLDOWN_FILE = os.path.join(PASTA_DADOS, 'cooldowns.json')
CACHE_RESPOSTAS = {}
COOLDOWN_MIMIR = 30
COOLDOWN_VIP = 180

def carregar_json(nome_arquivo, padrao):
    try:
        with lock:
            if os.path.exists(nome_arquivo):
                with open(nome_arquivo, 'r') as f:
                    return json.load(f)
    except Exception as e:
        print(f">>> ERRO AO CARREGAR {nome_arquivo}: {e}", flush=True)
    return padrao

def salvar_json(nome_arquivo, dados):
    try:
        with lock:
            with open(nome_arquivo, 'w') as f:
                json.dump(dados, f)
    except Exception as e:
        print(f">>> ERRO AO SALVAR {nome_arquivo}: {e}", flush=True)

IDS_VIP = carregar_json(VIP_FILE, [ID_DO_MIMIR])
PERSONALIDADES = carregar_json(PERSONALIDADES_FILE, {})
COOLDOWNS = carregar_json(COOLDOWN_FILE, {})

def eh_vip(user_id): return user_id in IDS_VIP

# ================= WEBHOOK - COM PROTEÇÃO CONTRA 429 =================
@app.route("/")
def webhook_setup():
    try:
        info = bot.get_webhook_info()
        if info.url: # Se já tem webhook, não seta de novo
            print(f">>> WEBHOOK JA EXISTE: {info.url}", flush=True)
            return f"VLAGOD ONLINE - WEBHOOK JA SETADO: {info.url}", 200

        url_completa = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        sucesso = bot.set_webhook(url=url_completa)
        print(f">>> WEBHOOK SETADO PARA {url_completa}: {sucesso}", flush=True)
        return f"VLAGOD V3.6.2 ONLINE - WEBHOOK: {sucesso}", 200
    except Exception as e:
        print(f">>> ERRO AO SETAR WEBHOOK: {e}", flush=True)
        return f"ERRO: {e}", 500

@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        print(f">>> UPDATE RECEBIDO: {json_string[:500]}", flush=True)
        update = telebot.types.Update.de_json(json_string)

        # DEBUG BRUTO DO QUE CHEGOU
        if update.message:
            print(f">>> TIPO: {update.message.content_type}", flush=True)
            print(f">>> TEXTO: '{update.message.text}'", flush=True)
            print(f">>> ENTITIES: {update.message.entities}", flush=True)
        elif update.edited_message:
            print(f">>> EDITED_MSG: '{update.edited_message.text}'", flush=True)
        else:
            print(">>> UPDATE SEM MESSAGE", flush=True)

        bot.process_new_updates([update])
        print(">>> UPDATE PROCESSADO", flush=True)
        return "!", 200
    except Exception as e:
        print(f">>> CRASH NO WEBHOOK: {e}", flush=True)
        return "!", 200

# ================= HANDLERS - COMANDOS PRIMEIRO =================
@bot.message_handler(commands=['id'])
def pegar_id(message):
    try:
        print(f">>> /id chamado por {message.from_user.id}", flush=True)
        bot.reply_to(message, f"Teu ID: `{message.from_user.id}`", parse_mode='Markdown')
    except Exception as e:
        print(f">>> ERRO NO /id: {e}", flush=True)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    try:
        user_id = message.from_user.id
        print(f">>> /start por {user_id}", flush=True)
        if not eh_vip(user_id):
            print(f">>> {user_id} NAO EH VIP", flush=True)
            return
        bot.reply_to(message, "VLAGOD V3.6.2 ONLINE. Manda a letra, Mimir.")
    except Exception as e:
        print(f">>> ERRO NO /start: {e}", flush=True)

@bot.message_handler(commands=['debug'])
def debug(message):
    try:
        user_id = message.from_user.id
        if user_id!= ID_DO_MIMIR: return
        info = f"Token: {TELEGRAM_TOKEN[:10]}...\nWebhook: {WEBHOOK_URL}\nVIPs: {IDS_VIP}\nTeu ID: {user_id}"
        bot.reply_to(message, f"```{info}```", parse_mode='Markdown')
    except Exception as e:
        print(f">>> ERRO NO /debug: {e}", flush=True)

# ================= HANDLER GERAL - POR ÚLTIMO =================
@bot.message_handler(content_types=['text'])
def responder_geral(message):
    try:
        user_id = message.from_user.id
        print(f">>> MSG NORMAL DE {user_id}: {message.text}", flush=True)
        if not eh_vip(user_id):
            print(f">>> {user_id} NAO EH VIP - IGNORADO", flush=True)
            return

        # Checa Cooldown
        agora = time.time()
        cooldown = COOLDOWN_MIMIR if user_id == ID_DO_MIMIR else COOLDOWN_VIP
        if agora - COOLDOWNS.get(str(user_id), 0) < cooldown:
            print(f">>> {user_id} EM COOLDOWN", flush=True)
            return

        # Checa Cache
        texto = message.text
        if texto in CACHE_RESPOSTAS:
            bot.reply_to(message, CACHE_RESPOSTAS[texto])
            return

        # Chama Gemini
        prompt = PERSONALIDADES.get(str(user_id), "Responde de forma direta e sarcástica.")
        prompt += f"\n\nPergunta: {texto}"
        resposta = call_gemini(prompt)

        bot.reply_to(message, resposta)
        CACHE_RESPOSTAS[texto] = resposta
        COOLDOWNS[str(user_id)] = agora
        salvar_json(COOLDOWN_FILE, COOLDOWNS)
        print(f">>> RESPONDI {user_id}", flush=True)

    except Exception as e:
        print(f">>> ERRO NO RESPONDER_GERAL: {e}", flush=True)
        try:
            bot.reply_to(message, "Buguei.")
        except:
            pass

if __name__ == "__main__":
    print(">>> RODANDO LOCAL", flush=True)
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
