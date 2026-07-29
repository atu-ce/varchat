"""
FINE-TUNE — Adım 1: KAYNAK ÇEKME (LLM YOK).

~15 varyant için PubMed makalelerini çeker ve KAYNAKLARI bir dosyaya yazar.
Sonra bu kaynaklar okunup, öğretmen (Claude) tarafından temiz, kaynaklı Türkçe
özetler yazılır -> (varyant + kaynaklar -> özet) = fine-tune eğitim verisi.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from c01_makale_getir import makale_ara, makale_detaylari_al
from c03_varchat_gemini import baglam_metni, arama_terimi_belirle

CIKTI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaynaklar.jsonl")

# İyi çalışılmış, literatürü bol varyantlar (çeşitli gen/kanser/mekanizma)
VARYANTLAR = [
    "BRAF V600E", "EGFR L858R", "EGFR T790M", "KRAS G12C", "KRAS G12D",
    "TP53 R175H", "JAK2 V617F", "PIK3CA H1047R", "NRAS Q61R", "IDH1 R132H",
    "KIT D816V", "FLT3 D835Y", "MYD88 L265P", "CFTR F508del", "AKT1 E17K",
]


def main():
    yazilan = 0
    with open(CIKTI, "w", encoding="utf-8") as f:
        for i, v in enumerate(VARYANTLAR, start=1):
            terim = arama_terimi_belirle(v)
            makaleler = makale_detaylari_al(makale_ara(terim, adet=5)[0])
            if not makaleler:
                print(f"[{i:2}] {v}: makale yok, atlandı")
                continue
            f.write(json.dumps({"varyant": v, "kaynaklar": baglam_metni(makaleler)},
                               ensure_ascii=False) + "\n")
            f.flush()
            yazilan += 1
            print(f"[{i:2}] {v}: {len(makaleler)} makale ✓")
    print(f"\n{yazilan} varyantın kaynağı yazıldı -> {os.path.basename(CIKTI)}")


if __name__ == "__main__":
    main()
