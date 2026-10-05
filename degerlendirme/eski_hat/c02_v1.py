"""
Varyant anlamlandırma (annotation) — İLK adım.

Amaç: chr1:17001759:A>T gibi bir GENOMİK KOORDİNATI, aranabilir bilgilere çevirmek:
  - hangi gen?
  - bilinen kimliği (rsID)?
  - etkisi (consequence)?

Neden gerekli: Koordinatın kendisi hiçbir makalede metin olarak geçmez; ama gen adı
ve rsID literatürde geçer. Yani önce koordinatı "anlamlandırıp" aranabilir hale getiriyoruz.

Kaynak: Ensembl VEP (Variant Effect Predictor) REST API — ücretsiz, anahtar gerektirmez.
Varsayılan genom sürümü: GRCh38 (hg38).
"""

import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")

# GRCh38 (hg38) sunucusu. GRCh37 (hg19) için: https://grch37.rest.ensembl.org
VEP_TABAN = "https://rest.ensembl.org"


def varyanti_coz(varyant):
    """'chr1:17001759:A>T' metnini parçalarına ayırır -> (kromozom, pozisyon, ref, alt)."""
    v = varyant.strip().replace("chr", "", 1)   # 'chr' önekini kaldır
    kromozom, pozisyon, degisim = v.split(":")
    referans, alternatif = degisim.split(">")
    return kromozom, int(pozisyon), referans, alternatif


def anlamlandir(varyant):
    kromozom, pozisyon, referans, alternatif = varyanti_coz(varyant)

    # Şimdilik sadece tek harfli değişimleri (SNV) ele alıyoruz
    if len(referans) != 1 or len(alternatif) != 1:
        return {"hata": "Şimdilik sadece SNV (tek harf > tek harf) destekleniyor; "
                        "silme/ekleme (indel) sonraki adımda."}

    # VEP 'region' formatı: kromozom:baslangic-bitis/alternatif_alel
    bolge = f"{kromozom}:{pozisyon}-{pozisyon}/{alternatif}"
    url = f"{VEP_TABAN}/vep/human/region/{bolge}"
    cevap = requests.get(url, headers={"Content-Type": "application/json"}, timeout=30)
    cevap.raise_for_status()
    veri = cevap.json()[0]   # tek varyant sorduk, ilk (tek) sonucu al

    # Gen isimlerini topla
    genler = sorted({
        t.get("gene_symbol")
        for t in veri.get("transcript_consequences", [])
        if t.get("gene_symbol")
    })

    # rsID'leri topla (dbSNP kimliği)
    rsidler = sorted({
        c.get("id")
        for c in veri.get("colocated_variants", [])
        if str(c.get("id", "")).startswith("rs")
    })

    return {
        "genler": genler,
        "rsid": rsidler,
        "etki": veri.get("most_severe_consequence"),
    }


def anlamlandir_hgvs(hgvs):
    """VEP'in HGVS ucunu kullanır (örn. '1:g.17001759A>T'); gen/rsID döndürür.

    VarChat tarzı koordinatlar (GRCh38:1:g.17001759A>T) içindir. Baştaki
    'GRCh38:' / 'GRCh37:' gibi sürüm öneklerini temizler.
    """
    temiz = hgvs.strip()
    for onek in ("GRCh38:", "GRCh37:", "grch38:", "grch37:"):
        temiz = temiz.replace(onek, "")
    url = f"{VEP_TABAN}/vep/human/hgvs/{temiz}"
    cevap = requests.get(url, headers={"Content-Type": "application/json"}, timeout=30)
    cevap.raise_for_status()
    veri = cevap.json()[0]

    genler = sorted({
        t.get("gene_symbol")
        for t in veri.get("transcript_consequences", [])
        if t.get("gene_symbol")
    })
    rsidler = sorted({
        c.get("id")
        for c in veri.get("colocated_variants", [])
        if str(c.get("id", "")).startswith("rs")
    })
    return {"genler": genler, "rsid": rsidler, "etki": veri.get("most_severe_consequence")}


def main():
    varyant = "chr1:17001759:A>T"
    print(f"Varyant: {varyant}\n")
    sonuc = anlamlandir(varyant)
    for anahtar, deger in sonuc.items():
        print(f"{anahtar}: {deger}")


if __name__ == "__main__":
    main()
