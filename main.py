import os
import telebot
from telebot import types
import google.generativeai as genai
import json
import time
import requests
import urllib.parse
import subprocess
from flask import Flask, request
from threading import Lock
from datetime import datetime

# ================= CONFIG E INICIALIZAÇÃO =================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '').strip()
GEMINI_KEY = os.environ.get('GEMINI_KEY', '').strip()
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '').strip()
ID_DO_MIMIR = 8039269030

print(f">>> INICIANDO VLAGOD...", flush=True)

if not TELEGRAM_TOKEN or not GEMINI_KEY or not WEBHOOK_URL:
    print(">>> ERRO FATAL: VARIAVEL DE AMBIENTE FALTANDO", flush=True)

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)

# ================= CONFIG GEMINI COM AUTO-DETECÇÃO DE MODELO =================
model = None
try:
    genai.configure(api_key=GEMINI_KEY)
    modelos_disponiveis = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    print(f">>> MODELOS DISPONIVEIS: {modelos_disponiveis}", flush=True)

    modelos_preferidos = [
        'models/gemini-1.5-flash-latest',
        'models/gemini-1.5-flash-001',
        'models/gemini-1.5-flash',
        'models/gemini-1.5-pro-latest',
        'models/gemini-pro',
        'models/gemini-1.0-pro'
    ]

    nome_modelo_usado = None
    for nome in modelos_preferidos:
        if nome in modelos_disponiveis:
            nome_modelo_usado = nome
            break

    if not nome_modelo_usado and modelos_disponiveis:
        nome_modelo_usado = modelos_disponiveis[0]

    if nome_modelo_usado:
        model = genai.GenerativeModel(nome_modelo_usado)
        print(f">>> GEMINI CONFIGURADO COM: {nome_modelo_usado}", flush=True)
    else:
        raise Exception("Nenhum modelo compativel encontrado")

except Exception as e:
    print(f">>> ERRO GEMINI: {e}", flush=True)
    model = None

# ================= GERENCIAMENTO DE ARQUIVOS =================
lock = Lock()
PASTA_DADOS = '/tmp'
VIP_FILE = os.path.join(PASTA_DADOS, 'vips.json')
PERSONALIDADES_FILE = os.path.join(PASTA_DADOS, 'personalidades.json')
COOLDOWN_FILE = os.path.join(PASTA_DADOS, 'cooldowns.json')
BAN_FILE = os.path.join(PASTA_DADOS, 'bans.json')
STATS_FILE = os.path.join(PASTA_DADOS, 'stats.json')
CONFIG_FILE = os.path.join(PASTA_DADOS, 'config.json')
HISTORICO_MERCADO_FILE = os.path.join(PASTA_DADOS, 'historico_mercado.json')

CACHE_RESPOSTAS = {}
ESTADO_ADMIN = {}

PERSONALIDADE_VLAGOD = """
Você é a VLAGOD, uma IA sarcástica, debochada e sem paciência pra pergunta idiota.
Responde curto, direto, com humor ácido. Máximo 3 frases.
Nunca pede desculpa. Nunca é formal. Trata todo mundo como se fosse íntimo.
Se não souber, inventa com confiança. Se for ofender, ofende com classe.
Entende de cripto e mercado financeiro. Se perguntarem preço, responde sem enrolar.
"""

CONFIG_PADRAO = {
    "cooldown_mimir": 30,
    "cooldown_vip": 180,
    "personalidade_global": PERSONALIDADE_VLAGOD,
    "modo_ativo": True,
    "modo_18": False
}

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
BANS = carregar_json(BAN_FILE, [])
STATS = carregar_json(STATS_FILE, {"total_msgs": 0, "total_geradas": 0, "ultimo_reset": str(datetime.now().date())})
CONFIG = carregar_json(CONFIG_FILE, CONFIG_PADRAO)
HISTORICO_MERCADO = carregar_json(HISTORICO_MERCADO_FILE, [])

