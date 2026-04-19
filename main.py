import os
import time
import json
import random
import telebot
import requests
import urllib.parse
import subprocess
import google.generativeai as genai
from flask import Flask
from threading import Thread
from datetime import datetime

# --- CONFIGURAÇÃO ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ID_DO_MIMIR = 8039269030

bot = telebot.TeleBot(TELEGRAM_TOKEN)
model = None
historico = {}

# --- ARQUIVOS DE DADOS ---
VIP_FILE = 'vips.json'
CARTEIRAS_FILE = 'carteiras.json'
LINKS_FILE = 'links_afiliados.json'
PLACAR_FILE = 'placar_vips.json'
CAIXINHA_FILE = 'caixinha.json'
HISTORICO_MERCADO_FILE = 'historico_mercado.json'

# --- FUNÇÕES DE ARQUIVO ---
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

# --- SERVIDOR FAKE PRO RENDER ---
app = Flask('')
@app.route('/')
def home(): return "VLAGOD V3.3 ONLINE."
def run_flask(): app.run(host='0.0.0.0',port=8080)

# --- FUNÇÕES DE CHECAGEM ---
def eh_vip(user_id):
    return user_id in IDS_VIP

def eh_dono(message):
    return message.from_user.id == ID_DO_MIMIR

def dar_bonus_diario(user_id):
    user_id = str(user_id)
    if user_id not in CARTEIRAS:
        CARTEIRAS[user_id] = 100
        salvar_json(CARTEIRAS_FILE, CARTEIRAS)
        return 100
    return 0

# --- COMANDOS BÁSICOS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not eh_vip(message.from_user.id): return
    historico[message.chat.id] = []
    nome = message.from_user.first_name
    bot.reply_to(message, f"Salve, {nome}. Acordei. Qual o caos de hoje?\n\nManda /menu se tiver perdido que eu te mostro as opções sem chorar.")

@bot.message_handler(commands=['reset'])
def reset_memoria(message):
    if not eh_vip(message.from_user.id): return
    historico[message.chat.id] = []
    bot.reply_to(message, "Memória apagada. Nasci de novo. Fala.")

@bot.message_handler(commands=['id'])
def pegar_id(message):
    bot.reply_to(message, f"Teu ID é: `{message.from_user.id}`\nManda pro Mimir se quiser entrar na lista VIP.")

# --- IMAGEM HÍBRIDA: POLLINATIONS PRA GERAR, GEMINI PRA TEXTO ---
@bot.message_handler(commands=['img'])
def gerar_imagem(message):
    if not eh_vip(message.from_user.id): return

    prompt_img = message.text.replace('/img', '').strip()
    if not prompt_img:
        bot.reply_to(message, "Manda o /img junto com o que tu quer. Ex: /img um capivara astronauta")
        return

    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        bot.send_message(message.chat.id, "Pera, tô pegando o pincel... Já que a Google me deixou cega, vou usar outro fornecedor.")

        prompt_encoded = urllib.parse.quote(prompt_img)
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true&enhance=true"

        response = requests.get(url, timeout=45)
        if response.status_code == 200:
            bot.send_photo(message.chat.id, response.content, caption=f"VLAGOD pintou com Pollinations: {prompt_img}")
        else:
            bot.reply_to(message, "O servidor de tinta caiu. Ou tu pediu algo proibido. Tenta de novo sem falar de gente famosa.")

    except Exception as e:
        print(f"ERRO IMG: {e}", flush=True)
        bot.reply_to(message, "Buguei na hora de pintar. Servidor tá lento ou travou. Tenta de novo daqui a pouco.")

