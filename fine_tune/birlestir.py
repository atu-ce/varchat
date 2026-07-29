"""
FINE-TUNE — Adım 3: BİRLEŞTİRME.

ozetler.py (öğretmen özetleri) + kaynaklar.jsonl (PubMed kaynakları)
    -> egitim_verisi.jsonl  (messages formatında, chat fine-tune için)

Her örnek, ÇIKARIM (inference) anındaki formatın BİREBİR aynısıdır:
  system  : c04'teki grounded system mesajı (kurallar + KAYNAKLAR)
  user    : "<varyant> varyantını kaynaklı olarak özetle."
  assistant: öğretmenin (Claude) yazdığı kaynaklı Türkçe özet

Böylece model, "kaynak ver -> kaynaklı Türkçe özet üret" davranışını öğrenir.
"""

import json
import os

from ozetler import OZETLER
from takip_sorular import TAKIP

BURASI = os.path.dirname(os.path.abspath(__file__))
KAYNAK_DOSYA = os.path.join(BURASI, "kaynaklar.jsonl")
CIKTI = os.path.join(BURASI, "egitim_verisi.jsonl")


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


def main():
    # kaynaklar.jsonl -> {varyant: kaynaklar_metni}
    kaynak = {}
    with open(KAYNAK_DOSYA, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                kayit = json.loads(satir)
                kaynak[kayit["varyant"]] = kayit["kaynaklar"]

    def ornek_yaz(f, varyant, soru, cevap):
        """Tek bir (system + user + assistant) eğitim örneği yazar."""
        kayit = {
            "messages": [
                {"role": "system", "content": sistem_mesaji(varyant, kaynak[varyant])},
                {"role": "user", "content": soru},
                {"role": "assistant", "content": cevap.strip()},
            ]
        }
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")

    ozet_n, takip_n, atlanan = 0, 0, []
    with open(CIKTI, "w", encoding="utf-8") as f:
        # 1) Özet örnekleri
        for varyant, ozet in OZETLER.items():
            if varyant not in kaynak:
                atlanan.append(varyant)
                continue
            ornek_yaz(f, varyant, f"{varyant} varyantını kaynaklı olarak özetle.", ozet)
            ozet_n += 1
        # 2) Takip-soru örnekleri (aynı kaynaklar, odaklı soru-cevap)
        for t in TAKIP:
            varyant = t["varyant"]
            if varyant not in kaynak:
                atlanan.append(f"{varyant} (takip)")
                continue
            ornek_yaz(f, varyant, t["soru"], t["cevap"])
            takip_n += 1

    print(f"{ozet_n} özet + {takip_n} takip = {ozet_n + takip_n} eğitim örneği "
          f"-> {os.path.basename(CIKTI)}")
    if atlanan:
        print(f"Kaynağı bulunamayan (atlanan): {', '.join(atlanan)}")


if __name__ == "__main__":
    main()
