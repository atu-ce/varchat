"""
Uçtan uca akış (koordinat -> makaleler). İki parçayı birleştirir:
  1) ANLAMLANDIR: chr1:17001759:A>T  ->  gen (ATP13A2), rsID   [varyant_anlamlandir.py'den]
  2) ARA:         gen adı            ->  PubMed makaleleri      [makale_getir.py'den]

Hocanın koordinat formatını girince, otomatik olarak gen bulup ilgili makaleleri getirir.
(Henüz LLM/özet yok; önce bu iki parçanın düzgün birleştiğini görüyoruz.)
"""

import sys

from varyant_anlamlandir import anlamlandir
from makale_getir import makale_idleri_bul, makale_detaylari_al

sys.stdout.reconfigure(encoding="utf-8")


def main():
    varyant = "chr1:17001759:A>T"
    print(f"Girilen varyant (koordinat): {varyant}\n")

    # 1) ANLAMLANDIR: koordinat -> gen / rsID
    print("1) Anlamlandırılıyor (VEP)...")
    bilgi = anlamlandir(varyant)
    if "hata" in bilgi:
        print("   Hata:", bilgi["hata"])
        return
    genler = bilgi["genler"]
    print(f"   Gen(ler): {genler}")
    print(f"   rsID: {bilgi['rsid']}")
    print(f"   Etki: {bilgi['etki']}\n")

    if not genler:
        print("Bu varyant bir gene düşmüyor (örn. intergenik); arama yapılamıyor.")
        return

    # 2) ARA: bulunan geni PubMed'de arıyoruz
    arama_terimi = genler[0]   # şimdilik ilk geni kullanıyoruz
    print(f"2) PubMed'de aranıyor: '{arama_terimi}'...")
    pmidler = makale_idleri_bul(arama_terimi, adet=5)
    makaleler = makale_detaylari_al(pmidler)
    print(f"   {len(makaleler)} makale bulundu.\n")

    # Sonuçları göster
    print("=" * 70)
    for i, m in enumerate(makaleler, start=1):
        print(f"[{i}] {m['baslik']}")
        print(f"    https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