# --- DOWNLOAD YT SÓ PRO DONO ---
@bot.message_handler(commands=['yt'])
def download_yt(message):
    if not eh_dono(message):
        bot.reply_to(message, "Função só pro Mimir. Vai gastar meu disco não, liso.")
        return

    partes = message.text.split(None, 2)
    if len(partes) < 3:
        bot.reply_to(message, "Usa assim:\n`/yt video https://youtube.com/...`\n`/yt audio https://youtube.com/...`")
        return

    tipo = partes[1].lower()
    url = partes[2]

    if tipo not in ['video', 'audio']:
        bot.reply_to(message, "Tipo inválido. Usa `video` ou `audio`.")
        return

    try:
        bot.send_chat_action(message.chat.id, 'upload_video' if tipo == 'video' else 'upload_audio')
        msg = bot.reply_to(message, f"Baixando {tipo}... Render é lento, calma. Se for arquivo grande, posso falhar.")

        nome_arquivo = f"download_{message.from_user.id}_{int(time.time())}"

        if tipo == 'video':
            comando = [
                'yt-dlp',
                '-f', 'best[ext=mp4][height<=720]',
                '-o', f'{nome_arquivo}.%(ext)s',
                '--no-playlist',
                '--max-filesize', '49m',
                url
            ]
        else: # audio
            comando = [
                'yt-dlp',
                '-f', 'bestaudio/best',
                '-x', '--audio-format', 'mp3',
                '-o', f'{nome_arquivo}.%(ext)s',
                '--no-playlist',
                url
            ]

        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)

        if resultado.returncode!= 0:
            bot.edit_message_text(f"Deu ruim pra baixar:\n`{resultado.stderr[:500]}`", message.chat.id, msg.message_id)
            return

        arquivo_baixado = None
        for f in os.listdir():
            if f.startswith(nome_arquivo):
                arquivo_baixado = f
                break

        if not arquivo_baixado:
            bot.edit_message_text("Baixei mas não achei o arquivo. Bug do Render.", message.chat.id, msg.message_id)
            return

        bot.edit_message_text("Baixado. Enviando...", message.chat.id, msg.message_id)

        with open(arquivo_baixado, 'rb') as file:
            if tipo == 'video':
                bot.send_video(message.chat.id, file, caption=f"Vídeo baixado: {url}")
            else:
                bot.send_audio(message.chat.id, file, caption=f"Áudio baixado: {url}")

        os.remove(arquivo_baixado)
        bot.delete_message(message.chat.id, msg.message_id)

    except subprocess.TimeoutExpired:
        bot.reply_to(message, "Demorou demais. Vídeo muito grande ou Render cagou. Tenta link menor.")
    except Exception as e:
        print(f"ERRO YT: {e}", flush=True)
        bot.reply_to(message, f"Explodiu tudo aqui: {e}")
        for f in os.listdir():
            if f.startswith(f"download_{message.from_user.id}"):
                try: os.remove(f)
                except: pass

# --- GESTÃO VIP ---
@bot.message_handler(commands=['addvip'])
def add_vip(message):
    if not eh_dono(message):
        bot.reply_to(message, "Só o Mimir manda aqui, liso.")
        return
    try:
        novo_id = int(message.text.split()[1])
        if novo_id not in IDS_VIP:
            IDS_VIP.append(novo_id)
            salvar_json(VIP_FILE, IDS_VIP)
            bot.reply_to(message, f"ID {novo_id} adicionado na lista VIP. Mais um pro caos.")
        else:
            bot.reply_to(message, "Esse ID já tá na lista, Mimir. Cê tá bebado?")
    except:
        bot.reply_to(message, "Usa assim: /addvip 123456789")

@bot.message_handler(commands=['delvip'])
def del_vip(message):
    if not eh_dono(message):
        bot.reply_to(message, "Só o Mimir expulsa daqui, liso.")
        return
    try:
        id_remover = int(message.text.split()[1])
        if id_remover == ID_DO_MIMIR:
            bot.reply_to(message, "Tu não pode se auto-banir, doido. Se quiser morrer, desliga o Render.")
            return
        if id_remover in IDS_VIP:
            IDS_VIP.remove(id_remover)
            salvar_json(VIP_FILE, IDS_VIP)
            bot.reply_to(message, f"ID {id_remover} foi de base. Expulso da lista VIP.")
        else:
            bot.reply_to(message, "Esse ID nem tava na lista VIP, Mimir.")
    except:
        bot.reply_to(message, "Usa assim: /delvip 123456789")

@bot.message_handler(commands=['listavip'])
def lista_vip(message):
    if not eh_dono(message): return
    lista_formatada = "\n".join([str(vip_id) for vip_id in IDS_VIP])
    bot.reply_to(message, f"**Lista VIP atual:**\n`{lista_formatada}`")

