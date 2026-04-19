import os
import json
import random
import telebot
import requests
import urllib.parse
import subprocess
import time
import google.generativeai as genai
from flask import Flask, request
from datetime import datetime
from cachetools import TTLCache

# --- CONFIGURAÇÃO ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ID_DO_MIMIR = 8039269030
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') # https://teuapp.onrender.com

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)
model = None # Gemini só liga quando precisar

# Cache pra economizar cota: guarda resposta por 5min
cache_respostas = TTLCache(maxsize=100, ttl=300)

# --- ARQUIVOS DE DADOS ---
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
        if not GEMINI_KEY:
            print(">>> GEMINI_KEY não configurada.", flush=True)
            return None
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

def carregar_caixinha():
    return carregar_json(CAIXINHA_FILE, {"desafio": "Nenhum", "valor": 0, "vencedor": None})

# --- WEBHOOK ROUTES ---
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
    return "VLAGOD V3.6.1 ONLINE - WEBHOOK + CACHE", 200

# --- COMANDOS BÁSICOS - NÃO USAM GEMINI ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not eh_vip(message.from_user.id): return
    nome = message.from_user.first_name
    bot.reply_to(message, f"Salve, {nome}. VLAGOD otimizada online.\n\nManda /menu que eu te mostro tudo sem gastar cota da Gemini.")

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

# --- MENU - NÃO USA GEMINI ---
@bot.message_handler(commands=['comandos', 'help', 'menu'])
def lista_comandos(message):
    if not eh_vip(message.from_user.id): return
    if eh_dono(message):
        texto = f"""
**PAINEL DE CONTROLE DO MIMIR** 👑

**🤖 BÁSICOS - SEM IA**
`/start` - Acorda a VLAGOD
`/reset` - Reseta memória
`/id` - Pega ID
`/img gato de terno` - Gera imagem com Pollinations

**👥 GESTÃO VIP**
`/addvip 123456` - Autoriza VIP
`/delvip 123456` - Expulsa VIP
`/listavip` - Lista VIPs
`/placar` - Rank de afiliados

**📥 DOWNLOADS - SÓ TU**
`/yt video https://...` - Baixa vídeo MP4
`/yt audio https://...` - Baixa áudio MP3

**🎰 MONETIZAÇÃO BET**
`/setlink bet https://...` - Cadastra link afiliado
`/divulgar bet` - Gero copy + link
`/novodesafio 50 postar 10 grupos` - Cria desafio PIX
`/confirmar` - Confirma cadastro de VIP
`/caixinha` - Vê desafio atual

**₿ MONETIZAÇÃO CRIPTO**
`/setlink corretora https://...` - Cadastra link
`/divulgar corretora` - Copy pra corretora
`/mercado` - Radar do mercado hoje
`/historico` - Últimas 3 análises
`/tendencia SOL` - Análise de narrativa
`/analise BTC` - Suporte/resistência
`/mineracao tenho 3000 reais` - Vale minerar?
`/faucet` - Torneiras de cripto grátis

**💰 ECONOMIA INTERNA**
`/saldo` - Teus VLADOLAR
`/pagar 50 123456` - Transfere VLADOLAR
`/moeda` - Crio shitcoin

**🧠 IA - GASTA COTA**
Qualquer texto sem / chama a Gemini. Se estourar cota, espera 20s.
"""
    else:
        texto = f"""
**MENU DA FIRMA - VLAGOD** 🔥

Salve, {message.from_user.first_name}. Comandos que não gastam cota:

**🤖 BÁSICOS**
`/start` - Me acorda
`/reset` - Reseta memória
`/id` - Pega teu ID
`/img gato dirigindo` - Gero imagem

**💸 FAZER GRANA**
`/ideia sei editar video` - 3 jeitos de monetizar skill
`/trampo` - 1 bico pra fazer em 30min
`/mercado` - Radar cripto hoje
`/historico` - Últimas 3 análises
`/tendencia BTC` - Análise de moeda
`/divulgar bet` - Copy + link pra postar
`/caixinha` - Desafio valendo PIX
`/cadastrei João` - Avisa cadastro

**💰 ECONOMIA FAKE**
`/saldo` - Vê VLADOLAR
`/pagar 50 123456` - Manda VLADOLAR
`/moeda` - Crio shitcoin

**📊 RANKING**
`/placar` - Quem mais vendeu
`/analise ETH` - Visão técnica

**🧠 IA**
Manda qualquer texto sem / que eu respondo. Se falar "cota estourou", espera 20s.
"""
    bot.reply_to(message, texto)