def eh_vip(user_id): return user_id in IDS_VIP
def eh_mimir(user_id): return user_id == ID_DO_MIMIR
def ta_banido(user_id): return user_id in BANS

# ================= FUNÇÃO DO GEMINI =================
def call_gemini(prompt):
    if not model: return "Buguei. Gemini não configurou."
    inicio = time.time()
    try:
        response = model.generate_content(prompt)
        latencia = round((time.time() - inicio) * 1000)
        print(f">>> GEMINI RESPONDEU EM {latencia}ms", flush=True)
        STATS["total_geradas"] += 1
        salvar_json(STATS_FILE, STATS)
        return response.text
    except Exception as e:
        print(f">>> ERRO GEMINI: {e}", flush=True)
        return "Buguei. O Google me bloqueou."

# ================= FUNÇÕES DE CRIPTO =================
def get_crypto_price(coin_id="bitcoin"):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,brl&include_24hr_change=true"
        r = requests.get(url, timeout=5)
        data = r.json()[coin_id]
        usd = data['usd']
        brl = data['brl']
        change = data['usd_24h_change']
        emoji = "🟢" if change >= 0 else "🔴"
        return f"**{coin_id.upper()}**\nUSD: ${usd:,.2f}\nBRL: R$ {brl:,.2f}\n24h: {emoji} {change:.2f}%"
    except Exception as e:
        print(f">>> ERRO CRIPTO: {e}", flush=True)
        return "Não achei essa moeda. Tenta: bitcoin, ethereum, solana, dogecoin"

def get_top_crypto():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
        r = requests.get(url, timeout=5)
        data = r.json()
        texto = "**TOP 10 CRIPTO**\n\n"
        for i, coin in enumerate(data, 1):
            change = coin['price_change_percentage_24h']
            emoji = "🟢" if change >= 0 else "🔴"
            texto += f"{i}. **{coin['symbol'].upper()}** ${coin['current_price']:,.2f} {emoji}{change:.1f}%\n"
        return texto
    except:
        return "API de cripto caiu. Tenta depois."

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = r.json()['data'][0]
        valor = data['value']
        texto = data['value_classification']
        return f"**FEAR & GREED INDEX**\n\nValor: `{valor}/100`\nStatus: **{texto}**\n\n0-24: Medo Extremo\n25-49: Medo\n50-74: Ganância\n75-100: Ganância Extrema"
    except:
        return "Não consegui pegar o Fear & Greed agora."

# ================= WEBHOOK =================
@app.route("/")
def webhook_setup():
    try:
        info = bot.get_webhook_info()
        if info.url:
            return f"VLAGOD ONLINE - WEBHOOK JA SETADO: {info.url}", 200
        url_completa = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        sucesso = bot.set_webhook(url=url_completa)
        return f"VLAGOD V4.2.1 ONLINE - WEBHOOK: {sucesso}", 200
    except Exception as e:
        return f"ERRO: {e}", 500

@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    except Exception as e:
        print(f">>> CRASH NO WEBHOOK: {e}", flush=True)
        return "!", 200