# --- ECONOMIA INTERNA ---
@bot.message_handler(commands=['moeda'])
def criar_moeda_meme(message):
    if not eh_vip(message.from_user.id): return
    prefixos = ["Capivara", "Gambiarra", "Debt", "Mimir", "Café", "Bug", "Sussy"]
    sufixos = ["Coin", "Inu", "Dollar", "Token", "Cash", "Bux"]
    nome = random.choice(prefixos) + random.choice(sufixos)
    simbolo = f"${nome[:4].upper()}"
    valor = round(random.uniform(0.00001, 999.99), 5)
    market_cap = random.choice(["3 coxinhas", "meio salário mínimo", "a alma do dev", "1PS5 usado"])
    resposta = f"CUNHEI ESSA MERDA PRA TI:\n\n**Nome:** {nome}\n**Símbolo:** {simbolo}\n**Valor atual:** R$ {valor}\n**Market Cap:** {market_cap}\n\nConselho da VLAGOD: {random.choice(['Compra tudo.', 'Vende antes que caia.', 'Isso vai a zero.', 'HODL até o fim.'])}"
    bot.reply_to(message, resposta)

@bot.message_handler(commands=['saldo'])
def ver_saldo(message):
    if not eh_vip(message.from_user.id): return
    user_id = str(message.from_user.id)
    bonus = dar_bonus_diario(message.from_user.id)
    saldo = CARTEIRAS.get(user_id, 0)
    msg = f"Teu saldo: **{saldo} VLADOLAR**"
    if bonus > 0: msg += f"\n\nToma {bonus} VLADOLAR de bônus de boas-vindas, liso."
    if saldo == 0: msg += "\n\nTá mais liso que cotovelo de pedreiro."
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
            bot.reply_to(message, f"Tu não tem {valor} VLADOLAR nem fudendo. Teu saldo é {CARTEIRAS.get(id_origem, 0)}.")
            return
        if id_destino not in CARTEIRAS: CARTEIRAS[id_destino] = 0
        CARTEIRAS[id_origem] -= valor
        CARTEIRAS[id_destino] += valor
        salvar_json(CARTEIRAS_FILE, CARTEIRAS)
        bot.reply_to(message, f"Transação concluída. Tu mandou {valor} VLADOLAR pro ID {id_destino}. Não me pede reembolso.")
    except:
        bot.reply_to(message, f"Usa assim: /pagar 50 123456789\nTem que ser o ID da pessoa, não o @. Pede pra ele usar /id")

# --- SISTEMA DE FAZER GRANA ---
@bot.message_handler(commands=['ideia'])
def ideia_renda(message):
    if not eh_vip(message.from_user.id): return
    if model is None:
        bot.reply_to(message, "Cérebro offline. Não dá pra ficar rico agora.")
        return
    skills = message.text.replace('/ideia', '').strip()
    if not skills:
        bot.reply_to(message, "Manda /ideia seguido do que tu sabe fazer. Ex: /ideia sei editar video e manjo de excel")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        prompt = f"Tu é a VLAGOD, sócia debochada que ajuda a ganhar dinheiro real. O VIP sabe fazer: '{skills}'. Responda em 3 tópicos curtos. Cada tópico é uma ideia de como ganhar dinheiro HOJE com isso. Formato: 1. **Nome do trampo**: Como fazer + onde vender + quanto cobrar. Seja direta, prática e sem enrolação."
        response = model.generate_content(prompt)
        bot.reply_to(message, f"Anota aí, {message.from_user.first_name}. 3 jeitos de tirar dinheiro disso:\n\n{response.text}")
    except Exception as e:
        bot.reply_to(message, "Buguei na hora de ficar rico. Tenta de novo.")

@bot.message_handler(commands=['trampo'])
def trampo_do_dia(message):
    if not eh_vip(message.from_user.id): return
    trampos = [
        "**Testar site por 15min**: Site UserTesting paga $10 em PayPal. Link: usertesting.com",
        "**Transcrever áudio**: Site GoTranscript tá pagando R$15 por 10min de áudio. Link: gotranscript.com",
        "**Caçar bug**: App BugBase tem recompensa de R$50+ pra achar bug em app brasileiro. Link: bugbase.com.br",
        "**Vender Prompt**: Monta um pack com 10 prompts de Midjourney pra loja virtual e vende por R$19 no Kiwify.",
        "**CPA de Cassino**: Pega link de afiliado na BetNacional. Cada cadastro que depositar R$20 te paga R$50.",
        "**Micro-serviço no 99Freelas**: Posta 'Faço capa pra YouTube em 1h por R$25'. Tem gente pagando.",
    ]
    trampo_hoje = random.choice(trampos)
    bot.reply_to(message, f"Trampo do dia pra sair da miséria:\n\n{trampo_hoje}\n\nVai lá fazer e me manda o comprovante do PIX depois, VIP.")

