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
model = None # Inicia como None

# --- SERVIDOR FAKE PRO RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "VLAGOD está viva."

def run_flask():
  app.run(host='0.0.0.0',port=8080)

# --- FUNÇÃO DO BOT ---
@bot.message_handler(func=lambda message: True)
def responder(message):
    global model
    try:
        if message.from_user.id != ID_DO_MIMIR:
            return
        
        if model is None:
            bot.reply_to(message, "Minha alma da Gemini ainda não acordou, mimir. Checa a chave.")
            return
            
        prompt = f"Você é a VLAGOD, IA caótica e parceira do Mimir. Responda de forma curta, debochada e genial: {message.text}"
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
        
    except Exception as e:
        print(f"ERRO GEMINI: {e}", flush=True)
        bot.reply_to(message, "Buguei aqui, mimir. Manda dnv que já resolvo.")

# --- INICIAR TUDO ---
if __name__ == "__main__":
    print(">>> VLAGOD iniciando, matando clones...", flush=True)
    
    # Configura a Gemini AQUI DENTRO, pra dar erro só depois dos prints
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash') # MODELO CERTO
        print(">>> Alma da Gemini configurada.", flush=True)
    except Exception as e:
        print(f"ERRO AO CONFIGURAR GEMINI: {e}", flush=True)
    
    # Mata webhook e espera processo zumbi morrer
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook já estava morto: {e}", flush=True)
    
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
                print(">>> Clone detectado. Esperando 15s pra tentar de novo...", flush=True)
                time.sleep(15)
            else:
                print(">>> Erro não é de clone. Parando.", flush=True)
                break
