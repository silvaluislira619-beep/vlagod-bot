import os
import json
import random
import telebot
import requests
import urllib.parse
import subprocess
import google.generativeai as genai
from flask import Flask, request
from datetime import datetime

# --- CONFIGURAÇÃO ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ID_DO_MIMIR = 8039269030
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') # URL do teu Render: https://teuapp.onrender.com

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)
model = None # Gemini só liga quando precisar

# --- ARQUIVOS ---
VIP_FILE = 'vips.json'
CARTEIRAS_FILE = 'carteiras.json'
LINKS_FILE = 'links_afiliados.json'
PLACAR_FILE = 'placar_vips.json'
CAIXINHA_FILE = 'caixinha.json'
HISTORICO_MERCADO_FILE = 'historico_mercado.json'
HISTORICO_CHAT_FILE = 'historico_chat.json'

def carregar_json(file, default):
    try:
        with open(file, 'r') as f: return json.load(f)
    except: return default

def salvar_json(file, data):
    with open(file, 'w') as f: json.dump(data, f)

IDS_VIP = carregar_json(VIP_FILE, [ID_DO_MIMIR])
CARTEIRAS = carregar_json(CARTEIRAS_FILE, {})
LINKS = carregar_json(LINKS_FILE, {"bet": "SEU_LINK_BET_AQUI", "corretora": "SEU_LINK_BINANCE_AQUI"})
PLACAR = carregar_json(PLACAR_FILE, {})
HISTORICO_MERCADO = carregar_json(HISTORICO_MERCADO_FILE, [])
HISTORICO_CHAT = carregar_json(HISTORICO_CHAT_FILE, {})

# --- GEMINI LAZY LOAD ---
def get_gemini():
    global model
    if model is None:
        if not GEMINI_KEY: return None
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            print(">>> Gemini ligada sob demanda.", flush=True)
        except Exception as e:
            print(f">>> ERRO GEMINI: {e}", flush=True)
            return None
    return model

# --- FUNÇÕES AUX ---
def eh_vip(user_id): return user_id in IDS_VIP
def eh_dono(message): return message.from_user.id == ID_DO_MIMIR

def add_historico(chat_id, role, text):
    chat_id = str(chat_id)
    if chat_id not in HISTORICO_CHAT: HISTORICO_CHAT[chat_id] = []
    HISTORICO_CHAT[chat_id].append({"role": role, "parts": [text]})
    HISTORICO_CHAT[chat_id] = HISTORICO_CHAT[chat_id][-6:] # Só últimas 6 msgs
    salvar_json(HISTORICO_CHAT_FILE, HISTORICO_CHAT)

def dar_bonus_diario(user_id):
    user_id = str(user_id)
    if user_id not in CARTEIRAS:
        CARTEIRAS[user_id] = 100
        salvar_json(CARTEIRAS_FILE, CARTEIRAS)
        return 100
    return 0

# --- WEBHOOK ROUTE ---
@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + '/' + TELEGRAM_TOKEN)
    return "VLAGOD V3.6 ONLINE - WEBHOOK MODE", 200

# --- COMANDOS LEVES - NÃO USAM GEMINI ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not eh_vip(message.from_user.id): return
    nome = message.from_user.first_name
    bot.reply_to(message, f"Salve, {nome}. VLAGOD otimizada online.\n\nManda /menu que eu te mostro o que faço sem gastar cota.")

@bot.message_handler(commands=['reset'])
def reset_memoria(message):
    if not eh_vip(message.from_user.id): return
    chat_id = str(message.chat.id)
    if chat_id in HISTORICO_CHAT:
        del HISTORICO_CHAT[chat_id]
        salvar_json(HISTORICO_CHAT_FILE, HISTORICO_CHAT)
    bot.reply_to(message, "Memória zerada. Gastei menos RAM agora.")

@bot.message_handler(commands=['id'])
def pegar_id(message):
    bot.reply_to(message, f"Teu ID: `{message.from_user.id}`")

@bot.message_handler(commands=['img'])
def gerar_imagem(message):
    if not eh_vip(message.from_user.id): return
    prompt_img = message.text.replace('/img', '').strip()
    if not prompt_img:
        bot.reply_to(message, "Manda: /img um capivara de terno")
        return
    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        prompt_encoded = urllib.parse.quote(prompt_img)
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=768&height=768&nologo=true"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            bot.send_photo(message.chat.id, response.content, caption=f"Pollinations: {prompt_img}")
        else:
            bot.reply_to(message, "Pollinations caiu ou tu pediu coisa proibida.")
    except Exception as e:
        bot.reply_to(message, "Bug na tinta. Tenta de novo.")

# --- COMANDOS PESADOS - USAM GEMINI SÓ QUANDO CHAMAR ---
@bot.message_handler(func=lambda message: True)
def responder(message):
    if not eh_vip(message.from_user.id): return
    # Comandos que não precisam de IA saem daqui
    if message.text.startswith('/'):
        bot.reply_to(message, "Comando não reconhecido. Usa /menu pra ver a lista.")
        return

    gemini = get_gemini()
    if gemini is None:
        bot.reply_to(message, "Cérebro offline. Sem GEMINI_KEY ou estourou cota. Só comando manual: /menu /img /yt /saldo")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        chat_id = str(message.chat.id)
        historico_user = HISTORICO_CHAT.get(chat_id, [])

        if eh_dono(message):
            prompt_sistema = "Você é a VLAGOD, IA caótica do Mimir. Resposta curta, debochada, genial. Máximo 3 linhas."
        else:
            prompt_sistema = "Você é a VLAGOD. VIP falando. Seja debochada, curta, trate como recruta. Máximo 3 linhas."

        chat = gemini.start_chat(history=historico_user)
        chat.send_message(prompt_sistema + f"\n\n{message.from_user.first_name} disse: {message.text}")
        resposta = chat.last.text

        bot.reply_to(message, resposta)
        add_historico(chat_id, "user", message.text)
        add_historico(chat_id, "model", resposta)

    except Exception as e:
        print(f"ERRO GEMINI: {e}", flush=True)
        if "quota" in str(e).lower() or "429" in str(e):
            bot.reply_to(message, "Estourei a cota da Gemini. Espera 1min. Usa /img que não gasta cota.")
        else:
            bot.reply_to(message, "Buguei. Manda /reset.")

# --- COLA OS OUTROS COMANDOS AQUI: /menu, /yt, /saldo, /pagar, /addvip etc ---
# Usei só os principais pra não ficar gigante. O resto do código V3.4 funciona igual.
# Só lembra de trocar todos `model` por `get_gemini()` nos comandos que usam IA

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
