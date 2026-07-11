"""
Küçük TEST: Bir chatbot'u chatbot yapan şey -> SOHBETİ HATIRLAMAK.

Modele iki mesaj gönderiyoruz. İkinci mesajda, birincide söylediğimizi
soruyoruz. Model hatırlıyorsa, "sohbet hafızası" çalışıyor demektir.
(VarChat'in yapamadığı şey tam da bu: takip sorusu.)
"""

import os
import sys

from dotenv import load_dotenv
from google import genai

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "").strip())

# Bir SOHBET oturumu başlat. Bu nesne, konuşma geçmişini kendisi tutar.
chat = client.chats.create(model="gemini-2.5-flash")

# 1. mesaj
cevap1 = chat.send_message("Adım Ahmet. Bilgisayar mühendisliği yüksek lisansı yapıyorum.")
print("Kullanıcı: Adım Ahmet. Bilgisayar mühendisliği yüksek lisansı yapıyorum.")
print("Bot:", cevap1.text)
print("-" * 60)

# 2. mesaj — adımı TEKRAR söylemiyorum; hatırlıyor mu diye soruyorum
cevap2 = chat.send_message("Benim adım neydi ve ne okuyorum?")
print("Kullanıcı: Benim adım neydi ve ne okuyorum?")
print("Bot:", cevap2.text)
