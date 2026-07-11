"""
VarChat benzeri chatbot — TAMAMEN YEREL sürüm (Gemini YOK).

Gemini yerine, kendi bilgisayarında çalışan açık kaynak modeli (qwen2.5:7b, Ollama)
kullanır. İnternet yalnızca PubMed'den makale çekerken gerekir; özet ve sohbet
tamamen yerelde üretilir — yazdığın hiçbir şey dışarı çıkmaz.

Önceki dosyalardaki hazır parçaları kullanır (makale çekme, koordinat anlamlandırma).
"""

import sys

import ollama

from c01_makale_getir import makale_idleri_bul, makale_detaylari_al
from c03_varchat_gemini import baglam_metni, arama_terimi_belirle

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

MODEL = "qwen2.5:7b"


def main():
    varyant = input("Bir genetik varyant girin (örn. BRAF V600E): ").strip().lstrip("﻿")
    if not varyant:
        varyant = "BRAF V600E"
    print(f"\nVaryant: {varyant}")

    # 1) Girdiyi aranabilir terime çevir (koordinatsa gene) + makaleleri çek
    arama_terimi = arama_terimi_belirle(varyant)
    print(f"PubMed'de aranıyor: '{arama_terimi}' ...")
    makaleler = makale_detaylari_al(makale_idleri_bul(arama_terimi, adet=5))
    if not makaleler:
        print("Bu varyantla ilgili makale bulunamadı.")
        return
    print(f"{len(makaleler)} makale bulundu. Yerel model özetliyor (CPU'da biraz sürebilir)...\n")

    # 2) Sohbet geçmişini KENDİMİZ tutuyoruz (Ollama, Gemini gibi otomatik tutmaz).
    #    İlk mesaj "system": kurallar + makaleler (kalıcı bağlam).
    sistem = (
        f"Sen bir genetik varyant asistanısın. Kullanıcının '{varyant}' varyantı hakkındaki "
        "sorularını YALNIZCA aşağıdaki makale özetlerine dayanarak, anlaşılır bir Türkçe ile yanıtla.\n"
        "Kurallar:\n"
        "- Kendi bilginden bilgi EKLEME; sadece verilen kaynakları kullan.\n"
        "- Her bilginin yanına kaynağını köşeli parantezle yaz: [1], [2] gibi.\n"
        "- Kaynaklarda cevap yoksa 'Verilen kaynaklarda bu bilgi bulunmuyor' de.\n\n"
        f"KAYNAKLAR:\n{baglam_metni(makaleler)}"
    )
    mesajlar = [{"role": "system", "content": sistem}]

    def sor(kullanici_mesaji):
        """Mesajı geçmişe ekler, yerel modele sorar, cevabı geçmişe ekleyip döndürür."""
        mesajlar.append({"role": "user", "content": kullanici_mesaji})
        cevap = ollama.chat(model=MODEL, messages=mesajlar)
        icerik = cevap["message"]["content"]
        mesajlar.append({"role": "assistant", "content": icerik})
        return icerik

    # 3) İlk cevap: kaynaklı özet
    ozet = sor(f"{varyant} varyantını kaynaklı olarak özetle.")
    print("=" * 70)
    print("ÖZET:\n")
    print(ozet)
    print("\n" + "=" * 70)
    print("KAYNAKLAR:")
    for i, m in enumerate(makaleler, start=1):
        print(f"[{i}] {m['baslik']} — https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
    print("=" * 70)

    # 4) Takip soruları (geçmiş kendimizde olduğu için model hatırlar)
    print("\nBu varyant hakkında soru sorabilirsin. Çıkmak için 'çık' yaz.\n")
    try:
        while True:
            soru = input("Sen: ").strip().lstrip("﻿")
            if soru.lower() in ("çık", "cik", "exit", "quit", ""):
                print("Görüşürüz!")
                break
            print("(yanıt üretiliyor...)")
            print("\nBot:", sor(soru), "\n")
    except (KeyboardInterrupt, EOFError):
        print("\nGörüşürüz!")


if __name__ == "__main__":
    main()