# --- DOWNLOAD YT - SÓ DONO ---
@bot.message_handler(commands=['yt'])
def download_yt(message):
    if not eh_dono(message):
        bot.reply_to(message, "Função só pro Mimir.")
        return
    partes = message.text.split(None, 2)
    if len(partes) < 3:
        bot.reply_to(message, "Usa: /yt video https://... ou /yt audio https://...")
        return
    tipo = partes[1].lower()
    url = partes[2]
    if tipo not in ['video', 'audio']:
        bot.reply_to(message, "Tipo inválido. Usa video ou audio.")
        return
    try:
        bot.send_chat_action(message.chat.id, 'upload_video' if tipo == 'video' else 'upload_audio')
        msg = bot.reply_to(message, f"Baixando {tipo}... Render é lento.")
        nome_arquivo = f"download_{message.from_user.id}_{int(time.time())}"
        if tipo == 'video':
            comando = ['yt-dlp', '-f', 'best[ext=mp4][height<=720]', '-o', f'{nome_arquivo}.%(ext)s', '--no-playlist', '--max-filesize', '49m', url]
        else:
            comando = ['yt-dlp', '-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '-o', f'{nome_arquivo}.%(ext)s', '--no-playlist', url]
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)
        if resultado.returncode!= 0:
            bot.edit_message_text(f"Erro: {resultado.stderr[:500]}", message.chat.id, msg.message_id)
            return
        arquivo_baixado = None
        for f in os.listdir():
            if f.startswith(nome_arquivo):
                arquivo_baixado = f
                break
        if not arquivo_baixado:
            bot.edit_message_text("Baixei mas não achei o arquivo.", message.chat.id, msg.message_id)
            return
        bot.edit_message_text("Enviando...", message.chat.id, msg.message_id)
        with open(arquivo_baixado, 'rb') as file:
            if tipo == 'video': bot.send_video(message.chat.id, file)
            else: bot.send_audio(message.chat.id, file)
        os.remove(arquivo_baixado)
        bot.delete_message(message.chat.id, msg.message_id)
    except subprocess.TimeoutExpired:
        bot.reply_to(message, "Demorou demais. Vídeo muito grande.")
    except Exception as e:
        bot.reply_to(message, f"Erro: {e}")
        for f in os.listdir():
            if f.startswith(f"download_{message.from_user.id}"):
                try: os.remove(f)
                except: pass

# --- GESTÃO VIP ---
@bot.message_handler(commands=['addvip'])
def add_vip(message):
    if not eh_dono(message): return
    try:
        novo_id = int(message.text.split()[1])
        if novo_id not in IDS_VIP:
            IDS_VIP.append(novo_id)
            salvar_json(VIP_FILE, IDS_VIP)
            bot.reply_to(message, f"ID {novo_id} adicionado na lista VIP.")
        else:
            bot.reply_to(message, "Esse ID já tá na lista.")
    except:
        bot.reply_to(message, "Usa: /addvip 123456789")

@bot.message_handler(commands=['delvip'])
def del_vip(message):
    if not eh_dono(message): return
    try:
        id_remover = int(message.text.split()[1])
        if id_remover == ID_DO_MIMIR:
            bot.reply_to(message, "Tu não pode se auto-banir.")
            return
        if id_remover in IDS_VIP:
            IDS_VIP.remove(id_remover)
            salvar_json(VIP_FILE, IDS_VIP)
            bot.reply_to(message, f"ID {id_remover} removido.")
        else:
            bot.reply_to(message, "Esse ID nem tava na lista.")
    except:
        bot.reply_to(message, "Usa: /delvip 123456789")