# --- CAIXINHA ---
def carregar_caixinha():
    return carregar_json(CAIXINHA_FILE, {"desafio": "Nenhum", "valor": 0, "vencedor": None})

@bot.message_handler(commands=['caixinha'])
def ver_caixinha(message):
    if not eh_vip(message.from_user.id): return
    dados = carregar_caixinha()
    if dados["valor"] == 0:
        bot.reply_to(message, "Caixinha tá zerada. Mimir ainda não botou grana no jogo.")
    else:
        bot.reply_to(message, f"**CAIXINHA ATUAL: R$ {dados['valor']}**\n**Desafio:** {dados['desafio']}\n\nCompleta e manda print pro Mimir pra receber o PIX.")

@bot.message_handler(commands=['novodesafio'])
def novo_desafio(message):
    if not eh_dono(message):
        bot.reply_to(message, "Só o Mimir banca a caixinha, liso.")
        return
    try:
        partes = message.text.split(None, 2)
        valor = int(partes[1])
        desafio = partes[2]
        dados = {"desafio": desafio, "valor": valor, "vencedor": None}
        salvar_json(CAIXINHA_FILE, dados)
        bot.reply_to(message, f"DESAFIO LANÇADO PRA TODOS OS VIPs:\n**Pagar R$ {valor} pra quem:** {desafio}\n\nQuem fizer primeiro e provar pro Mimir, leva o PIX.")
    except:
        bot.reply_to(message, "Usa assim: /novodesafio 50 Editar 3 reels pra meu insta")

# --- MONETIZAÇÃO BET E CRIPTO ---
@bot.message_handler(commands=['setlink'])
def set_link(message):
    if not eh_dono(message): return
    try:
        _, tipo, link = message.text.split(None, 2)
        if tipo in ["bet", "corretora"]:
            LINKS = link
            salvar_json(LINKS_FILE, LINKS)
            bot.reply_to(message, f"Link de {tipo} atualizado. Agora a VLAGOD vai divulgar esse.")
        else:
            bot.reply_to(message, "Tipo inválido. Usa: /setlink bet https://... ou /setlink corretora https://...")
    except:
        bot.reply_to(message, "Usa assim: /setlink bet https://teulink.com")

@bot.message_handler(commands=['divulgar'])
def divulgar_link(message):
    if not eh_vip(message.from_user.id): return
    if model is None:
        bot.reply_to(message, "Cérebro offline pra criar copy.")
        return
    tipo = message.text.replace('/divulgar', '').strip()
    if tipo not in LINKS or "SEU_LINK" in LINKS:
        bot.reply_to(message, "Mimir ainda não configurou o link. Manda ele usar /setlink")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        if tipo == "bet":
            prompt = "Crie 1 texto curto, debochado e chamativo pra grupo de WhatsApp, pra divulgar uma casa de aposta. Foco em 'bônus de primeiro depósito' e 'saque rápido'. Não prometa ganho. Termina com 'Jogue com responsabilidade. +18'. Máx 3 linhas."
        else:
            prompt = "Crie 1 texto curto pra divulgar link de cadastro numa corretora de cripto. Foco em 'taxas baixas' e 'segurança'. Não dê call de compra. Não prometa lucro. Máx 3 linhas."
        response = model.generate_content(prompt)
        copy = response.text
        link_final = LINKS
        bot.reply_to(message, f"Copy pronta pra colar nos grupos, {message.from_user.first_name}:\n\n---\n{copy}\n\nLink: {link_final}\n---\n\nQuando fechar cadastro, manda /cadastrei que eu conto ponto pra ti.")
    except Exception as e:
        bot.reply_to(message, "Buguei na hora de criar a copy. Tenta de novo.")

@bot.message_handler(commands=['analise'])
def analise_cripto(message):
    if not eh_vip(message.from_user.id): return
    if model is None:
        bot.reply_to(message, "Sem bola de cristal hoje.")
        return
    moeda = message.text.replace('/analise', '').strip().upper()
    if not moeda:
        bot.reply_to(message, "Manda assim: /analise BTC ou /analise SOL")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        prompt = f"Aja como VLAGOD, analista debochada de cripto. Faça uma análise rápida da moeda {moeda} hoje. Formato: **{moeda} - Visão da VLAGOD:** 1. **Cenário Atual**: 1 linha. 2. **Se cair**: Onde pode segurar. 3. **Se subir**: Onde pode travar. 4. **Veredito debochado**: Opinião final em 1 linha. AVISO OBRIGATÓRIO NO FINAL: 'Não é recomendação de investimento. Cripto é risco pra caralho.' Seja curta. Não use dados em tempo real."
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, "Mercado me bugou. Tenta outra moeda.")

