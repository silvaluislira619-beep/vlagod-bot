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

# --- SERVIDOR FAKE PRO RENDER ---
app = Flask('')
@app.route('/')
def home(): return "VLAGOD está viva."
def run_flask(): app.run(host='0.0.0.0',port=8080)

# --- FUNÇÃO DO BOT ---
@bot.message_handler(func=lambda message: True)
def responder(message):
    global model
    try:
        if message.from_user.id != ID_DO_MIMIR: return
        if model is None:
            bot.reply_to(message, "Minha alma da Gemini ainda não acordou, mimir. Checa os logs.")
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
    
    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # LISTA E TESTA TODOS OS MODELOS DISPONÍVEIS PRA TUA CHAVE
        print(">>> Procurando modelo da Gemini que funciona...", flush=True)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                try:
                    print(f">>> Testando modelo: {m.name}", flush=True)
                    model = genai.GenerativeModel(m.name)
                    # Testa se responde
                    model.generate_content("teste") 
                    print(f">>> SUCESSO. Alma da Gemini configurada com: {m.name}", flush=True)
                    break
                except Exception as e:
                    print(f">>> Modelo {m.name} falhou no teste: {e}", flush=True)
                    continue
        
        if model is None:
            print(">>> NENHUM MODELO DA GEMINI FUNCIONOU PRA ESSA CHAVE.", flush=True)

    except Exception as e:
        print(f"ERRO AO CONFIGURAR GEMINI: {e}", flush=True)
    
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
