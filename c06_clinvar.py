"""
ClinVar KATMANI (v2.1) — varyantın klinik önemini (patojenik/benign) kanıt düzeyiyle çeker.

VarChat'in "veri tabanı katmanı" gibi: literatür özetinin yanına, varyantın ClinVar'daki klinik
SINIFLANDIRMASINI ve HASTALIĞINI ekler.

v2 ile gelenler:
  - rsID yolu: rs334 gibi girdilerde (ve koordinat girdisinde VEP'in verdiği rsID ile) kayıt bulunur;
    esummary'deki dbSNP çapraz referansı (variation_xrefs) ile kaydın gerçekten o rsID'ye ait olduğu doğrulanır.
  - NCBI 2024 şeması: üç sınıflandırma birlikte okunur: germline (kalıtsal), onkojenite (tümör),
    klinik etki (somatik, Tier I-IV). BRAF V600E germline'da "çelişkili" iken onkojenitede "Oncogenic, Tier I".
  - Yıldız: ClinVar inceleme durumu 0-4 yıldıza çevrilir (somatik "criteria provided, multiple submitters" = 2).
  - Eski adlar: MTHFR C677T, Faktör V Leiden, GJB2 35delG gibi klinikte yaygın, ClinVar başlığıyla eşleşmeyen adlar rsID'ye çevrilir.
v2.1 (denetim sonrası):
  - Kanonik kaydı seçme sırası: kullanıcının/VEP'in protein değişimi > cDNA > genomik (m.) > gönderim sayısı > yıldız.
    Çıplak çok alelli rsID'de (rs113488022: A/C/G/T) c02 kartı ClinVar önemi olan aleli seçtiyse (klinik_alel_sec) o alel kullanılır,
    böylece anlamlandırma satırı ile ClinVar satırı aynı aleli gösterir (rs121913671: D1228N); seçemediyse en çok gönderimli alel.
  - Hastalıklar: VCV XML'inden koşul başına gönderim sayısı (RCV SubmissionCount); HPO fenotip terimleri ('Abdominal pain') ve
    'not provided' elenir. 'drug response' toplu sınıfı ayrı etiketlenir, patojenite gönderimleri koşul bazında gösterilir.
  - Somatik satırlar önce; özet yıldızı üç sınıfın en büyüğü; referans/sinonim ('=') başlıklar aday dışı; boş girdi -> None.

ÖNEMLİ — kesinlik: yanlış klinik önem = tehlikeli bilgi. Emin olunamıyorsa None döner (hiç gösterilmez).
"""

import re
import sys
import xml.etree.ElementTree as ET

from c01_makale_getir import ncbi_get
from c07_sorgu_kur import varyant_kaydi

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Klinikte yaygın eski/nükleotid adlar -> dbSNP kimliği (ClinVar başlıkları bunları farklı yazar)
ESKI_ADLAR = {
    "MTHFR C677T": "rs1801133", "MTHFR A1298C": "rs1801131",
    "F5 R506Q": "rs6025", "F5 LEIDEN": "rs6025", "FACTOR V LEIDEN": "rs6025", "F5 V LEIDEN": "rs6025",
    "F2 G20210A": "rs1799963", "SERPINA1 E342K": "rs28929474", "SERPINA1 Z": "rs28929474",
    "HFE C282Y": "rs1800562", "HFE H63D": "rs1799945", "HBB E6V": "rs334",
    "GJB2 35DELG": "rs80338939", "BRCA1 5382INSC": "rs80357906", "BRCA1 185DELAG": "rs386833395",
    # 26 Eylül: VEP ile doğrulanmış ek eski adlar (E264V = S aleli, olgun protein numaralaması; E26K = HbE; 6174delT = c.5946del)
    "SERPINA1 E264V": "rs17580", "SERPINA1 S": "rs17580", "HBB E26K": "rs33950507", "BRCA2 6174DELT": "rs80359550",
}

# ClinVar inceleme durumu -> yıldız (resmi tablo: practice guideline 4, expert panel 3, multiple submitters 2, single/conflicting 1, none 0)
YILDIZ = [
    ("practice guideline", 4), ("reviewed by expert panel", 3),
    ("criteria provided, multiple submitters, no conflicts", 2),
    ("criteria provided, conflicting", 1),
    ("criteria provided, multiple submitters", 2),     # somatik (clinical impact) biçimi: 'no conflicts' eki yok
    ("criteria provided, single submitter", 1),
    ("no assertion", 0), ("no classification", 0),
]
ATLA = ("not provided", "not specified", "see cases")
SINIF_ALANLARI = ("germline_classification", "oncogenicity_classification", "clinical_impact_classification")


def yildiz(inceleme):
    inceleme = (inceleme or "").lower()
    for anahtar, y in YILDIZ:
        if anahtar in inceleme:
            return y
    return 0