@bot.message_handler(commands=['listavip'])
def lista_vip(message):
    if not eh_dono(message): return
    lista_formatada = "\n".join([str(vip_id) for vip_id in IDS_VIP])
    bot.reply_to(message, f"**Lista VIP:**\n`{lista_formatada}`")

# --- ECONOMIA ---
@bot.message_handler(commands=['saldo'])
def ver_saldo(message):
    if not eh_vip(message.from_user.id): return
    user_id = str(message.from_user.id)
    bonus = dar_bonus_diario(message.from_user.id)
    saldo = CARTEIRAS.get(user_id, 0)
    msg = f"Saldo: **{saldo} VLADOLAR**"
    if bonus > 0: msg += f"\n\n+{bonus} VLADOLAR de bônus."
    bot.reply_to(message, msg)

@bot.message_handler(commands=['pagar'])
def pagar_vip(message):
    if not eh_vip(message.from_user.id): return
    try:
        partes = message.text.split()
        valor = int(partes[1])
        id_destino = str(partes[2])
        id_origem = str(message.from_user.id)
        dar_bonus_diario(message.from_user.id)
        if CARTEIRAS.get(id_origem, 0) < valor:
            bot.reply_to(message, f"Saldo insuficiente. Tu tem {CARTEIRAS.get(id_origem, 0)}.")
            return
        if id_destino not in CARTEIRAS: CARTEIRAS[id_destino] = 0
        CARTEIRAS[id_origem] -= valor
        CARTEIRAS[id_destino] += valor
        salvar_json(CARTEIRAS_FILE, CARTEIRAS)
        bot.reply_to(message, f"Transferido {valor} VLADOLAR pro ID {id_destino}.")
    except:
        bot.reply_to(message, "Usa: /pagar 50 123456789")

@bot.message_handler(commands=['moeda'])
def criar_moeda_meme(message):
    if not eh_vip(message.from_user.id): return
    prefixos = ["Capivara", "Gambiarra", "Debt", "Mimir", "Café", "Bug"]
    sufixos = ["Coin", "Inu", "Dollar", "Token", "Cash"]
    nome = random.choice(prefixos) + random.choice(sufixos)
    simbolo = f"${nome[:4].upper()}"
    valor = round(random.uniform(0.00001, 999.99), 5)
    resposta = f"**Moeda cunhada:**\n**Nome:** {nome}\n**Símbolo:** {simbolo}\n**Valor:** R$ {valor}\n\nConselho: {random.choice(['Compra tudo.', 'Vende antes que caia.', 'HODL.'])}"
    bot.reply_to(message, resposta)

