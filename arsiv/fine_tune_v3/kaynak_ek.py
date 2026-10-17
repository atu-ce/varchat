"""
FINE-TUNE — Adım 1b: YENİ VARYANT KAYNAKLARINI EKLE (LLM YOK).

kaynaklar.jsonl'daki mevcut satırlara DOKUNMADAN, yalnızca yeni varyantları
çeker ve dosyanın SONUNA ekler. Böylece önceden yazılmış özetlerin [n] atıfları
bozulmaz (mevcut varyantlar yeniden çekilmez).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from c01_makale_getir import makale_ara, makale_detaylari_al
from c03_varchat_gemini import baglam_metni, arama_terimi_belirle

DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaynaklar.jsonl")

# Farklı gen/hastalık: CML, AML, GIST, MTC, meme, pankreas, herediter, MDS
EK_VARYANTLAR = [
    "ABL1 T315I", "IDH2 R140Q", "DNMT3A R882H", "PDGFRA D842V", "RET M918T",
    "ESR1 Y537S", "PIK3CA E545K", "KRAS G12V", "HFE C282Y", "SF3B1 K700E",
    # 2. parti: promoter, GPCR/uveal, Wnt, DNA polimeraz, FGFR, MPN, prostat, pediatrik
    "TERT promoter C228T", "GNAQ Q209L", "CTNNB1 S45F", "POLE P286R",
    "TP53 R248Q", "KRAS G13D", "FGFR3 S249C", "MPL W515L",
    "AR T878A", "PTEN R130Q", "HRAS G12V", "ALK F1174L",
]


def mevcut_varyantlar():
    if not os.path.exists(DOSYA):
        return set()
    var = set()
    with open(DOSYA, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                var.add(json.loads(satir)["varyant"])
    return var


def main():
    zaten = mevcut_varyantlar()
    eklenen = 0
    with open(DOSYA, "a", encoding="utf-8") as f:
        for i, v in enumerate(EK_VARYANTLAR, start=1):
            if v in zaten:
                print(f"[{i:2}] {v}: zaten var, atlandı")
                continue
            terim = arama_terimi_belirle(v)
            makaleler = makale_detaylari_al(makale_ara(terim, adet=5)[0])
            if not makaleler:
                print(f"[{i:2}] {v}: makale yok, atlandı")
                continue
            f.write(json.dumps({"varyant": v, "kaynaklar": baglam_metni(makaleler)},
                               ensure_ascii=False) + "\n")
            f.flush()
            eklenen += 1
            print(f"[{i:2}] {v}: {len(makaleler)} makale ✓")
    print(f"\n{eklenen} yeni varyant eklendi -> {os.path.basename(DOSYA)}")


if __name__ == "__main__":
    main()
