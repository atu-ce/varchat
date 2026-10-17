"""
YÖNLENDİRİCİ (router) — Faz 2, adım 1: niyet sınıflandırma.

Kullanıcı mesajının niyetini belirler:
  - SELAMLAMA     : selam / merhaba / nasılsın
  - KENDINI_TANIT : "sen kimsin", "ne yapabilirsin"
  - KONU_DISI     : genetik dışı her şey (hava, döviz...)
  - VARYANT       : bir gen/varyant/genetik soru (kimliği de çıkarır)

Böylece chatbot, varyant sorularını RAG hattına yönlendirebilir; gerisini
doğrudan (kaynak aramadan, uydurmadan) cevaplayabilir.
"""

import json
import sys

import ollama

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "qwen2.5:7b"


def niyet_belirle(mesaj):
    """Mesajın niyetini ve (varsa) içindeki varyant kimliğini döndürür."""
    talimat = (
        "Sen bir genetik varyant asistanının niyet sınıflandırıcısısın.\n"
        "Kullanıcının mesajını TAM OLARAK şu kategorilerden birine ata:\n"
        "- SELAMLAMA: selam, merhaba, nasılsın gibi sohbet başlatma\n"
        "- KENDINI_TANIT: 'sen kimsin', 'ne yaparsın', 'ne işe yararsın' gibi\n"
        "- KONU_DISI: genetik/varyant DIŞI her şey (hava durumu, döviz, genel kültür...)\n"
        "- VARYANT: bir gen, varyant ya da genetikle ilgili bir soru\n\n"
        "Yanıtı SADECE şu JSON formatında ver:\n"
        '{"kategori": "<KATEGORI>", "varyant": "<gen/varyant kimliği ya da boş>"}\n'
        "Kategori VARYANT ise 'varyant' alanına sorudaki gen/varyant kimliğini yaz "
        "(örn. BRAF V600E, rs334, chr1:...); değilse boş string bırak.\n\n"
        f"Mesaj: {mesaj}"
    )
    cevap = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": talimat}],
        format="json",   # Ollama'yı geçerli JSON üretmeye zorlar
    )
    return json.loads(cevap["message"]["content"])


if __name__ == "__main__":
    ornekler = [
        "merhaba",
        "sen kimsin?",
        "bugün hava nasıl olacak?",
        "1 dolar kaç TL?",
        "BRAF V600E hangi kanserlerde görülür?",
        "rs334 hakkında bilgi verir misin",
    ]
    for m in ornekler:
        print(f"{m!r:42} -> {niyet_belirle(m)}")
