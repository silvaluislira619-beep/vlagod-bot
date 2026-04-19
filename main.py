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
    
    # Mata webhook e espera processo zumbi morrer
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook já estava morto: {e}")
    
    time.sleep(5) # Espera 5s pra garantir
    
    # Liga o servidor fake pro Render não matar o processo
    Thread(target=run_flask).start()
    
    # Liga o bot com retry infinito contra clones
    while True:
        try:
            print(">>> Iniciando polling...")
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
            break # Se chegou aqui, rodou de boa e pode sair do loop
        except Exception as e:
            print(f"ERRO DE POLLING: {e}")
            if "409" in str(e):
                print(">>> Clone detectado. Esperando 15s pra tentar de novo...")
                time.sleep(15) # Espera 15s e tenta de novo
            else:
                print(">>> Erro não é de clone. Parando.")
                break
