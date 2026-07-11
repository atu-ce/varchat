"""
VarChat benzeri ama SOHBET EDEN chatbot.

Fark: VarChat tek atışlıktır (takip sorusu yok). Bu ise bir varyant hakkında
KONUŞMAYA devam etmene izin verir.

Akış:
  1) Varyant gir
  2) İlgili makaleleri çek (PubMed)
  3) Makaleleri kalıcı bağlam yapıp Gemini ile kaynaklı özet üret
  4) Aynı bağlam + sohbet hafızası üzerinden takip soruları sor ("çık" yazana kadar)
"""

import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

from c01_makale_getir import makale_idleri_bul, makale_detaylari_al
from c02_varyant_anlamlandir import anlamlandir, anlamlandir_hgvs

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")   # boru/UTF-8 girdiyi doğru oku (BOM tek karaktere iner)


def baglam_metni(makaleler):
    """Makaleleri, modele verilecek numaralı tek bir metne çevirir."""
    parcalar = []
    for i, m in enumerate(makaleler, start=1):
        parcalar.append(f"[{i}] Başlık: {m['baslik']}\n    Özet: {m['ozet']}")
    return "\n\n".join(parcalar)


def arama_terimi_belirle(girdi):
    """Girdiye göre PubMed'de aranacak terimi belirler.

    - Koordinat/HGVS-genomik ise VEP ile anlamlandırıp GEN adını döndürür.
    - Değilse (gen / rsID / protein HGVS) girdiyi olduğu gibi kullanır.
    """
    g = girdi.strip()
    try:
        if ":g." in g:                          # HGVS-genomik: GRCh38:1:g.17001759A>T
            bilgi = anlamlandir_hgvs(g)
        elif ">" in g and g.count(":") >= 2:    # VCF tarzı: chr1:17001759:A>T
            bilgi = anlamlandir(g)
        else:
            return g                            # gen / rsID / protein HGVS -> doğrudan ara
        genler = bilgi.get("genler")
        if genler:
            print(f"(Koordinat anlamlandırıldı → gen: {genler[0]}, rsID: {bilgi.get('rsid')})")
            return genler[0]
        print("(Anlamlandırıldı ama gen bulunamadı; girdi olduğu gibi aranıyor.)")
        return g
    except Exception as e:
        print(f"(Anlamlandırma başarısız: {e}; girdi olduğu gibi aranıyor.)")
        return g


def main():
    load_dotenv()
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "").strip())

    # 1) Varyant al (.lstrip: olası görünmez BOM işaretini temizler)
    varyant = input("Bir genetik varyant girin (örn. BRAF V600E): ").strip().lstrip("﻿")
    if not varyant:
        varyant = "BRAF V600E"
    print(f"\nVaryant: {varyant}")

    # 2) Girdiyi aranabilir terime çevir (koordinatsa gene), sonra makaleleri çek
    arama_terimi = arama_terimi_belirle(varyant)
    print(f"PubMed'de aranıyor: '{arama_terimi}' ...")
    pmidler = makale_idleri_bul(arama_terimi, adet=5)
    makaleler = makale_detaylari_al(pmidler)
    if not makaleler:
        print("Bu varyantla ilgili makale bulunamadı.")
        return
    print(f"{len(makaleler)} makale bulundu.\n")

    # 3) Sohbeti, makaleleri KALICI bağlam (system_instruction) yaparak başlat.
    #    Böylece hem ilk özet hem de sonraki tüm takip soruları bu kaynaklara dayanır.
    sistem_talimati = (
        f"Sen bir genetik varyant asistanısın. Kullanıcının '{varyant}' varyantı hakkındaki "
        "sorularını YALNIZCA aşağıdaki makale özetlerine dayanarak, anlaşılır bir Türkçe ile yanıtla.\n"
        "Kurallar:\n"
        "- Kendi bilginden bilgi EKLEME; sadece verilen kaynakları kullan.\n"
        "- Her bilginin yanına kaynağını köşeli parantezle yaz: [1], [2] gibi.\n"
        "- Kaynaklarda cevap yoksa 'Verilen kaynaklarda bu bilgi bulunmuyor' de.\n\n"
        f"KAYNAKLAR:\n{baglam_metni(makaleler)}"
    )
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(system_instruction=sistem_talimati),
    )

    # 4a) İlk cevap: kaynaklı özet
    ilk = chat.send_message(f"{varyant} varyantını kaynaklı olarak özetle.")
    print("=" * 70)
    print("ÖZET:\n")
    print(ilk.text)
    print("\n" + "=" * 70)
    print("KAYNAKLAR:")
    for i, m in enumerate(makaleler, start=1):
        print(f"[{i}] {m['baslik']} — https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
    print("=" * 70)

    # 4b) Takip soruları döngüsü (chat nesnesi geçmişi kendisi hatırlar)
    print("\nBu varyant hakkında soru sorabilirsin. Çıkmak için 'çık' yaz.\n")
    try:
        while True:
            soru = input("Sen: ").strip().lstrip("﻿")
            if soru.lower() in ("çık", "cik", "exit", "quit", ""):
                print("Görüşürüz!")
                break
            cevap = chat.send_message(soru)
            print("\nBot:", cevap.text, "\n")
    except (KeyboardInterrupt, EOFError):
        print("\nGörüşürüz!")


if __name__ == "__main__":
    main()