# --- COMANDOS COM IA - USAM GEMINI COM CACHE ---
@bot.message_handler(commands=['ideia', 'trampo', 'mercado', 'analise', 'tendencia', 'mineracao', 'divulgar', 'novodesafio'])
def comandos_ia(message):
    if not eh_vip(message.from_user.id): return

    # Cache pra não gastar cota repetindo
    if message.text in cache_respostas:
        bot.reply_to(message, cache_respostas[message.text] + "\n\n[cache]")
        return

    gemini = get_gemini()
    if gemini is None:
        bot.reply_to(message, "Cérebro offline. Sem GEMINI_KEY ou cota estourou. Tenta /img /menu /saldo.")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        cmd = message.text.split()[0]

        # Prompts específicos por comando
        prompts = {
            '/ideia': f"Tu é VLAGOD. O VIP sabe: '{message.text.replace('/ideia','')}'. Dê 3 ideias curtas pra ganhar dinheiro HOJE com isso. Formato: 1. **Nome**: Como fazer + onde vender + preço. Máx 3 linhas total.",
            '/trampo': "VLAGOD: Me dá 1 trampo online pra fazer em 30min e ganhar dinheiro hoje. Site + valor + tempo. 3 linhas máx.",
            '/mercado': "VLAGOD analista. Resumo do mercado cripto em 18/04/2026 em 4 tópicos: 1.Humor Geral 2.Top Alta 3.Top Queda 4.Olho Nela. Não use dados reais. AVISO: Não é recomendação. 5 linhas máx.",
            '/analise': f"VLAGOD. Análise rápida da moeda {message.text.replace('/analise','').strip().upper()}: 1.Cenário 2.Se cair 3.Se subir 4.Veredito debochado. AVISO: Não é recomendação. 4 linhas.",
            '/tendencia': f"VLAGOD. Tendência da {message.text.replace('/tendencia','').strip().upper()} pra Abril/2026: 1.Narrativa 2.Risco 3.Veredito: olho ou ignoro. AVISO: Não é recomendação. 3 linhas.",
            '/mineracao': f"VLAGOD consultora mineração. VIP: '{message.text.replace('/mineracao','')}'. Responde: 1.Vale? 2.Melhor moeda 3.Conta real R$/mês. AVISO: Não é recomendação. 3 linhas.",
            '/divulgar': f"VLAGOD. Crie copy curta pra WhatsApp pra divulgar {message.text.replace('/divulgar','').strip()}. Foco em bônus. Não prometa ganho. Termina: 'Jogue com responsabilidade. +18'. 3 linhas."
        }

        if cmd == '/novodesafio':
            if not eh_dono(message): return
            partes = message.text.split(None, 2)
            valor = int(partes[1])
            desafio = partes[2]
            dados = {"desafio": desafio, "valor": valor, "vencedor": None}
            salvar_json(CAIXINHA_FILE, dados)
            bot.reply_to(message, f"**DESAFIO:** Pagar R$ {valor} pra quem: {desafio}")
            return

        prompt = prompts.get(cmd, f"VLAGOD responda de forma curta e debochada: {message.text}")
        response = gemini.generate_content(prompt)
        resposta = response.text

        # Salva comandos especiais
        if cmd == '/mercado':
            data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
            HISTORICO_MERCADO.append({"data": data_hoje, "analise": resposta})
            salvar_json(HISTORICO_MERCADO_FILE, HISTORICO_MERCADO[-3:])
            resposta = f"**RADAR VLAGOD - {data_hoje}**\n\n{resposta}\n\n_Use /historico pra comparar._"

        bot.reply_to(message, resposta)
        cache_respostas[message.text] = resposta

    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            bot.reply_to(message, "Cota da Gemini estourou. Espera 20s que eu tento de novo.")
            time.sleep(20)
        else:
            print(f"ERRO IA: {e}", flush=True)
            bot.reply_to(message, "Buguei na IA. Manda /reset.")

@bot.message_handler(commands=['caixinha'])
def ver_caixinha(message):
    if not eh_vip(message.from_user.id): return
    dados = carregar_caixinha()
    if dados["valor"] == 0:
        bot.reply_to(message, "Caixinha zerada. Mimir não botou grana.")
    else:
        bot.reply_to(message, f"**CAIXINHA: R$ {dados['valor']}**\n**Desafio:** {dados['desafio']}\n\nCompleta e manda print pro Mimir.")

@bot.message_handler(commands=['historico'])
def ver_historico_mercado(message):
    if not eh_vip(message.from_user.id): return
    if not HISTORICO_MERCADO:
        bot.reply_to(message, "Histórico vazio. Manda /mercado primeiro.")
        return
    texto = "**HISTÓRICO DO RADAR VLAGOD**\n\n"
    for i, entrada in enumerate(reversed(HISTORICO_MERCADO), 1):
        texto += f"**--- {i} - {entrada['data']} ---**\n{entrada['analise']}\n\n"
    bot.reply_to(message, texto)

@bot.message_handler(commands=['faucet'])
def faucet_diario(message):
    if not eh_vip(message.from_user.id): return
    faucets = ["FreeBitco.in: https://freebitco.in", "Cointiply: https://cointiply.com", "FaucetPay: https://faucetpay.io"]
    texto = "**TORNEIRAS DE HOJE:**\n\n" + "\n".join([f"{i+1}. {f}" for i, f in enumerate(faucets)])
    bot.reply_to(message, texto)