def _sinif(kayit, alan):
    """esummary'deki sınıflandırma alanını (germline_classification vb.) sadeleştirir."""
    s = kayit.get(alan) or {}
    if not s.get("description"):
        return None
    return {"onem": s.get("description"), "inceleme": s.get("review_status") or "", "yildiz": yildiz(s.get("review_status")),
            "hastaliklar": [t.get("trait_name", "") for t in (s.get("trait_set") or []) if t.get("trait_name")]}


def _gonderim_sayisi(kayit):
    ss = kayit.get("supporting_submissions") or {}
    return len(ss.get("scv") or []) if isinstance(ss, dict) else 0


def _rsid_eslesiyor(kayit, rsid):
    numara = rsid.lower().replace("rs", "")
    for vs in kayit.get("variation_set") or []:
        for x in vs.get("variation_xrefs") or []:
            if (x.get("db_source") or "").lower() == "dbsnp" and str(x.get("db_id")) == numara:
                return True
    return False


def _adaylari_cek(terim, retmax=50):
    p = {"db": "clinvar", "term": terim, "retmax": retmax, "retmode": "json", "sort": "relevance"}
    idler = ncbi_get(ESEARCH, p).json().get("esearchresult", {}).get("idlist", [])
    if not idler:
        return []
    sonuc = ncbi_get(ESUMMARY, {"db": "clinvar", "id": ",".join(idler), "retmode": "json"}).json().get("result", {})
    return [dict(sonuc[uid], uid=uid) for uid in idler if uid in sonuc and sonuc[uid].get("title")]


def _rcv_kosullari(uid):
    """VCV XML'inden koşul başına gönderim sayısı: [(gonderim, sinif_turu, sinif, kosul)] çoktan aza. Ağ hatasında []."""
    try:
        x = ncbi_get(EFETCH, {"db": "clinvar", "id": uid, "rettype": "vcv", "is_variationid": "", "from_esearch": "true"}).text
        root = ET.fromstring(x)
    except Exception:
        return []
    satirlar = []
    for rcv in root.iter("RCVAccession"):
        kosullar = [(c.text or "").strip() for c in rcv.iter("ClassifiedCondition")]
        if len(kosullar) != 1:                       # birleşik (A / B / C) RCV'ler sayımı bozar
            continue
        for k in rcv.findall("./RCVClassifications/*"):
            d = k.find("Description")
            if d is None or not d.text or "no classifications" in d.text.lower():
                continue
            satirlar.append((int(d.get("SubmissionCount") or 0), k.tag, d.text.strip(), kosullar[0]))
    return sorted(satirlar, key=lambda s: -s[0])


def _hastaliklar(kayit, rcv=None):
    """RCV gönderim sayısına göre; yoksa esummary sırası + HPO fenotip terimleri elenir. En fazla 4."""
    if rcv:
        gorulen, cikti = set(), []
        for sayi, _, _, kosul in rcv:
            if kosul.lower() in ATLA or kosul in gorulen:
                continue
            gorulen.add(kosul)
            cikti.append((sayi, kosul))
        guclu = [k for s, k in cikti if s >= 2]
        return (guclu if len(guclu) >= 2 else [k for _, k in cikti])[:4]
    cikti = []
    for alan in SINIF_ALANLARI:
        for t in ((kayit.get(alan) or {}).get("trait_set") or []):
            ad = (t.get("trait_name") or "").strip()
            kaynaklar = {(x.get("db_source") or "") for x in (t.get("trait_xrefs") or [])}
            if not ad or ad.lower() in ATLA or ad in cikti:
                continue
            if "Human Phenotype Ontology" in kaynaklar and not kaynaklar & {"OMIM", "Orphanet"}:
                continue                              # 'Abdominal pain' gibi fenotip terimleri hastalık değil
            cikti.append(ad)
    return cikti[:4]


def _protein_etiketi(baslik):
    m = re.search(r"\(p\.([A-Za-z0-9_*=]+)\)", baslik or "")
    return m.group(1).lower() if m else None


def _kayit_ozeti(kayit, rcv=None):
    germ = _sinif(kayit, "germline_classification")
    onko = _sinif(kayit, "oncogenicity_classification")
    etki = _sinif(kayit, "clinical_impact_classification")
    ana = germ or onko or etki
    return {
        "baslik": kayit.get("title", ""),
        "onem": ana["onem"] if ana else "bilinmiyor",
        "inceleme": ana["inceleme"] if ana else "",
        "yildiz": max((s["yildiz"] for s in (germ, onko, etki) if s), default=0),
        "germline": germ, "onkojenite": onko, "klinik_etki": etki,
        "hastaliklar": _hastaliklar(kayit, rcv),
        # patojenite RCV satırları (ilaç yanıtı ve 'not provided' dışı) — en fazla 3
        "rcv": [(s, sinif, kosul) for s, tur, sinif, kosul in rcv
                if tur == "GermlineClassification" and kosul.lower() not in ATLA and sinif.lower() != "drug response"][:3] if rcv else [],
        "gonderim": _gonderim_sayisi(kayit),
        "link": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{kayit['uid']}/",
    }