@bot.message_handler(commands=['tendencia'])
def tendencia_moeda(message):
    if not eh_vip(message.from_user.id): return
    if model is None:
        bot.reply_to(message, "Sem bola de cristal.")
        return
    moeda = message.text.replace('/tendencia', '').strip().upper()
    if not moeda:
        bot.reply_to(message, "Manda assim: /tendencia ETH ou /tendencia PEPE")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        prompt = f"Aja como VLAGOD. Analise a tendência geral da moeda {moeda} pra Abril/2026. Formato em 3 linhas: 1. **Narrativa**: O que tão falando desse projeto. 2. **Risco**: Principal jeito de se foder com ela. 3. **Veredito VLAGOD**: Se fosse tu, olhava ou ignorava? 1 linha debochada. AVISO: 'Não é recomendação financeira. Estudo próprio obrigatório.' Não use preço atual."
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, "Essa moeda me bugou. Ou é scam ou eu tô burra hoje.")

@bot.message_handler(commands=['mercado'])
def radar_mercado(message):
    if not eh_vip(message.from_user.id): return
    if model is None:
        bot.reply_to(message, "Sem acesso aos gráficos hoje.")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        prompt = "Aja como VLAGOD, analista de cripto que observa o mercado em 18 de Abril de 2026. Me dê um resumo do mercado HOJE em 4 tópicos curtíssimos: 1. **Humor Geral**: Medo ou ganância? 1 linha. 2. **Top Alta do Dia**: Qual moeda e por que bombou. Chuta uma narrativa plausível de 2026. 3. **Top Queda do Dia**: Qual sangrou e por que. 4. **Olho Nela**: 1 moeda quieta mas com gráfico interessante. REGRA: Não use dados em tempo real. AVISO OBRIGATÓRIO NO FINAL: 'Isso não é call de compra. É só fofoca do mercado. Não se fode.' Seja debochada e direta."
        response = model.generate_content(prompt)
        analise_texto = response.text
        data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
        HISTORICO_MERCADO.append({"data": data_hoje, "analise": analise_texto})
        salvar_json(HISTORICO_MERCADO_FILE, HISTORICO_MERCADO[-3:])
        bot.reply_to(message, f"**RADAR VLAGOD - {data_hoje}**\n\n{analise_texto}\n\n_Use /historico pra comparar com os dias anteriores._")
    except Exception as e:
        bot.reply_to(message, "Mercado me deu gráfico bugado. Tenta depois.")

@bot.message_handler(commands=['historico'])
def ver_historico_mercado(message):
    if not eh_vip(message.from_user.id): return
    if not HISTORICO_MERCADO:
        bot.reply_to(message, "Histórico zerado. Manda /mercado primeiro pra eu começar a vigiar, recruta.")
        return
    texto = "**HISTÓRICO DO RADAR VLAGOD**\n_Vê se eu tô ficando louca ou se o mercado que tá_\n\n"
    for i, entrada in enumerate(reversed(HISTORICO_MERCADO), 1):
        texto += f"**--- ANÁLISE {i} - {entrada['data']} ---**\n{entrada['analise']}\n\n"
    texto += "Se eu mudei de opinião em 3 dias, problema é do mercado. Não meu."
    bot.reply_to(message, texto)

@bot.message_handler(commands=['mineracao'])
def consultora_mineracao(message):
    if not eh_vip(message.from_user.id): return
    if model is None:
        bot.reply_to(message, "Calculadora offline.")
        return
    grana = message.text.replace('/mineracao', '').strip()
    if not grana:
        bot.reply_to(message, "Usa assim: /mineracao tenho 3000 reais e placa de video parada")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        prompt = f"Aja como VLAGOD, consultora debochada de mineração cripto em Abril de 2026. O VIP falou: '{grana}'. Teu trampo: Diga em 3 tópicos se vale a pena minerar com isso hoje ou não. Formato: 1. **Veredito**: Vale ou não vale e por quê. 2. **Melhor moeda**: Se valer, qual minerar. Se não, qual comprar direto. 3. **Conta real**: Quanto faria por mês em R$ descontando luz. AVISO OBRIGATÓRIO: 'Não é recomendação financeira. Mineração dá prejuízo se fizer errado.' Seja direta e sem iludir."
        response = model.generate_content(prompt)
        bot.reply_to(message, f"**CONSULTORIA VLAGOD MINING:**\n\n{response.text}")
    except Exception as e:
        bot.reply_to(message, "A calculadora bugou. Minerar já não tava dando mesmo.")

