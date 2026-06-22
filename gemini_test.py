"""
Küçük bir TEST: Gemini (beynimiz) tek başına çalışıyor mu?

Henüz makale falan yok. Sadece "Gemini'ye bağlanabiliyor muyuz ve cevap
alabiliyor muyuz?" diye kontrol ediyoruz. Bu çalışırsa, sonraki adımda
Gemini'yi makalelerle birleştireceğiz.
"""

import os
import sys

from dotenv import load_dotenv      # .env dosyasındaki gizli anahtarı okumak için
from google import genai            # Google Gemini ile konuşmak için

sys.stdout.reconfigure(encoding="utf-8")   # özel karakterlerde çökmeyi önler (daha önce öğrendik)

# 1) .env dosyasındaki anahtarı belleğe yükle, sonra oku
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY", "").strip()

# 2) Anahtar gerçekten konulmuş mu? Kontrol et, yoksa anlaşılır bir uyarı ver
if not api_key or api_key == "buraya_kendi_anahtarini_yapistir":
    print("HATA: .env dosyasına geçerli bir GEMINI_API_KEY yapıştırmalısın.")
    raise SystemExit(1)

# 3) Gemini'ye bağlan
client = genai.Client(api_key=api_key)

# 4) Küçük bir soru sor (henüz makale yok; sadece beyin çalışıyor mu test ediyoruz)
cevap = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Merhaba! Tek cümleyle kendini tanıt.",
)

# 5) Cevabı ekrana yaz
print("Gemini'nin cevabı:")
print(cevap.text)
