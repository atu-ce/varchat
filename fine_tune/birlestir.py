"""
FINE-TUNE — Adım 3: BİRLEŞTİRME (v3).

ozetler.py (öğretmen özetleri) + takip_sorular.py (takip soru-cevapları) + kaynaklar.jsonl (PubMed kaynakları)
    -> egitim_verisi.jsonl  (messages formatında, chat fine-tune için)

Her örnekte system mesajı ÇIKARIM (inference) anındaki c04 promptunun BİREBİR aynısıdır.
Her satıra üç yardımcı alan da yazılır; Colab defteri bölmeyi buradan okur:
  "varyant" : örneğin ait olduğu varyant
  "bolme"   : "train" ya da "val"  (GEN bazlı: VAL_GENLER'deki genlerin TÜM örnekleri doğrulamaya gider;
              aynı genin farklı varyantları ortak makale paylaşabildiği için varyant bazlı bölme sızdırır)
  "tur"     : örnek türü

Örnek türleri:
  ozet             "<varyant> varyantını kaynaklı olarak özetle." -> öğretmenin kaynaklı Türkçe özeti
  takip            odaklı soru -> kaynaklı kısa cevap (tek turlu)
  takip_cok_turlu  c04'ün gerçek kullanım biçimi: system, "özetle", özet, takip sorusu, cevap
  ret_yabanci      BAŞKA bir genin takip sorusu bu varyantın kaynaklarına sorulur -> "bilgi yok"
                   (yalnızca aynı bölmeden; sorunun geni/değişimi kaynaklarda kelime olarak hiç geçmiyorsa;
                    her soru en fazla bir kez; varyantların yarısı için)
  ret_kapsam_disi  AKTİF varyant hakkında ama makale özetlerinin kapsamadığı konu (doz, gebelik, maliyet...)
                   -> "bilgi yok" (konu anahtar kelimeleri kaynaklarda geçmiyorsa eklenir)
     Neden ret örnekleri: system promptun 3. kuralı bu cevabı ister; model bunu ancak örneğini görürse öğrenir.
"""

import collections
import json
import os
import random
import re

from ozetler import OZETLER
from takip_sorular import TAKIP

BURASI = os.path.dirname(os.path.abspath(__file__))
KAYNAK_DOSYA = os.path.join(BURASI, "kaynaklar.jsonl")
CIKTI = os.path.join(BURASI, "egitim_verisi.jsonl")

# Doğrulama genleri: tek varyantlı 6 gen (solid tümör, hematolojik, kalıtsal karışık). Sabit liste = sabit bölme.
VAL_GENLER = {"AKT1", "DNMT3A", "HFE", "HRAS", "IDH2", "MYD88"}

RET_CEVAP = "Bu konuda elimdeki kaynaklarda bilgi yok."

# Aktif varyant hakkında, makale özetlerinin genelde kapsamadığı konular:
# (Türkçe soru şablonu, kaynaklarda aranacak İngilizce anahtar kelimeler — biri geçiyorsa şablon o varyant için kullanılmaz)
KAPSAM_DISI = [
    ("{v} için önerilen ilaç dozu nedir?", ["dose", "dosing", " mg", "mg/"]),
    ("{v} taşıyan hastalarda gebelik takibi nasıl yapılır?", ["pregnan", "gestation"]),
    ("{v} testi Türkiye'de hangi merkezlerde yapılıyor?", ["turk", "türk"]),
    ("{v} tedavisinin maliyeti ne kadardır?", ["cost", "price", "economic", "reimburs"]),
    ("{v} testinin sonuçlanma süresi kaç gündür?", ["turnaround", "within days", "working days"]),
    ("{v} için diyet önerisi var mı?", ["diet", "nutrition"]),
    ("{v} çocuklarda nasıl tedavi edilir?", ["pediatric", "children", "childhood", "child"]),
    ("{v} taşıyan hastalarda aşı önerisi nedir?", ["vaccin", "immuniz"]),
]


def sistem_mesaji(varyant, kaynaklar):
    """c04_varchat_ollama.varyant_baglami_kur ile BİREBİR aynı system metni."""
    return (
        f"Sen bir genetik varyant asistanısın. '{varyant}' hakkında SADECE aşağıdaki KAYNAKLAR'a "
        "dayanarak yanıt verirsin. Yanıtın DAİMA ve TAMAMEN Türkçe olmalı; başka dil kullanma.\n\n"
        "Kurallar:\n"
        "- Yalnızca kaynaklarda yazan bilgiyi kullan; kendi bilginden ekleme, tahmin etme, uydurma.\n"
        "- Her cümlenin sonuna dayandığı kaynağı yaz: [1], [2]. Kaynağı olmayan cümle yazma.\n"
        "- Cevap kaynaklarda yoksa yalnızca şunu de: 'Bu konuda elimdeki kaynaklarda bilgi yok.'\n\n"
        f"KAYNAKLAR:\n{kaynaklar}"
    )


def gen_sembolu(varyant):
    """'KRAS G12C' -> 'KRAS', 'TERT promoter C228T' -> 'TERT'."""
    return varyant.split()[0].upper()


def degisim(varyant):
    """'KRAS G12C' -> 'G12C', 'TERT promoter C228T' -> 'C228T'."""
    return varyant.split()[-1]


def bolme(varyant):
    return "val" if gen_sembolu(varyant) in VAL_GENLER else "train"


