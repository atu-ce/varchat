"""
VALİDASYON (Faz 2, ikinci yarı): varyant/gen kimliği geçerli mi?

Kullanıcı 'BRFA' gibi yanlış yazarsa yakalar ve 'BRAF mı demek istediniz?' diye önerir.
Geçerli gen sembolleri listesini (HGNC) genler.txt'de tutar; dosya yoksa bir kez indirir.

- Gen sembolü (BRAF, TP53...) -> listeye karşı doğrulanır; yanlışsa difflib ile öneri.
- rsID (rs334) ve koordinat (chr1:...) -> gen doğrulaması gerekmez; onları VEP/pipeline doğrular.
"""

import csv
import io
import os
import re
import sys

import requests
from rapidfuzz import process
from rapidfuzz.distance import JaroWinkler

sys.stdout.reconfigure(encoding="utf-8")

GENLER_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genler.txt")
HGNC_URLLER = [
    "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt",
    "https://ftp.ebi.ac.uk/pub/databases/genenames/hgnc/tsv/hgnc_complete_set.txt",
]


def _genleri_indir():
    """HGNC'den gen sembollerini indirip genler.txt'ye yazar, kümeyi döndürür."""
    for url in HGNC_URLLER:
        try:
            print(f"Gen listesi indiriliyor: {url}")
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            okuyucu = csv.DictReader(io.StringIO(r.text), delimiter="\t")
            semboller = sorted({
                row["symbol"].strip().upper()
                for row in okuyucu if row.get("symbol", "").strip()
            })
            with open(GENLER_DOSYA, "w", encoding="utf-8") as f:
                f.write("\n".join(semboller))
            print(f"  {len(semboller)} sembol genler.txt'ye kaydedildi.")
            return set(semboller)
        except Exception as e:
            print(f"  başarısız: {e}")
    raise RuntimeError("HGNC gen listesi indirilemedi.")


def gen_listesi_yukle():
    """genler.txt'yi (yoksa indirip) bir küme olarak döndürür."""
    if not os.path.exists(GENLER_DOSYA):
        return _genleri_indir()
    with open(GENLER_DOSYA, encoding="utf-8") as f:
        return {satir.strip() for satir in f if satir.strip()}


GEN_LISTESI = gen_listesi_yukle()   # küme: hızlı 'in' kontrolü için
_GEN_LISTE = list(GEN_LISTESI)      # rapidfuzz için liste hali


def gen_cikar(kimlik):
    """Varyant kimliğinden gen sembolünü çıkarır. rsID/koordinat için None döner."""
    k = kimlik.strip()
    if re.match(r"^rs\d+$", k, re.IGNORECASE):
        return None                                 # rsID -> gen doğrulaması yok
    if ":g." in k or (">" in k and k.count(":") >= 2):
        return None                                 # koordinat/HGVS -> VEP doğrular
    return re.split(r"[\s:]", k)[0].upper()         # gen sembolü (ilk token)


def gen_gecerli_mi(gen):
    """(gecerli_mi, oneriler) döndürür. Öneriler için Jaro-Winkler (önek ağırlıklı) benzerlik."""
    if gen in GEN_LISTESI:
        return True, []
    eslesmeler = process.extract(gen, _GEN_LISTE, scorer=JaroWinkler.normalized_similarity, limit=3)
    oneriler = [ad for ad, skor, _ in eslesmeler if skor >= 0.8]
    return False, oneriler


if __name__ == "__main__":
    print(f"\nGen listesi: {len(GEN_LISTESI)} sembol yüklü.\n")
    testler = ["BRAF V600E", "BRFA V600E", "rs334", "chr1:17001759:A>T", "TP53", "TPP53", "XQZWK"]
    for t in testler:
        gen = gen_cikar(t)
        if gen is None:
            print(f"{t!r:22} -> gen doğrulaması gerekmez (rsID/koordinat)")
        else:
            gecerli, oneriler = gen_gecerli_mi(gen)
            durum = "GEÇERLİ" if gecerli else f"GEÇERSİZ -> öneri: {oneriler}"
            print(f"{t!r:22} -> gen={gen}: {durum}")