def _kanonik_sec(adaylar, birincil=None, cdna=None, genomik=None):
    """Sıralama: protein eşleşmesi > cDNA > genomik (m.3243A>G) > gönderim sayısı > yıldız > '[' yok > delins değil."""
    def puan(k):
        b = (k.get("title") or "").lower()
        yil = max(yildiz((k.get(a) or {}).get("review_status")) for a in SINIF_ALANLARI)
        return (bool(birincil) and birincil.lower() in b, bool(cdna) and cdna.lower() in b,
                bool(genomik) and genomik.lower() in b, _gonderim_sayisi(k), yil, "[" not in b, "delins" not in b)
    return max(adaylar, key=puan) if adaylar else None


def _eski_ad(girdi, kayit_bilgi):
    """Eski ad tablosunda ara: ham girdi, temizlenmiş girdi, 'GEN DEĞİŞİM', 'GEN İFADE' anahtarlarıyla."""
    adaylar = [girdi, kayit_bilgi.get("girdi") or ""]
    if kayit_bilgi.get("gen") and kayit_bilgi.get("protein_kisa"):
        adaylar.append(f"{kayit_bilgi['gen']} {kayit_bilgi['protein_kisa']}")
    if kayit_bilgi.get("gen") and kayit_bilgi.get("ek_terimler"):
        adaylar.append(f"{kayit_bilgi['gen']} {kayit_bilgi['ek_terimler'][0]}")
    for a in adaylar:
        a = re.sub(r"\s+", " ", a.strip().rstrip("?!.,;")).upper()
        if a in ESKI_ADLAR:
            return ESKI_ADLAR[a]
    return None


def clinvar_bilgisi(varyant, kayit=None):
    """Varyantı ClinVar'da güvenle bulursa klinik önem sözlüğü, bulamazsa None döndürür.
    kayit: c07.varyant_kaydi çıktısı (varsa yeniden VEP'e gidilmez).
    Yollar: rsID (girdi rsID ise, koordinatsa VEP'in rsID'si, eski adsa tablo) -> dbSNP xref doğrulaması;
            gen + protein değişimi -> başlıkta 3-harfli değişim eşleşmesi."""
    girdi = (varyant or "").strip()
    if not girdi:
        return None
    kayit_bilgi = kayit or varyant_kaydi(girdi)
    kart = kayit_bilgi.get("kart") or {}
    rsid = _eski_ad(girdi, kayit_bilgi) or (kayit_bilgi.get("rsid") or [None])[0]
    protein3 = [p for p in [kayit_bilgi.get("protein_3harf"), *kayit_bilgi.get("protein_diger", [])]
                if p and re.match(r"^[A-Z][a-z]{2}\d+", p)]
    gen = kayit_bilgi.get("gen")
    # Çıplak rsID + çok alelli kayıt: kart alelini ClinVar kanıtıyla seçtiyse (c02.klinik_alel_sec) o alel esas alınır;
    # yalnızca sıklık/etkiyle seçtiyse protein/cDNA seçimde kullanılmaz (en çok gönderimli kayıt)
    cok_alelli = kayit_bilgi.get("tur") == "rsid" and (kart.get("alel") or "").count("/") > 1
    kart_aleli = cok_alelli and kart.get("alel_secim_nedeni") in ("klinik", "clinvar_kaydi")
    birincil = None if (cok_alelli and not kart_aleli) else kayit_bilgi.get("protein_3harf")
    cdna = None if (cok_alelli and not kart_aleli) else kayit_bilgi.get("cdna")
    genomik = (kart.get("hgvs_g") or "").split("g.")[-1] if kart.get("hgvs_g") else None

    def uygun(k):
        b = k.get("title") or ""
        return "[" not in b and ("=)" not in b or (birincil or "").endswith("="))   # haplotip ve referans/sinonim kayıt dışı

    adaylar = []
    if rsid:
        adaylar = [k for k in _adaylari_cek(rsid) if _rsid_eslesiyor(k, rsid) and uygun(k)]
        if protein3 and any(any(p.lower() in (k.get("title") or "").lower() for p in protein3) for k in adaylar):
            adaylar = [k for k in adaylar if any(p.lower() in (k.get("title") or "").lower() for p in protein3)]
    if not adaylar and gen and protein3:
        terim = f"{gen}[gene] AND ({' OR '.join(protein3)})"
        adaylar = [k for k in _adaylari_cek(terim)
                   if any(p.lower() in (k.get("title") or "").lower() for p in protein3) and uygun(k)]
    if not adaylar:
        return None   # emin değiliz -> hiç gösterme
    secilen = _kanonik_sec(adaylar, birincil, cdna, genomik)
    rcv = _rcv_kosullari(secilen["uid"])                            # koşul bazında gönderim sayıları (1 ek istek)
    ozet = _kayit_ozeti(secilen, rcv)
    ozet["aday_sayisi"] = len(adaylar)
    ozet["cok_alelli"] = cok_alelli
    ozet["kart_aleli"] = kart_aleli
    # Aynı protein değişiminin başka gösterimi 'diğer kayıt' değildir (CFTR c.1522_1524del)
    sec_p = _protein_etiketi(secilen.get("title"))
    baska, ayni = [], 0
    for k in adaylar:
        if k is secilen or k.get("title") == secilen.get("title"):
            continue
        if sec_p and _protein_etiketi(k.get("title")) == sec_p:
            ayni += 1
        else:
            baska.append(k.get("title"))
    ozet["diger_kayitlar"] = sorted(set(baska))[:3]
    ozet["ayni_degisim_tekrar"] = ayni
    return ozet


