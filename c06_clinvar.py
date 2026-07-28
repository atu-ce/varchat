"""
ClinVar KATMANI — varyantın klinik önemini (patojenik/benign) çeker.

VarChat'in "veri tabanı katmanı" gibi: literatür özetinin yanına, varyantın
ClinVar'daki klinik SINIFLANDIRMASINI ve HASTALIĞINI ekler.

ÖNEMLİ — kesinlik: ClinVar serbest-metin araması yanlış aleli getirebilir (aynı
pozisyonda birçok varyant olabilir). Yanlış klinik önem = tehlikeli bilgi. Bu yüzden:
  1) Birçok aday çekeriz,
  2) Başlığı, sorulan protein değişimiyle (örn. V600E -> Val600Glu) TAM eşleşeni seçeriz,
  3) Emin olamazsak HİÇBİR ŞEY göstermeyiz (None).
Şu an yalnızca "gen + protein değişimi" (BRAF V600E) girdilerini güvenle doğrulayabiliriz.

NCBI E-utilities (PubMed ile aynı altyapı) kullanır; ücretsiz.
"""

import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EMAIL = "yazilimbirimi@karacasutekstil.com.tr"
TOOL = "varchat-tez-prototip"

# Tek harf -> üç harf amino asit (ClinVar başlıkları 3-harfli kullanır: p.Val600Glu)
AMINO = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys", "E": "Glu", "Q": "Gln",
    "G": "Gly", "H": "His", "I": "Ile", "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe",
    "P": "Pro", "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val",
}


def protein_degisimi_3harf(varyant):
    """'BRAF V600E' -> 'Val600Glu' (ClinVar başlığındaki form). Bulamazsa None."""
    m = re.search(r"\b([A-Z])(\d+)([A-Z])\b", varyant.upper())
    if not m:
        return None
    a1, pos, a2 = m.groups()
    if a1 in AMINO and a2 in AMINO:
        return f"{AMINO[a1]}{pos}{AMINO[a2]}"
    return None


def _kayit_ozeti(kayit, uid):
    sinif = kayit.get("germline_classification") or kayit.get("clinical_significance") or {}
    trait_set = sinif.get("trait_set") or kayit.get("trait_set") or []
    hastaliklar = [t.get("trait_name", "") for t in trait_set if t.get("trait_name")]
    return {
        "baslik": kayit.get("title", ""),
        "onem": sinif.get("description") or "bilinmiyor",
        "inceleme": sinif.get("review_status") or "",
        "hastaliklar": hastaliklar[:5],
        "link": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/",
    }


def clinvar_bilgisi(varyant):
    """Varyantı ClinVar'da güvenle bulursa klinik önem bilgisini, bulamazsa None döndürür."""
    hedef = protein_degisimi_3harf(varyant)
    if not hedef:
        return None   # protein değişimi yoksa doğrulayamayız -> yanlış göstermektense hiç gösterme

    # 1) Aday kayıtları çek (alaka sırasıyla)
    p = {"db": "clinvar", "term": varyant, "retmax": 50, "retmode": "json",
         "sort": "relevance", "email": EMAIL, "tool": TOOL}
    idler = requests.get(ESEARCH, params=p, timeout=30).json()["esearchresult"]["idlist"]
    if not idler:
        return None

    # 2) Hepsinin özetini al
    p2 = {"db": "clinvar", "id": ",".join(idler), "retmode": "json", "email": EMAIL, "tool": TOOL}
    sonuc = requests.get(ESUMMARY, params=p2, timeout=30).json()["result"]

    # 3) Başlığı hedef protein değişimini TAM içeren ilk kaydı seç
    for uid in idler:
        kayit = sonuc.get(uid, {})
        if hedef.lower() in kayit.get("title", "").lower():
            return _kayit_ozeti(kayit, uid)

    return None   # tam eşleşme yok -> emin değiliz, gösterme


if __name__ == "__main__":
    for v in ["BRAF V600E", "EGFR L858R", "KRAS G12C", "TP53 R175H", "rs334", "chr1:17001759:A>T"]:
        print(f"=== {v} ===")
        b = clinvar_bilgisi(v)
        if b is None:
            print("  (ClinVar'da doğrulanmış kayıt yok / gösterilmiyor)")
        else:
            print(f"  Başlık: {b['baslik']}")
            print(f"  Klinik önem: {b['onem']}  ({b['inceleme']})")
            print(f"  Hastalık: {', '.join(b['hastaliklar']) or '—'}")
            print(f"  Link: {b['link']}")
        print()
