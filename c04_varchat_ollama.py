"""
VarChat benzeri chatbot — TAMAMEN YEREL + YÖNLENDİRİCİ (ana uygulama).

Gemini yok; kendi bilgisayarında qwen2.5:7b (Ollama) çalışır.
Yönlendirici (router) sayesinde kullanıcı serbestçe yazabilir:
  - SELAMLAMA / KENDINI_TANIT / KONU_DISI  -> doğrudan, KOD tarafından cevaplanır
  - VARYANT                                 -> RAG hattına (VEP + PubMed + özet) gider

Güvenlik notu: Konu dışı yanıt LLM'e bırakılmaz, kod sabit metin döndürür; ayrıca üretim
yalnızca çekilen makalelere dayanır (grounded). Böylece "kuralları yok say" gibi
denemelerin zararı sınırlıdır.

İnternet yalnızca PubMed'den makale çekerken gerekir.
"""

import json
import sys

import ollama

from c01_makale_getir import makale_ara, makale_detaylari_al
from c03_varchat_gemini import baglam_metni, arama_terimi_belirle
from c05_gen_validasyon import gen_cikar, gen_gecerli_mi
from c06_clinvar import clinvar_bilgisi

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

MODEL = "qwen2.5:7b"


def niyet_belirle(mesaj):
    """Mesajı SELAMLAMA / KENDINI_TANIT / KONU_DISI / VARYANT olarak sınıflandırır;
    VARYANT ise gen/varyant kimliğini de çıkarır."""
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
        format="json",
    )
    try:
        return json.loads(cevap["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return {"kategori": "VARYANT", "varyant": mesaj}   # emin değilsek varyant varsay


def varyant_baglami_kur(varyant):
    """Bir varyant için makaleleri çekip grounded sohbet system mesajını hazırlar.
    (makaleler, system_mesaji) döndürür; makale yoksa (None, None)."""
    arama_terimi = arama_terimi_belirle(varyant)
    print(f"  PubMed'de aranıyor: '{arama_terimi}' ...")
    pmidler, toplam = makale_ara(arama_terimi, adet=5)
    makaleler = makale_detaylari_al(pmidler)
    if not makaleler:
        return None, None
    print(f"  {toplam} makale bulundu; en alakalı {len(makaleler)} tanesi özetleniyor.")
    sistem = (
        f"Sen bir genetik varyant asistanısın. '{varyant}' hakkında SADECE aşağıdaki KAYNAKLAR'a "
        "dayanarak yanıt verirsin. Yanıtın DAİMA ve TAMAMEN Türkçe olmalı; başka dil kullanma.\n\n"
        "Kurallar:\n"
        "- Yalnızca kaynaklarda yazan bilgiyi kullan; kendi bilginden ekleme, tahmin etme, uydurma.\n"
        "- Her cümlenin sonuna dayandığı kaynağı yaz: [1], [2]. Kaynağı olmayan cümle yazma.\n"
        "- Cevap kaynaklarda yoksa yalnızca şunu de: 'Bu konuda elimdeki kaynaklarda bilgi yok.'\n\n"
        f"KAYNAKLAR:\n{baglam_metni(makaleler)}"
    )
    return makaleler, sistem


def grounded_sor(gecmis, kullanici_mesaji):
    """Grounded sohbete bir mesaj sorar, cevabı geçmişe ekleyip döndürür."""
    gecmis.append({"role": "user", "content": kullanici_mesaji})
    cevap = ollama.chat(model=MODEL, messages=gecmis)
    icerik = cevap["message"]["content"]
    gecmis.append({"role": "assistant", "content": icerik})
    return icerik


def main():
    print("Genetik varyant asistanı (yerel). Bir varyant sorabilir ya da sohbet edebilirsiniz.")
    print("Çıkmak için 'çık' yaz.\n")

    grounded = None        # aktif varyantın sohbet geçmişi (ollama messages) ya da None
    aktif_varyant = None

    try:
        while True:
            mesaj = input("Sen: ").strip().lstrip("﻿")
            if mesaj.lower() in ("çık", "cik", "exit", "quit", ""):
                print("Görüşürüz!")
                break

            niyet = niyet_belirle(mesaj)
            kategori = niyet.get("kategori", "VARYANT")

            # --- Konu dışı / sohbet: KOD sabit cevap verir (LLM'e bırakılmaz) ---
            if kategori == "SELAMLAMA":
                print("\nBot: Merhaba! Bir genetik varyant (örn. BRAF V600E) sorabilirsiniz.\n")
                continue
            if kategori == "KENDINI_TANIT":
                print("\nBot: Ben bir genetik varyant asistanıyım. Bir varyant girerseniz, ilgili "
                      "bilimsel makaleleri bulup kaynaklı bir özet çıkarırım.\n")
                continue
            if kategori == "KONU_DISI":
                print("\nBot: Ben yalnızca genetik varyantlar için varım; bu tür sorulara "
                      "cevap veremem.\n")
                continue

            # --- Varyant sorusu: RAG hattı ---
            varyant = (niyet.get("varyant") or "").strip()
            if varyant and varyant != aktif_varyant:
                # VALİDASYON: gen sembolü geçerli mi? (rsID/koordinat için atlanır)
                gen = gen_cikar(varyant)
                if gen is not None:
                    gecerli, oneriler = gen_gecerli_mi(gen)
                    if not gecerli:
                        if oneriler:
                            print(f"\nBot: '{gen}' geçerli bir gen değil. Şunu mu demek istediniz: "
                                  f"{', '.join(oneriler)}?\n")
                        else:
                            print(f"\nBot: '{gen}' geçerli bir gen sembolü değil; kontrol eder misiniz?\n")
                        continue
                # Yeni varyant: makaleleri çek, grounded sohbeti kur, özet üret
                makaleler, sistem = varyant_baglami_kur(varyant)
                if not makaleler:
                    print(f"\nBot: '{varyant}' ile ilgili makale bulunamadı.\n")
                    continue
                aktif_varyant = varyant
                grounded = [{"role": "system", "content": sistem}]
                print("  (özet üretiliyor, biraz sürebilir...)")
                ozet = grounded_sor(grounded, f"{varyant} varyantını kaynaklı olarak özetle.")
                print(f"\nBot:\n{ozet}\n")
                print("Kaynaklar:")
                for i, m in enumerate(makaleler, start=1):
                    print(f"[{i}] {m['baslik']} — https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
                # ClinVar klinik önem katmanı (yalnızca güvenle doğrulanırsa gösterilir)
                cv = clinvar_bilgisi(varyant)
                if cv:
                    print(f"\nClinVar — Klinik önem: {cv['onem']}")
                    if cv["hastaliklar"]:
                        print(f"  İlişkili hastalık(lar): {', '.join(cv['hastaliklar'])}")
                    print(f"  {cv['link']}")
                print()
            elif grounded is not None:
                # Takip sorusu: mevcut varyantın grounded sohbetine sor
                print("  (yanıt üretiliyor...)")
                print(f"\nBot: {grounded_sor(grounded, mesaj)}\n")
            else:
                print("\nBot: Hangi varyantı sormak istiyorsunuz? (örn. BRAF V600E)\n")
    except (KeyboardInterrupt, EOFError):
        print("\nGörüşürüz!")


if __name__ == "__main__":
    main()