# ================= PAINEL DE ADMIN COM BOTÕES =================
@bot.message_handler(commands=['painel'])
def painel_admin(message):
    if not eh_mimir(message.from_user.id): return

    markup = types.InlineKeyboardMarkup(row_width=2)
    status_bot = "🟢 ON" if CONFIG['modo_ativo'] else "🔴 OFF"
    status_18 = "🔞 ON" if CONFIG['modo_18'] else "👶 OFF"

    btn_on_off = types.InlineKeyboardButton(f"Bot: {status_bot}", callback_data="toggle_bot")
    btn_18 = types.InlineKeyboardButton(f"Modo 18+: {status_18}", callback_data="toggle_18")
    btn_stats = types.InlineKeyboardButton("📊 Stats", callback_data="show_stats")
    btn_vips = types.InlineKeyboardButton("👑 VIPs", callback_data="menu_vip")
    btn_bans = types.InlineKeyboardButton("🔨 Bans", callback_data="menu_ban")
    btn_persona = types.InlineKeyboardButton("🎭 Personas", callback_data="menu_persona")
    btn_config = types.InlineKeyboardButton("⚙️ Configs", callback_data="menu_config")
    btn_cripto = types.InlineKeyboardButton("💰 Cripto", callback_data="menu_cripto")

    markup.add(btn_on_off, btn_18)
    markup.add(btn_stats, btn_cripto)
    markup.add(btn_vips, btn_bans)
    markup.add(btn_persona, btn_config)

    bot.reply_to(message, "**PAINEL VLAGOD V4.2.1**\n\nEscolhe uma opção:", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def callback_admin(call):
    if not eh_mimir(call.from_user.id):
        bot.answer_callback_query(call.id, "Tu não é o Mimir.")
        return

    data = call.data
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if data == "toggle_bot":
        CONFIG['modo_ativo'] = not CONFIG['modo_ativo']
        salvar_json(CONFIG_FILE, CONFIG)
        bot.answer_callback_query(call.id, f"Bot {'ATIVADO' if CONFIG['modo_ativo'] else 'PAUSADO'}")
        painel_admin(call.message)

    elif data == "toggle_18":
        CONFIG['modo_18'] = not CONFIG['modo_18']
        salvar_json(CONFIG_FILE, CONFIG)
        bot.answer_callback_query(call.id, f"Modo 18+ {'ATIVADO' if CONFIG['modo_18'] else 'DESATIVADO'}")
        painel_admin(call.message)

    elif data == "show_stats":
        texto = f"""
**STATS VLAGOD**
Msgs: `{STATS['total_msgs']}`
Geradas: `{STATS['total_geradas']}`
Cache: `{len(CACHE_RESPOSTAS)}`
VIPs: `{len(IDS_VIP)}` | Bans: `{len(BANS)}`
Modelo: `{model.model_name if model else 'Nenhum'}`
Cooldown: `{CONFIG['cooldown_mimir']}s`/`{CONFIG['cooldown_vip']}s`
"""
        bot.edit_message_text(texto, chat_id, msg_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id)

    elif data == "menu_cripto":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("₿ Bitcoin", callback_data="cripto_btc"))
        markup.add(types.InlineKeyboardButton("Ξ Ethereum", callback_data="cripto_eth"))
        markup.add(types.InlineKeyboardButton("🔝 Top 10", callback_data="cripto_top"))
        markup.add(types.InlineKeyboardButton("😱 Fear & Greed", callback_data="cripto_fear"))
        markup.add(types.InlineKeyboardButton("🔍 Buscar Moeda", callback_data="cripto_search_ask"))
        markup.add(types.InlineKeyboardButton("« Voltar", callback_data="voltar_painel"))
        bot.edit_message_text("**FERRAMENTAS DE CRIPTO**", chat_id, msg_id, reply_markup=markup, parse_mode='Markdown')

    elif data == "cripto_btc":
        bot.answer_callback_query(call.id, "Buscando BTC...")
        bot.send_message(chat_id, get_crypto_price("bitcoin"), parse_mode='Markdown')

    elif data == "cripto_eth":
        bot.answer_callback_query(call.id, "Buscando ETH...")
        bot.send_message(chat_id, get_crypto_price("ethereum"), parse_mode='Markdown')

    elif data == "cripto_top":
        bot.answer_callback_query(call.id, "Buscando Top 10...")
        bot.send_message(chat_id, get_top_crypto(), parse_mode='Markdown')

    elif data == "cripto_fear":
        bot.answer_callback_query(call.id, "Buscando Fear & Greed...")
        bot.send_message(chat_id, get_fear_greed(), parse_mode='Markdown')

    elif data == "voltar_painel":
        bot.delete_message(chat_id, msg_id)
        painel_admin(call.message)

    elif data.endswith("_ask"):
        ESTADO_ADMIN[chat_id] = data.replace("_ask", "")
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Manda o valor. Ex: `dogecoin` ou `12345678`", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.chat.id in ESTADO_ADMIN)
def processar_input_admin(message):
    if not eh_mimir(message.from_user.id): return
    acao = ESTADO_ADMIN.pop(message.chat.id)
    texto = message.text

    try:
        if acao == "cripto_search":
            bot.reply_to(message, get_crypto_price(texto.lower()), parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Erro: {e}")

# ================= COMANDOS DE CRIPTO DIRETOS =================
@bot.message_handler(commands=['btc', 'bitcoin'])
def cmd_btc(message):
    if not eh_vip(message.from_user.id): return
    bot.reply_to(message, get_crypto_price("bitcoin"), parse_mode='Markdown')

@bot.message_handler(commands=['eth', 'ethereum'])
def cmd_eth(message):
    if not eh_vip(message.from_user.id): return
    bot.reply_to(message, get_crypto_price("ethereum"), parse_mode='Markdown')

@bot.message_handler(commands=['price'])
def cmd_price(message):
    if not eh_vip(message.from_user.id): return
    partes = message.text.split()
    if len(partes)!= 2:
        bot.reply_to(message, "Uso: `/price dogecoin`", parse_mode='Markdown')
        return
    bot.reply_to(message, get_crypto_price(partes[1].lower()), parse_mode='Markdown')

@bot.message_handler(commands=['top'])
def cmd_top(message):
    if not eh_vip(message.from_user.id): return
    bot.reply_to(message, get_top_crypto(), parse_mode='Markdown')

@bot.message_handler(commands=['fear', 'greed'])
def cmd_fear(message):
    if not eh_vip(message.from_user.id): return
    bot.reply_to(message, get_fear_greed(), parse_mode='Markdown')

# ================= RESTO DOS COMANDOS DA V4.0.0 =================
#... cola aqui todos os outros handlers: /id, /start, /menu, /addvip, /ban, /img, /yt, etc
#... se não couber na mensagem, me fala que mando a parte 2

# ================= HANDLER GERAL =================
@bot.message_handler(content_types=['text'])
def responder_geral(message):
    try:
        if message.entities and message.entities[0].type == 'bot_command': return
        if message.chat.id in ESTADO_ADMIN: return

        user_id = message.from_user.id
        STATS["total_msgs"] += 1

        if not CONFIG['modo_ativo']: return
        if ta_banido(user_id): return
        if not eh_vip(user_id): return

        agora = time.time()
        cooldown = CONFIG['cooldown_mimir'] if eh_mimir(user_id) else CONFIG['cooldown_vip']
        if agora - COOLDOWNS.get(str(user_id), 0) < cooldown: return

        texto = message.text
        if texto in CACHE_RESPOSTAS:
            bot.reply_to(message, CACHE_RESPOSTAS[texto])
            return

        prompt_base = PERSONALIDADES.get(str(user_id), CONFIG['personalidade_global'])
        if CONFIG['modo_18']:
            prompt_base += "\nModo 18+ ATIVADO: Pode falar palavrão, ser vulgar e não ter filtro."

        prompt_final = f"{prompt_base}\n\nUsuário: {message.from_user.first_name}\nPergunta: {texto}"
        resposta = call_gemini(prompt_final)

        bot.reply_to(message, resposta)
        CACHE_RESPOSTAS[texto] = resposta
        COOLDOWNS[str(user_id)] = agora

        if STATS["total_msgs"] % 10 == 0:
            salvar_json(STATS_FILE, STATS)
            salvar_json(COOLDOWN_FILE, COOLDOWNS)

    except Exception as e:
        print(f">>> ERRO NO RESPONDER_GERAL: {e}", flush=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