def clinvar_satirlari(cv):
    """Kullanıcıya gösterilecek satırlar (c04 kullanır). Somatik satırlar önce; ilaç yanıtı ayrı etiket."""
    satirlar = []
    e, o, g = cv.get("klinik_etki"), cv.get("onkojenite"), cv.get("germline")
    if e:
        satirlar.append(f"ClinVar — Klinik etki (somatik, tümör): {e['onem']} ({e['yildiz']}★, {e['inceleme']})")
    if o:
        satirlar.append(f"ClinVar — Onkojenite (tümör): {o['onem']} ({o['yildiz']}★, {o['inceleme']})")
    if g:
        if g["onem"].lower() == "drug response":
            satirlar.append(f"ClinVar — İlaç yanıtı (farmakogenomik, uzman paneli): {', '.join(g['hastaliklar']) or g['onem']} ({g['yildiz']}★)")
        else:
            ek = " — kalıtsal/mozaik bağlam; tümördeki anlamı için yukarıdaki satırlara bakın" if (e or o) and "conflicting" in g["onem"].lower() else ""
            satirlar.append(f"ClinVar — Germline (kalıtsal): {g['onem']} ({g['yildiz']}★, {g['inceleme']}){ek}")
    if not satirlar:
        satirlar.append(f"ClinVar — Klinik önem: {cv['onem']} ({cv['yildiz']}★)")
    if cv.get("rcv") and (not g or g["onem"].lower() == "drug response" or "conflicting" in g["onem"].lower()):
        satirlar.append("  Koşul bazında gönderimler: " + "; ".join(f"{sinif} — {kosul} ({s} gönderim)" for s, sinif, kosul in cv["rcv"]))
    if cv.get("hastaliklar"):
        satirlar.append(f"  İlişkili hastalık(lar): {', '.join(cv['hastaliklar'])}")
    if cv.get("yildiz", 0) <= 1:
        satirlar.append("  (zayıf kanıt: tek gönderici ya da çelişkili; dikkatle yorumlayın)")
    if cv.get("cok_alelli"):
        satirlar.append("  (bu rsID birden çok aleli kapsar; " + ("anlamlandırma kartındaki klinik alel gösterildi)" if cv.get("kart_aleli")
                                                                 else "en çok gönderimi olan alel gösterildi)"))
    if cv.get("diger_kayitlar"):
        satirlar.append(f"  Diğer eşleşen kayıt(lar): {' | '.join(cv['diger_kayitlar'])}")
    satirlar.append(f"  {cv['baslik']} — {cv['link']}")
    return satirlar


if __name__ == "__main__":
    for v in ["BRAF V600E", "rs113488022", "KRAS G12C", "rs334", "HBB E6V", "MTHFR C677T nedir", "Factor V Leiden?",
              "F2 G20210A", "HFE C282Y", "GJB2 35delG", "EGFR L858R/T790M", "CFTR F508del", "chr1:62578974:CAA>C",
              "chrM:3243:A>G", "TP53 R213*", "chr1:17001759:A>T", ""]:
        print(f"=== {v} ===")
        try:
            b = clinvar_bilgisi(v)
        except Exception as e:
            print(f"  HATA: {type(e).__name__}: {e}")
            continue
        if b is None:
            print("  (ClinVar'da doğrulanmış kayıt yok / gösterilmiyor)")
        else:
            for s in clinvar_satirlari(b):
                print(" ", s)
        print()
