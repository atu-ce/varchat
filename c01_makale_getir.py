"""
VarChat benzeri projenin İLK adımı.

Amaç: Bir genetik varyant verince (örn. "BRAF V600E"), o varyantla ilgili
GERÇEK bilimsel makaleleri PubMed'den çekmek.

Bu, RAG'ın "Retrieval" (bulma) parçasının en küçük çalışan halidir.
Burada henüz yapay zeka / LLM YOK. Önce "verinin geldiğinden" emin oluyoruz;
özetleme adımını sonra ekleyeceğiz.
"""

import sys                           # terminal çıktı ayarı için
import time                          # NCBI'yi yormamak için aralara minik bekleme koyacağız
import xml.etree.ElementTree as ET   # PubMed'in XML cevabını okumak için (Python'la hazır gelir)

import requests                      # internetten veri çekmek için (HTTP istekleri)

# Windows terminali varsayılan olarak bazı özel bilimsel karakterleri (α, β, ∼, ≥ gibi)
# yazdıramaz ve program çöker. Çıktıyı UTF-8'e çevirerek tüm karakterleri yazabilir hale getiriyoruz.
sys.stdout.reconfigure(encoding="utf-8")

# --- NCBI E-utilities: PubMed'in resmi programlama kapısı (API) adresleri ---
# esearch: arama yapıp makale kimliklerini döndürür
# efetch : verdiğin kimliklerin detaylarını (başlık, özet) döndürür
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI, kötüye kullanım olursa iletişim kurabilmek için kim olduğumuzu bilmek ister.
# Zorunlu değil ama doğru/nazik kullanım için bunları gönderiyoruz.
EMAIL = "yazilimbirimi@karacasutekstil.com.tr"
TOOL = "varchat-tez-prototip"


def makale_ara(varyant, adet=5):
    """1. ADIM: Varyantı PubMed'de aratır. (PMID listesi, TOPLAM eşleşme sayısı) döndürür.

    Toplam sayı, "X makale bulundu, en alakalı N özetlendi" gösterimi için işe yarar
    (PubMed kaç makale eşleşti onu söyler; biz sadece ilk N'ini çekeriz).
    """
    parametreler = {
        "db": "pubmed",        # hangi veri tabanında arıyoruz: PubMed
        "term": varyant,       # ne arıyoruz
        "retmax": adet,        # en fazla kaç sonuç istiyoruz
        "retmode": "json",     # cevabı JSON formatında ver (okuması kolay)
        "sort": "relevance",   # alaka düzeyine göre sırala
        "email": EMAIL,
        "tool": TOOL,
    }
    cevap = requests.get(ESEARCH, params=parametreler, timeout=30)
    cevap.raise_for_status()                       # bir hata olduysa burada dur ve bildir
    sonuc = cevap.json()["esearchresult"]
    return sonuc["idlist"], int(sonuc.get("count", 0))   # (PMID listesi, toplam sayı)


def makale_idleri_bul(varyant, adet=5):
    """Geriye dönük uyumluluk için: yalnızca PMID listesini döndürür."""
    return makale_ara(varyant, adet)[0]


def butun_metin(element):
    """Bir XML etiketinin içindeki TÜM metni, iç içe etiketler (örn. <i> italik) dahil birleştirir.

    Neden gerekli: PubMed başlık/özetlerinde bazen iç etiketler olur. Düz '.text' sadece
    ilk iç etikete kadarki kısmı alır; itertext() ise gömülü tüm metni gezip toplar.
    """
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def makale_detaylari_al(pmid_listesi):
    """2. ADIM: Bulunan kimliklerle makalelerin başlık ve özetlerini (abstract) çek."""
    if not pmid_listesi:
        return []
    parametreler = {
        "db": "pubmed",
        "id": ",".join(pmid_listesi),   # kimlikleri virgülle ayırıp tek seferde sor
        "rettype": "abstract",
        "retmode": "xml",               # özet metni en düzenli XML formatında gelir
        "email": EMAIL,
        "tool": TOOL,
    }
    cevap = requests.get(EFETCH, params=parametreler, timeout=30)
    cevap.raise_for_status()

    kok = ET.fromstring(cevap.text)     # XML metnini, gezebileceğimiz bir ağaç yapısına çevir
    makaleler = []
    for makale in kok.findall(".//PubmedArticle"):
        baslik = butun_metin(makale.find(".//ArticleTitle")) or "(başlık yok)"

        # Bir makalenin özeti birden çok parçaya bölünmüş olabilir; hepsini birleştiriyoruz
        ozet_parcalari = [butun_metin(el) for el in makale.findall(".//AbstractText")]
        ozet = " ".join(p for p in ozet_parcalari if p) or "(özet yok)"

        pmid_el = makale.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else "?"

        makaleler.append({"pmid": pmid, "baslik": baslik, "ozet": ozet})
    return makaleler


def main():
    # Varyantı artık kullanıcıdan alıyoruz. input() ekrana soruyu yazar ve
    # klavyeden yazılanı bize verir. .strip() baştaki/sondaki boşlukları temizler.
    varyant = input("Bir genetik varyant girin (örn. BRAF V600E): ").strip()
    if not varyant:                       # kullanıcı hiçbir şey yazmadan Enter'a basarsa
        varyant = "BRAF V600E"
        print("(Boş bırakıldı, örnek olarak 'BRAF V600E' kullanılıyor.)")
    print(f"\nAranan varyant: {varyant}\n")

    pmidler = makale_idleri_bul(varyant, adet=5)
    print(f"Bulunan makale kimlikleri (PMID): {pmidler}\n")

    time.sleep(0.4)            # NCBI'nin "saniyede en fazla 3 istek" kuralına uymak için minik bekleme
    makaleler = makale_detaylari_al(pmidler)

    for i, m in enumerate(makaleler, start=1):
        print("=" * 70)
        print(f"[{i}] PMID {m['pmid']}")
        print(f"Baslik: {m['baslik']}")
        ozet = m["ozet"]
        kisa_ozet = ozet[:400] + ("..." if len(ozet) > 400 else "")
        print(f"Ozet: {kisa_ozet}")
        print(f"Link: https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