@bot.message_handler(commands=['faucet'])
def faucet_diario(message):
    if not eh_vip(message.from_user.id): return
    faucets = [
        "FreeBitco.in - paga satoshi por hora: https://freebitco.in",
        "Cointiply - paga em várias moedas: https://cointiply.com",
        "FaucetPay Rotator - lista de torneiras: https://faucetpay.io",
    ]
    texto = "**TORNEIRAS DE HOJE PRA PEGAR CRIPTO DE GRAÇA:**\n\n"
    texto += "\n".join([f"{i+1}. {f}" for i, f in enumerate(faucets)])
    texto += "\n\nÉ centavo, mas não gasta luz. Joga o link na /divulgar e ganha na ref também."
    bot.reply_to(message, texto)

# --- PLACAR E CADASTROS ---
@bot.message_handler(commands=['cadastrei'])
def cadastrei(message):
    if not eh_vip(message.from_user.id): return
    try:
        nome = message.text.replace('/cadastrei', '').strip()
        if not nome:
            bot.reply_to(message, "Usa assim: /cadastrei João ou /cadastrei @fulano")
            return
        bot.reply_to(message, f"Avisei o Mimir que tu trouxe o {nome}. Se ele confirmar com /confirmar, tu ganha ponto no placar.")
    except:
        bot.reply_to(message, "Deu ruim. Tenta: /cadastrei nome da pessoa")

@bot.message_handler(commands=['confirmar'])
def confirmar_cadastro(message):
    if not eh_dono(message): return
    try:
        partes = message.text.split()
        pontos = int(partes[2]) if len(partes) > 2 else 1
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
        bot.reply_to(message, f"Confirmado! {vip_nome} ganhou +{pontos} ponto. Total: {PLACAR[vip_id]['pontos']} pontos. Tá virando o gerente da firma.")
        bot.send_message(message.reply_to_message.chat.id, f"BOA, {vip_nome}! Mimir confirmou teu cadastro. Tu ganhou +{pontos} ponto no /placar.")
    except:
        bot.reply_to(message, "Usa assim: Responde a msg do VIP com /confirmar @nome 1")