def gecer_mi(sembol, metin):
    """Sembol metinde BAĞIMSIZ kelime olarak geçiyor mu? ('AR' -> 'are'/'rash' ile eşleşmesin; büyük/küçük harfe duyarlı.)"""
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(sembol)}(?![A-Za-z0-9])", metin) is not None


def main():
    # kaynaklar.jsonl -> {varyant: kaynaklar_metni}
    kaynak = {}
    with open(KAYNAK_DOSYA, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                kayit = json.loads(satir)
                kaynak[kayit["varyant"]] = kayit["kaynaklar"]

    varyantlar = [v for v in OZETLER if v in kaynak]          # sabit sıra (ozetler.py sırası)
    atlanan = [v for v in OZETLER if v not in kaynak]

    def uclu(varyant, soru, cevap):
        return [
            {"role": "system", "content": sistem_mesaji(varyant, kaynak[varyant])},
            {"role": "user", "content": soru},
            {"role": "assistant", "content": cevap.strip()},
        ]

    sayac = collections.Counter()

    def ornek_yaz(f, varyant, tur, messages):
        kayit = {"messages": messages, "varyant": varyant, "bolme": bolme(varyant), "tur": tur}
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        sayac[tur] += 1
        sayac[bolme(varyant)] += 1

    # Takip sorularını varyanta göre grupla (ret_yabanci havuzu)
    takip_havuzu = {}
    for t in TAKIP:
        takip_havuzu.setdefault(t["varyant"], []).append(t["soru"])

    rng = random.Random(42)   # sabit tohum: her çalıştırmada aynı seçim (tekrar üretilebilirlik)

    with open(CIKTI, "w", encoding="utf-8") as f:
        # 1) Özet örnekleri
        for varyant in varyantlar:
            ornek_yaz(f, varyant, "ozet",
                      uclu(varyant, f"{varyant} varyantını kaynaklı olarak özetle.", OZETLER[varyant]))

        # 2) Takip örnekleri: çift indeksliler tek turlu, tek indeksliler çok turlu (c04'ün geçmişi taşıdığı biçim)
        for i, t in enumerate(TAKIP):
            varyant = t["varyant"]
            if varyant not in kaynak:
                atlanan.append(f"{varyant} (takip)")
                continue
            if i % 2 == 0:
                ornek_yaz(f, varyant, "takip", uclu(varyant, t["soru"], t["cevap"]))
            else:
                msgs = [
                    {"role": "system", "content": sistem_mesaji(varyant, kaynak[varyant])},
                    {"role": "user", "content": f"{varyant} varyantını kaynaklı olarak özetle."},
                    {"role": "assistant", "content": OZETLER[varyant].strip()},
                    {"role": "user", "content": t["soru"]},
                    {"role": "assistant", "content": t["cevap"].strip()},
                ]
                ornek_yaz(f, varyant, "takip_cok_turlu", msgs)

        # 3) ret_yabanci: varyantların yarısı için, AYNI bölmeden başka bir genin sorusu
        kullanilan_sorular = set()
        for j, varyant in enumerate(varyantlar):
            if j % 2 == 1:
                continue
            adaylar = [
                (v2, soru)
                for v2, sorular in takip_havuzu.items()
                if v2 in kaynak
                and bolme(v2) == bolme(varyant)                        # doğrulama sorusu eğitime sızmasın
                and gen_sembolu(v2) != gen_sembolu(varyant)
                and not gecer_mi(gen_sembolu(v2), kaynak[varyant])     # gen kaynaklarda geçmesin (kelime olarak)
                and not gecer_mi(degisim(v2), kaynak[varyant])         # değişim de geçmesin (T315I, C228T...)
                for soru in sorular
                if soru not in kullanilan_sorular                       # her soru en fazla bir kez
            ]
            if not adaylar:
                continue
            _, soru = rng.choice(adaylar)
            kullanilan_sorular.add(soru)
            ornek_yaz(f, varyant, "ret_yabanci", uclu(varyant, soru, RET_CEVAP))

        # 4) ret_kapsam_disi: her varyant için, kaynakların kapsamadığı bir konu (başlangıç şablonu varyanta göre döner)
        for j, varyant in enumerate(varyantlar):
            metin = kaynak[varyant].lower()
            for k in range(len(KAPSAM_DISI)):
                sablon, anahtarlar = KAPSAM_DISI[(j + k) % len(KAPSAM_DISI)]
                if not any(a.lower() in metin for a in anahtarlar):
                    ornek_yaz(f, varyant, "ret_kapsam_disi", uclu(varyant, sablon.format(v=varyant), RET_CEVAP))
                    break

    toplam = sum(sayac[t] for t in ("ozet", "takip", "takip_cok_turlu", "ret_yabanci", "ret_kapsam_disi"))
    print(f"{sayac['ozet']} özet + {sayac['takip']} takip + {sayac['takip_cok_turlu']} çok turlu takip + "
          f"{sayac['ret_yabanci']} ret (yabancı gen) + {sayac['ret_kapsam_disi']} ret (kapsam dışı) "
          f"= {toplam} örnek -> {os.path.basename(CIKTI)}")
    print(f"bölme: eğitim {sayac['train']} | doğrulama {sayac['val']}  (doğrulama genleri: {', '.join(sorted(VAL_GENLER))})")
    if atlanan:
        print(f"Kaynağı bulunamayan (atlanan): {', '.join(atlanan)}")


if __name__ == "__main__":
    main()
