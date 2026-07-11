"""Küçük TEST: yerel qwen2.5:7b modeli Ollama üzerinden çalışıyor mu, ne kadar hızlı?

Gemini testinin (gemini_test.py) yerel karşılığı. İnternet/anahtar gerektirmez;
model senin bilgisayarında çalışır.
"""

import sys
import time

import ollama

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "qwen2.5:7b"

print(f"Model: {MODEL} (yerel, CPU)")
print("İlk çağrıda model belleğe yükleneceği için biraz sürebilir...\n")

baslangic = time.time()
cevap = ollama.chat(
    model=MODEL,
    messages=[{"role": "user", "content": "Merhaba! Tek cümleyle kendini tanıt."}],
)
sure = time.time() - baslangic

print("Cevap:", cevap["message"]["content"])
print(f"\nSüre: {sure:.1f} saniye")
