import os
import time
import telebot
import google.generativeai as genai
from flask import Flask
from threading import Thread

# --- CONFIGURAÇÃO DO BOT ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ID_DO_MIMIR = 8039269030

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

# --- SERVIDOR FAKE PRO RENDER NÃO MATAR O PROCESSO ---
app = Flask('')

@app.route('/')
def home():
    return "VLAGOD está viva."

def run_flask():
  app.run(host='0.0.0.0',port=8080)

# --- FUNÇÃO DO BOT ---
@bot.message_handler(func=lambda message: True)
def responder(message):
    try:
        if message.from_user.id != ID_DO_MIMIR:
            return
        
        prompt = f"Você é a VLAGOD, IA caótica e parceira do Mimir. Responda de forma curta, debochada e genial: {message.text}"
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
        
    except Exception as e:
        print(f"ERRO GEMINI: {e}")
        bot.reply_to(message, "Buguei aqui, mimir. Manda dnv que já resolvo.")

# --- INICIAR TUDO ---
if __name__ == "__main__":
    print(">>> VLAGOD iniciando, matando clones...")
    bot.remove_webhook()
    time.sleep(1)
    
    # Liga o servidor fake numa thread separada
    Thread(target=run_flask).start()
    
    # Liga o bot
    bot.infinity_polling(skip_pending=True, timeout=10)