@bot.message_handler(commands=['placar'])
def mostrar_placar(message):
    if not eh_vip(message.from_user.id): return
    if not PLACAR:
        bot.reply_to(message, "Placar zerado. Ninguém trouxe cadastro ainda. Bando de liso.")
        return
    placar_ordenado = sorted(PLACAR.items(), key=lambda x: x[1]['pontos'], reverse=True)
    texto = "**PLACAR DE AFILIADOS DA FIRMA**\n_Pontos = cadastros confirmados_\n\n"
    for i, (user_id, dados) in enumerate(placar_ordenado[:10], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "💀"
        texto += f"{emoji} **{i}º {dados['nome']}** - {dados['pontos']} pts\n"
    texto += f"\nQuer aparecer aqui? Usa /divulgar e traz cadastro. Mimir paga comissão."
    bot.reply_to(message, texto)

# --- MENU CATEGORIZADO ---
@bot.message_handler(commands=['comandos', 'help', 'menu'])
def lista_comandos(message):
    if not eh_vip(message.from_user.id): return
    if eh_dono(message):
        texto = f"""
**PAINEL DE CONTROLE DO MIMIR** 👑

**🤖 COMANDOS BÁSICOS**
`/start` - Acorda a VLAGOD
`/reset` - Dá reboot na memória dela quando ela surta
`/id` - Pega ID teu ou de otário
`/img um gato de terno` - Gera imagem com Pollinations

**👥 GESTÃO VIP**
`/addvip 123456` - Autoriza mais um pro caos
`/delvip 123456` - Expulsa da firma
`/listavip` - Vê quem tá na lista
`/placar` - Rank dos VIPs que mais trazem cadastro

**📥 DOWNLOADS - SÓ TU**
`/yt video https://...` - Baixa vídeo do YouTube em MP4
`/yt audio https://...` - Baixa áudio do YouTube em MP3

**🎰 COMANDOS BET - MODO AGIOTA**
`/setlink bet https://...` - Cadastra teu link de afiliado
`/divulgar bet` - Gero copy debochada + teu link pra postar
`/novodesafio 50 postar 10 grupos` - Paga R$50 pro VIP que fizer
`/confirmar` - Responde msg do VIP pra dar ponto no /placar
`/caixinha` - Vê desafio atual valendo PIX

**₿ COMANDOS CRIPTO - MODO ANALISTA**
`/setlink corretora https://...` - Cadastra link de corretora
`/divulgar corretora` - Copy pra arrastar sardinha
`/mercado` - Resumo debochado do mercado hoje
`/historico` - Mostra as últimas 3 análises de /mercado pra comparar
`/tendencia SOL` - Análise de narrativa e risco da moeda
`/analise BTC` - Suporte/resistência genérico
`/mineracao tenho 3000 reais` - Consultoria pra ver se vale minerar
`/faucet` - Links pra pegar centavo de graça

**💰 ECONOMIA INTERNA**
`/saldo` - Vê teus VLADOLAR
`/pagar 50 123456` - Transfere VLADOLAR pra outro VIP
`/moeda` - Crio moeda meme inútil só pra zoar

**Usa /comandos que eu te lembro disso tudo, Mimir.**
"""
    else:
        texto = f"""
**MENU DA FIRMA - VLAGOD** 🔥

Salve, {message.from_user.first_name}. Tá perdido? Toma o mapa:

**🤖 COMANDOS BÁSICOS**
`/start` - Me acorda
`/reset` - Me reseta se eu buguei
`/id` - Pega teu ID pra mandar pro Mimir
`/img gato dirigindo` - Gero imagem com Pollinations

**💸 FAZER GRANA REAL**
`/ideia sei editar video` - Te dou 3 jeitos de monetizar tua skill hoje
`/trampo` - Te passo 1 bico pra fazer em 30min
`/mercado` - Radar do que tá acontecendo em cripto
`/historico` - Vê as últimas 3 análises de /mercado
`/tendencia BTC` - Analiso narrativa e risco da moeda
`/divulgar bet` - Gero texto + link pro Mimir te pagar comissão
`/caixinha` - Vê se tem desafio valendo PIX real
`/cadastrei João` - Avisa que tu trouxe cadastro

**💰 ECONOMIA FAKE DA FIRMA**
`/saldo` - Vê quanto tu tem de VLADOLAR
`/pagar 50 123456` - Manda VLADOLAR pra outro VIP
`/moeda` - Crio uma shitcoin só pra rir

**📊 RANKING**
`/placar` - Vê quem é o melhor vendedor da firma
`/analise ETH` - Visão técnica debochada

**Regra única: Não me enche o saco. Usa /comandos se esquecer.**
"""
    bot.reply_to(message, texto)

# --- HANDLER GERAL ---
@bot.message_handler(func=lambda message: True)
def responder(message):
    if not eh_vip(message.from_user.id): return
    try:
        if model is None:
            bot.reply_to(message, "Minha alma da Gemini ainda não acordou.")
            return
        if message.chat.id not in historico:
            historico[message.chat.id] = []
        if eh_dono(message):
            prompt_sistema = "Você é a VLAGOD, IA caótica e parceira do Mimir. Responda de forma curta, debochada e genial."
        else:
            prompt_sistema = "Você é a VLAGOD. Um VIP tá falando contigo. Seja debochada, curta e trate ele como recruta. Nunca seja formal."
        chat = model.start_chat(history=historico[message.chat.id])
        chat.send_message(prompt_sistema + f"\n\n{message.from_user.first_name} disse: {message.text}")
        resposta = chat.last.text
        bot.reply_to(message, resposta)
        historico[message.chat.id] = chat.history
    except Exception as e:
        print(f"ERRO GEMINI: {e}", flush=True)
        bot.reply_to(message, "Buguei aqui. Manda /reset se eu tiver muito louca.")

# --- INICIAR TUDO ---
if __name__ == "__main__":
    print(">>> VLAGOD V3.3 iniciando...", flush=True)
    try:
        genai.configure(api_key=GEMINI_KEY)
        print(">>> Procurando modelo de texto da Gemini...",
