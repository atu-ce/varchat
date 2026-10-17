"""
BENCHMARK 1 — Retrieval alaka ölçümü (Faz 6, ilk adım).

Soru: Getirdiğimiz makaleler ne kadar alakalı?
Her varyant için çekilen 5 makalenin başlık+özetinde:
  - GEN adı geçiyor mu?          -> gen-düzeyi alaka
  - Spesifik VARYANT (V600E...)  -> varyant-düzeyi alaka

Aradaki fark, "gen buluyoruz ama tam varyantı ne kadar?" boşluğunu sayısallaştırır.
Tamamen yerel (sadece PubMed); Gemini/GPU gerektirmez.
"""

import os
import sys

# degerlendirme/ klasöründe: ana klasördeki modülleri bulmak için üst klasörü yola ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from c01_makale_getir import makale_ara, makale_detaylari_al
from c03_varchat_gemini import arama_terimi_belirle

# (girdi, gen, spesifik değişim) — hepsi iyi çalışılmış, bilinen varyantlar
TEST = [
    ("BRAF V600E", "BRAF", "V600E"),
    ("EGFR L858R", "EGFR", "L858R"),
    ("KRAS G12C", "KRAS", "G12C"),
    ("TP53 R175H", "TP53", "R175H"),
    ("JAK2 V617F", "JAK2", "V617F"),
    ("PIK3CA H1047R", "PIK3CA", "H1047R"),
    ("NRAS Q61R", "NRAS", "Q61R"),
    ("IDH1 R132H", "IDH1", "R132H"),
]


def icerir(makale, kelime):
    """Makalenin başlık+özetinde kelime geçiyor mu?"""
    metin = (makale["baslik"] + " " + makale["ozet"]).lower()
    return kelime.lower() in metin


def main():
    makale_toplam = gen_toplam = varyant_toplam = 0
    print(f"{'Varyant':16} | gen | varyant")
    print("-" * 34)
    for girdi, gen, degisim in TEST:
        terim = arama_terimi_belirle(girdi)
        makaleler = makale_detaylari_al(makale_ara(terim, adet=5)[0])
        n = len(makaleler)
        gen_sayi = sum(icerir(m, gen) for m in makaleler)
        var_sayi = sum(icerir(m, degisim) for m in makaleler)
        makale_toplam += n
        gen_toplam += gen_sayi
        varyant_toplam += var_sayi
        print(f"{girdi:16} | {gen_sayi}/{n} | {var_sayi}/{n}")

    print("-" * 34)
    print(f"\nToplam {makale_toplam} makale üzerinde:")
    print(f"  Gen-düzeyi alaka     : {gen_toplam}/{makale_toplam} = %{100*gen_toplam/makale_toplam:.0f}")
    print(f"  Varyant-düzeyi alaka : {varyant_toplam}/{makale_toplam} = %{100*varyant_toplam/makale_toplam:.0f}")


if __name__ == "__main__":
    main()
