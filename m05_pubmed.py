"""
KÜTÜPHANECİ — PubMed'den makale çekme (RAG'ın "retrieval" parçası). LLM yok.

Amaç: Bir arama terimi verince PubMed'den GERÇEK makalelerin başlık + özetini (abstract) çekmek.

v2 ile gelenler:
  - PubMed'in SESSİZCE düşürdüğü terimler okunur (errorlist.phrasesnotfound + warninglist.quotedphrasesnotfound).
    Eskiden "KCNQ1 p.Arg555Cys" girdisi sessizce "KCNQ1" aramasına dönüşüyor ve "2.843 makale bulundu" deniyordu.
  - Yalnızca İngilizce özet alınır (Article/Abstract; OtherAbstract = yabancı dildeki özet, LLM'e gitmez); yapısal özet
    etiketleri korunur ("RESULTS: ..."); yıl, dergi, ilk yazar, yayın türü, geri çekilme durumu çekilir.
  - NCBI hız sınırı (anahtarsız 3 istek/sn) için istekler arasında bekleme; 429/5xx'te yeniden deneme (Retry-After);
    .env'de NCBI_API_KEY varsa kullanılır (10 istek/sn).
"""

import os
import re
import sys                           # terminal çıktı ayarı için
import time                          # NCBI'yi yormamak için aralara minik bekleme koyacağız
import xml.etree.ElementTree as ET   # PubMed'in XML cevabını okumak için (Python'la hazır gelir)

import requests                      # internetten veri çekmek için (HTTP istekleri)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows terminali α, β, ≥ gibi karakterlerde çökmesin
except (AttributeError, ValueError):
    pass

# --- NCBI E-utilities: PubMed'in resmi programlama kapısı (API) adresleri ---
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"   # arama -> PMID listesi
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"     # PMID -> başlık, özet (XML)

EMAIL = "yazilimbirimi@karacasutekstil.com.tr"   # NCBI etiketi (nazik kullanım)
TOOL = "varchat-tez-prototip"
API_KEY = os.environ.get("NCBI_API_KEY", "").strip() or None
ARALIK = 0.12 if API_KEY else 0.36               # istekler arası en az bekleme (10/sn ya da 3/sn)
_son_istek = 0.0
GURULTU_TUR = ("Research Support", "Journal Article", "English Abstract")


def ncbi_get(url, params, deneme=3):
    """NCBI'ye hız sınırına uyarak GET atar; 429/5xx ve ağ hatasında bekleyip yeniden dener."""
    global _son_istek
    params = dict(params, email=EMAIL, tool=TOOL)
    if API_KEY:
        params["api_key"] = API_KEY
    son_hata = None
    for i in range(deneme):
        bekle = ARALIK - (time.time() - _son_istek)
        if bekle > 0:
            time.sleep(bekle)
        _son_istek = time.time()
        try:
            cevap = requests.get(url, params=params, timeout=30)
        except requests.RequestException as e:
            son_hata = f"ağ hatası ({type(e).__name__})"
            if i < deneme - 1:
                time.sleep(1.5 * (i + 1))
            continue
        if cevap.status_code in (429, 500, 502, 503, 504):
            son_hata = f"NCBI {cevap.status_code}"
            if i < deneme - 1:
                try:
                    time.sleep(min(float(cevap.headers.get("Retry-After", 1.5 * (i + 1))), 10))
                except ValueError:
                    time.sleep(1.5 * (i + 1))
            continue
        cevap.raise_for_status()
        return cevap
    raise RuntimeError(f"NCBI'ye ulaşılamadı: {son_hata}")


def makale_ara_ayrintili(terim, adet=5):
    """PubMed araması; sonuç sözlüğü:
       pmidler  : ilk 'adet' PMID (alaka sırasıyla)
       toplam   : eşleşen makale sayısı
       ceviri   : PubMed'in sorguyu çevirdiği hali (querytranslation)
       dusen    : PubMed'in bulamayıp SESSİZCE attığı ifadeler (phrasesnotfound + quotedphrasesnotfound)"""
    parametreler = {"db": "pubmed", "term": terim, "retmax": adet, "retmode": "json", "sort": "relevance"}
    sonuc = ncbi_get(ESEARCH, parametreler).json().get("esearchresult", {})
    hata = sonuc.get("errorlist", {}) or {}
    uyari = sonuc.get("warninglist", {}) or {}
    dusen = list(hata.get("phrasesnotfound", []) or []) + list(uyari.get("quotedphrasesnotfound", []) or [])
    return {
        "pmidler": sonuc.get("idlist", []),
        "toplam": int(sonuc.get("count", 0) or 0),
        "ceviri": sonuc.get("querytranslation", ""),
        "dusen": dusen,
    }


def makale_ara(varyant, adet=5):
    """Geriye dönük uyumluluk: (PMID listesi, toplam eşleşme sayısı) döndürür."""
    s = makale_ara_ayrintili(varyant, adet)
    return s["pmidler"], s["toplam"]


