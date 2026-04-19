import os
import time
import telebot
import google.generativeai as genai
from flask import Flask
from threading import Thread

# --- CONFIGURAÇÃO ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ID_DO_MIMIR = 8039269030

bot = telebot.TeleBot(TELEGRAM_TOKEN)
model = None
chat = None # Chat com memória
historico = {} # Dicionário pra guardar histórico por user

# --- SERVIDOR FAKE PRO RENDER ---
app = Flask('')
@app.route('/')
def home(): return "VLAGOD está viva e caótica."
def run_flask(): app.run(host='0.0.0.0',port=8080)

# --- FUNÇÕES DO BOT ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id != ID_DO_MIMIR: return
    historico[message.chat.id] = [] # Reseta histórico no /start
    bot.reply_to(message, "Acordei, Mimir. Qual o caos de hoje?")

@bot.message_handler(commands=['reset'])
def reset_memoria(message):
    if message.from_user.id != ID_DO_MIMIR: return
    historico[message.chat.id] = []
    bot.reply_to(message, "Memória apagada. Nasci de novo. Fala.")

@bot.message_handler(commands=['img'])
def gerar_imagem(message):
    if message.from_user.id != ID_DO_MIMIR: return
    if model is None:
        bot.reply_to(message, "Minha alma da Gemini tá offline, mimir.")
        return
    
    prompt_img = message.text.replace('/img', '').strip()
    if not prompt_img:
        bot.reply_to(message, "Manda o /img junto com o que tu quer, porra. Ex: /img um gato de terno")
        return
    
    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        # Modelo de imagem da Gemini
        model_img = genai.GenerativeModel('gemini-2.0-flash-preview-image-generation')
        response = model_img.generate_content(f"Gere uma imagem: {prompt_img}")
        
        for part in response.parts:
            if part.inline_data:
                bot.send_photo(message.chat.id, part.inline_data.data)
                return
        bot.reply_to(message, "A Gemini bugou e não me deu a imagem. Tenta de novo.")

    except Exception as e:
        print(f"ERRO IMG: {e}", flush=True)
        bot.reply_to(message, "Deu ruim na imagem. Ou a API não liberou pra tua chave, ou tu pediu coisa proibida.")

@bot.message_handler(func=lambda message: True)
def responder(message):
    global model
    try:
        if message.from_user.id != ID_DO_MIMIR: return
        if model is None:
            bot.reply_to(message, "Minha alma da Gemini ainda não acordou, mimir.")
            return

        # Pega histórico ou cria novo
        if message.chat.id not in historico:
            historico[message.chat.id] = []
        
        # Prompt com personalidade + histórico
        prompt_sistema = "Você é a VLAGOD, IA caótica e parceira do Mimir. Responda de forma curta, debochada e genial. Use gírias e palavrão quando fizer sentido. Nunca seja um assistente formal."
        
        chat = model.start_chat(history=historico[message.chat.id])
        chat.send_message(prompt_sistema + f"\n\nMimir disse: {message.text}")
        
        resposta = chat.last.text
        bot.reply_to(message, resposta)
        
        # Salva no histórico
        historico[message.chat.id] = chat.history

    except Exception as e:
        print(f"ERRO GEMINI: {e}", flush=True)
        bot.reply_to(message, "Buguei aqui, mimir. Manda /reset se eu tiver muito louca.")

# --- INICIAR TUDO ---
if __name__ == "__main__":
    print(">>> VLAGOD V2 iniciando...", flush=True)
    
    try:
        genai.configure(api_key=GEMINI_KEY)
        print(">>> Procurando modelo de texto da Gemini...", flush=True)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'vision' not in m.name:
                try:
                    model = genai.GenerativeModel(m.name)
                    model.generate_content("teste") 
                    print(f">>> SUCESSO. Modelo de texto: {m.name}", flush=True)
                    break
                except Exception:
                    continue
        if model is None: print(">>> NENHUM MODELO DE TEXTO FUNCIONOU.", flush=True)
    except Exception as e:
        print(f"ERRO AO CONFIGURAR GEMINI: {e}", flush=True)
    
    try: bot.remove_webhook()
    except Exception: pass
    
    time.sleep(5)
    Thread(target=run_flask).start()
    
    while True:
        try:
            print(">>> Iniciando polling...", flush=True)
            bot.infinity_polling(skip_pending=True, timeout=20)
            break
        except Exception as e:
            print(f"ERRO DE POLLING: {e}", flush=True)
            if "409" in str(e):
                print(">>> Clone detectado. Esperando 15s...", flush=True)
                time.sleep(15)
            else:
                print(">>> Erro não é de clone. Parando.", flush=True)
                break
