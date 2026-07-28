"""
BENCHMARK 2 — Faithfulness (halüsinasyon) için veri üretimi.

Gerçek sistemi (c04 pipeline'ı, sıkılaştırılmış promptu) kullanarak birkaç varyant
özeti üretir ve KAYNAKLARIYLA birlikte bir dosyaya yazar. Sonra bu dosya okunup
her özet, kaynaklara sadık mı (yoksa uyduruyor mu) diye değerlendirilir.

Çıktı: faithfulness_verisi.jsonl  (her satır: varyant, kaynaklar, özet)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import c04_varchat_ollama as app          # gerçek sistemin pipeline'ı
from c03_varchat_gemini import baglam_metni

CIKTI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faithfulness_verisi.jsonl")

VARYANTLAR = ["BRAF V600E", "rs334", "TP53 R175H"]


def main():
    with open(CIKTI, "w", encoding="utf-8") as f:
        for v in VARYANTLAR:
            makaleler, sistem = app.varyant_baglami_kur(v)
            if not makaleler:
                print(f"{v}: makale yok, atlandı")
                continue
            grounded = [{"role": "system", "content": sistem}]
            print(f"{v}: özet üretiliyor (CPU, biraz sürer)...")
            ozet = app.grounded_sor(grounded, f"{v} varyantını kaynaklı olarak özetle.")
            f.write(json.dumps(
                {"varyant": v, "kaynaklar": baglam_metni(makaleler), "ozet": ozet},
                ensure_ascii=False) + "\n")
            f.flush()
            print(f"{v}: ✓ yazıldı ({len(ozet)} karakter)")

    print(f"\nBitti -> {os.path.basename(CIKTI)}")


if __name__ == "__main__":
    main()
