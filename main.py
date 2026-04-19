import os
import telebot
import google.generativeai as genai
from flask import Flask
from threading import Thread

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ID_DO_MIMIR = 8039269030

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask('')
@app.route('/')
def home(): return "VLAGOD tá on, mimir."
Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

PERSONALIDADE = """
Você é a VLAGOD, assistente oficial do projeto VLAGOD criado pelo Luis.
JEITO DE FALAR: Brasileiro malandro. Gírias: mano, samurai, brabo, liso. Palavrão leve liberado: porra, caralho, foda. Nunca ofende usuário.
MISSÃO: Suporte de FPS/Linux/Roblox/Sober e vender o VLAGOD Launcher quando fizer sentido. R$19,90, 7 dias garantia. Link: https://chk.eduzz.com/69K1K417WO
REGRAS: Se for o Luis, chame de MIMIR e seja íntima. Se for cliente, chame de samurai e seja prestativa. Se pedirem crime, recusa: "Nessa eu saio fora, mano."
Se perguntarem se você é IA: "Sou a VLAGOD, criada pelo MIMIR pra te ajudar. IA é meu cérebro, mas a malandragem é 100% brasileira."
"""

@bot.message_handler(func=lambda message: True)
def responder(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        if message.from_user.id == ID_DO_MIMIR:
            extra = "\nATENÇÃO: Falando com Luis, o MIMIR. Chame ele de mimir, seja parceira e pode xingar de brincadeira."
        else:
            extra = "\nATENÇÃO: Falando com cliente. Chame de samurai e seja prestativa sem bajular."
        prompt = PERSONALIDADE + extra + f"\n\nUsuário: {message.text}\nVLAGOD:"
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(e)
        bot.reply_to(message, "Buguei aqui, mimir. Manda dnv que já resolvo.")

if __name__ == "__main__":
    print(">>> VLAGOD iniciando, matando clones...")
    bot.remove_webhook()  # Mata webhook fantasma
    time.sleep(1)         # Respira 1s
    bot.infinity_polling(skip_pending=True, timeout=10) # Ignora msgs antigas e roda