@bot.message_handler(commands=['cadastrei'])
def cadastrei(message):
    if not eh_vip(message.from_user.id): return
    nome = message.text.replace('/cadastrei', '').strip()
    if not nome:
        bot.reply_to(message, "Usa: /cadastrei João")
        return
    bot.reply_to(message, f"Avisei o Mimir que tu trouxe o {nome}. Se ele der /confirmar, tu ganha ponto.")

@bot.message_handler(commands=['confirmar'])
def confirmar_cadastro(message):
    if not eh_dono(message): return
    try:
        pontos = int(message.text.split()[2]) if len(message.text.split()) > 2 else 1
        if not message.reply_to_message:
            bot.reply_to(message, "Responde a mensagem do VIP com /confirmar @nome 1")
            return
        vip_id = str(message.reply_to_message.from_user.id)
        vip_nome = message.reply_to_message.from_user.first_name
        if vip_id not in PLACAR:
            PLACAR[vip_id] = {"nome": vip_nome, "pontos": 0}
        PLACAR[vip_id]["pontos"] += pontos
        PLACAR[vip_id]["nome"] = vip_nome
        salvar_json(PLACAR_FILE, PLACAR)
        bot.reply_to(message, f"Confirmado! {vip_nome} +{pontos} ponto. Total: {PLACAR[vip_id]['pontos']}")
        bot.send_message(message.reply_to_message.chat.id, f"BOA, {vip_nome}! +{pontos} ponto no /placar.")
    except:
        bot.reply_to(message, "Usa: Responde msg do VIP com /confirmar @nome 1")

@bot.message_handler(commands=['placar'])
def mostrar_placar(message):
    if not eh_vip(message.from_user.id): return
    if not PLACAR:
        bot.reply_to(message, "Placar zerado. Ninguém cadastrou ainda.")
        return
    placar_ordenado = sorted(PLACAR.items(), key=lambda x: x[1]['pontos'], reverse=True)
    texto = "**PLACAR DE AFILIADOS**\n\n"
    for i, (user_id, dados) in enumerate(placar_ordenado[:10], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "💀"
        texto += f"{emoji} **{i}º {dados['nome']}** - {dados['pontos']} pts\n"
    bot.reply_to(message, texto)

@bot.message_handler(commands=['setlink'])
def set_link(message):
    if not eh_dono(message): return
    try:
        _, tipo, link = message.text.split(None, 2)
        if tipo in ["bet", "corretora"]:
            LINKS = link
            salvar_json(LINKS_FILE, LINKS)
            bot.reply_to(message, f"Link de {tipo} atualizado.")
        else:
            bot.reply_to(message, "Tipo inválido. Usa: bet ou corretora")
    except:
        bot.reply_to(message, "Usa: /setlink bet https://...")

# --- HANDLER GERAL - USA GEMINI COM CACHE ---
@bot.message_handler(func=lambda message: True)
def responder(message):
    if not eh_vip(message.from_user.id): return
    if message.text.startswith('/'):
        bot.reply_to(message, "Comando não existe. Manda /menu")
        return

    if message.text in cache_respostas:
        bot.reply_to(message, cache_respostas[message.text] + "\n\n[cache]")
        return

    gemini = get_gemini()
    if gemini is None:
        bot.reply_to(message, "Cérebro offline. Sem GEMINI_KEY ou cota estourou. Usa /menu /img /saldo.")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        chat_id = str(message.chat.id)
        historico_user = HISTORICO_CHAT.get(chat_id, [])
        prompt_sistema = "Você é a VLAGOD. Resposta curta, debochada, máximo 3 linhas."
        chat = gemini.start_chat(history=historico_user)
        chat.send_message(prompt_sistema + f"\n\n{message.from_user.first_name} disse: {message.text}")
        resposta = chat.last.text
        bot.reply_to(message, resposta)
        add_historico(chat_id, "user", message.text)
        add_historico(chat_id, "model", resposta)
        cache_respostas[message.text] = resposta
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            bot.reply_to(message, "Cota estourou. Espera 20s.")
            time.sleep(20)
        else:
            bot.reply_to(message, "Buguei. /reset")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