def makale_idleri_bul(varyant, adet=5):
    """Geriye dönük uyumluluk için: yalnızca PMID listesini döndürür."""
    return makale_ara(varyant, adet)[0]


def butun_metin(element):
    """Bir XML etiketinin içindeki TÜM metni, iç içe etiketler (örn. <i> italik) dahil birleştirir."""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _yil(art):
    """PubDate/Year, yoksa MedlineDate ('Summer 2001', '1998 Dec-1999 Jan') ya da ArticleDate içinden 4 haneli yıl."""
    for yol in ("./Journal/JournalIssue/PubDate/Year", "./Journal/JournalIssue/PubDate/MedlineDate", "./ArticleDate/Year"):
        el = art.find(yol)
        if el is not None and el.text:
            m = re.search(r"\d{4}", el.text)
            if m:
                return m.group(0)
    return ""


def makale_detaylari_al(pmid_listesi):
    """PMID'lerin başlık, özet ve künyesini çeker. Sözlük anahtarları:
       pmid, baslik, ozet (İngilizce; etiketli parçalar 'RESULTS: ...' biçiminde), yil, dergi, yazar, yazar_sayisi,
       tur (Review / Case Reports / Meta-Analysis gibi; 'Research Support' gürültüsü atılır), geri_cekildi, dil"""
    if not pmid_listesi:
        return []
    parametreler = {"db": "pubmed", "id": ",".join(str(p) for p in pmid_listesi), "rettype": "abstract", "retmode": "xml"}
    cevap = ncbi_get(EFETCH, parametreler)
    kok = ET.fromstring(cevap.text)
    makaleler = []
    for makale in kok.findall(".//PubmedArticle"):
        art = makale.find("./MedlineCitation/Article")
        if art is None:
            continue
        baslik = butun_metin(art.find("./ArticleTitle")) or "(başlık yok)"
        # Yalnızca Article/Abstract (İngilizce); OtherAbstract (yabancı dil) alınmaz. Etiketler korunur.
        parcalar = []
        for el in art.findall("./Abstract/AbstractText"):
            metin = butun_metin(el)
            if not metin:
                continue
            etiket = el.get("Label")
            parcalar.append(f"{etiket}: {metin}" if etiket else metin)
        ozet = " ".join(parcalar) or "(özet yok)"
        pmid_el = makale.find("./MedlineCitation/PMID")
        dergi = butun_metin(art.find("./Journal/ISOAbbreviation")) or butun_metin(art.find("./Journal/Title"))
        yazarlar = art.findall("./AuthorList/Author")
        yazar = ""
        for y in yazarlar:
            yazar = butun_metin(y.find("./LastName")) or butun_metin(y.find("./CollectiveName"))
            if yazar:
                break
        turler = [butun_metin(t) for t in art.findall("./PublicationTypeList/PublicationType")]
        geri_cekildi = any(t in ("Retracted Publication", "Retraction of Publication") for t in turler)
        turler = [t for t in turler if not t.startswith(GURULTU_TUR)]
        makaleler.append({
            "pmid": pmid_el.text if pmid_el is not None else "?",
            "baslik": baslik, "ozet": ozet, "yil": _yil(art), "dergi": dergi, "yazar": yazar,
            "yazar_sayisi": len(yazarlar), "tur": turler[:2], "geri_cekildi": geri_cekildi,
            "dil": butun_metin(art.find("./Language")),
        })
    return makaleler


def kunye(m):
    """Kaynak satırı için kısa künye: 'Smith ve ark., 2024, Nature Genet [Review]'."""
    parcalar = []
    if m.get("yazar"):
        parcalar.append(f"{m['yazar']} ve ark." if m.get("yazar_sayisi", 2) > 1 else m["yazar"])
    if m.get("yil"):
        parcalar.append(m["yil"])
    if m.get("dergi"):
        parcalar.append(m["dergi"])
    metin = ", ".join(parcalar)
    if m.get("tur"):
        metin += f" [{'; '.join(m['tur'])}]"
    if m.get("geri_cekildi"):
        metin += " [GERİ ÇEKİLDİ]"
    return metin


def main():
    varyant = input("Bir arama terimi girin (örn. BRAF V600E): ").strip() or "BRAF V600E"
    s = makale_ara_ayrintili(varyant, adet=5)
    print(f"\nSorgu: {varyant}\nPubMed çevirisi: {s['ceviri']}\nToplam: {s['toplam']} | PMID: {s['pmidler']}")
    if s["dusen"]:
        print(f"UYARI: PubMed şu ifadeleri bulamayıp sorgudan attı: {s['dusen']}")
    for i, m in enumerate(makale_detaylari_al(s["pmidler"]), start=1):
        print("=" * 70)
        print(f"[{i}] PMID {m['pmid']} | {kunye(m)} | dil: {m['dil']}")
        print(f"Baslik: {m['baslik']}")
        print(f"Ozet: {m['ozet'][:300]}{'...' if len(m['ozet']) > 300 else ''}")
    print("=" * 70)


if __name__ == "__main__":
    main()
