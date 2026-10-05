"""
FINE-TUNE v4 — Adım 1: YENİ VARYANTLARIN KAYNAKLARI (LLM YOK).

Eğitim verisini ~500 örneğe çıkarmak için yeni ve ÇEŞİTLİ girdiler: farklı alanlar (nöroloji, kardiyoloji, metabolizma, göz, işitme,
ilaç yanıtı, kanser), farklı yazım biçimleri ("GEN DEĞİŞİM", eski klinik ad, rsID, genom koordinatı GRCh38/GRCh37) ve
literatürü olmayan gen düzeyi girdiler (intron koordinatı).

Kaynaklar UYGULAMANIN KENDİ HATTIYLA çekilir (c07.kaynaklari_getir): modele giden system mesajı ve ilk soru, canlı sistemle
(c04.sistem_metni, c04.ilk_soru, c07.model_etiketi) birebir aynıdır -> eğitim/kullanım eşitliği.

Kural: hiçbir gen test setinde (degerlendirme/test_seti.py, 56 girdi) ya da v3 eğitim verisinde yoktur (çeşitlilik + sızıntı yok).
Test setinin donmuş arama kaydıyla ortak PMID varsa raporlanır.

Çıktı: fine_tune/kaynaklar_v4.jsonl  (eski fine_tune/kaynaklar.jsonl'a DOKUNULMAZ)
Kullanım: python fine_tune/kaynak_topla_v4.py
"""

import json
import os
import sys
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "degerlendirme"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import c02_varyant_anlamlandir as c02
import c04_varchat_ollama as app
from c07_sorgu_kur import kaynaklari_getir, model_etiketi
from test_seti import EGITIM_GENLERI, KATMANLAR

CIKTI = os.path.join(KOK, "fine_tune", "kaynaklar_v4.jsonl")
TEST_SNAPSHOT = os.path.join(KOK, "degerlendirme", "sonuclar", "arama_2026-10-05.jsonl")

# (girdi, alan, biçim) — biçim: gen_degisim | eski_ad | ifade | rsid
GIRDILER = [
    # Nöroloji / nörodejenerasyon
    ("LRRK2 G2019S", "nöroloji", "gen_degisim"), ("GBA1 N370S", "nöroloji", "eski_ad"), ("SNCA A53T", "nöroloji", "gen_degisim"),
    ("APP V717I", "nöroloji", "gen_degisim"), ("PSEN1 E280A", "nöroloji", "gen_degisim"), ("SOD1 A4V", "nöroloji", "eski_ad"),
    ("TREM2 R47H", "nöroloji", "gen_degisim"),
    # Kardiyoloji / lipid
    ("MYH7 R403Q", "kardiyoloji", "gen_degisim"), ("SCN5A E1784K", "kardiyoloji", "gen_degisim"), ("PCSK9 D374Y", "kardiyoloji", "gen_degisim"),
    ("APOB R3527Q", "kardiyoloji", "gen_degisim"), ("TTR V30M", "kardiyoloji", "eski_ad"),
    # Romatoloji / immünoloji / gastro
    ("MEFV M694V", "romatoloji", "gen_degisim"), ("NOD2 L1007fs", "gastroenteroloji", "gen_degisim"), ("PRSS1 R122H", "gastroenteroloji", "gen_degisim"),
    ("SPINK1 N34S", "gastroenteroloji", "gen_degisim"), ("CCR5 delta32", "immünoloji", "ifade"),
    # Metabolizma / endokrin / böbrek
    ("GALT Q188R", "metabolizma", "gen_degisim"), ("ACADM K329E", "metabolizma", "gen_degisim"), ("HNF1A P291fs", "endokrinoloji", "gen_degisim"),
    ("NPHS2 R229Q", "nefroloji", "gen_degisim"),
    # Göz / işitme / gelişim
    ("RHO P23H", "göz", "gen_degisim"), ("ABCA4 G1961E", "göz", "gen_degisim"), ("SLC26A4 H723R", "işitme", "gen_degisim"),
    ("OTOF Q829X", "işitme", "gen_degisim"), ("FGFR2 S252W", "gelişim", "gen_degisim"), ("RYR1 R614C", "kas / anestezi", "gen_degisim"),
    # Kanser (somatik ve kalıtsal)
    ("FOXL2 C134W", "kanser", "gen_degisim"), ("PTPN11 E76K", "kanser", "gen_degisim"), ("XPO1 E571K", "kanser", "gen_degisim"),
    ("BTK C481S", "kanser", "gen_degisim"), ("BCL2 G101V", "kanser", "gen_degisim"), ("STAT3 Y640F", "kanser", "gen_degisim"),
    ("CALR del52", "kanser", "ifade"), ("NPM1 W288fs", "kanser", "gen_degisim"), ("CHEK2 1100delC", "kanser", "ifade"),
    ("STK11 Q37*", "kanser", "gen_degisim"), ("APC R1450*", "kanser", "gen_degisim"),
    # İlaç yanıtı / yaygın özellikler (rsID girdisi)
    ("rs671", "farmakogenomik", "rsid"), ("rs4149056", "farmakogenomik", "rsid"), ("rs9923231", "farmakogenomik", "rsid"),
    ("rs3918290", "farmakogenomik", "rsid"), ("rs116855232", "farmakogenomik", "rsid"), ("rs738409", "metabolizma", "rsid"),
    ("rs7903146", "endokrinoloji", "rsid"), ("rs4988235", "beslenme", "rsid"), ("rs1815739", "spor / kas", "rsid"),
    ("rs73885319", "nefroloji", "rsid"), ("rs10490924", "göz", "rsid"), ("rs1061170", "göz", "rsid"),
]
# rsID'den türetilen KOORDİNAT girdileri (alel ClinVar'da önemi olan aleldir: c02.klinik_alel_sec); 3'ü GRCh37 biçiminde
KOORDINAT_RSID = [("rs1799990", "nöroloji", "GRCh38"), ("rs3892097", "farmakogenomik", "GRCh38"), ("rs776746", "farmakogenomik", "GRCh38"),
                  ("rs4148323", "farmakogenomik", "GRCh38"), ("rs5219", "endokrinoloji", "GRCh38"), ("rs601338", "immünoloji", "GRCh38"),
                  ("rs12979860", "enfeksiyon", "GRCh38"), ("rs1805007", "dermatoloji", "GRCh37"), ("rs58542926", "metabolizma", "GRCh37"),
                  ("rs17822931", "dermatoloji", "GRCh37")]
# Gen düzeyi: bilinen hastalık genlerinin İNTRONUNDA (kanonik transkript, 2. ve 3. ekzon arası) literatürsüz bir nokta
GEN_DUZEYI = [("SCN1A", "nöroloji"), ("NF1", "nöroloji"), ("DMD", "kas"), ("PKD1", "nefroloji"), ("RYR2", "kardiyoloji"),
              ("CACNA1A", "nöroloji"), ("LMNA", "kardiyoloji"), ("FBN1", "bağ dokusu"), ("COL1A1", "bağ dokusu"), ("TSC2", "nöroloji"),
              ("NF2", "nöroloji"), ("MSH2", "kanser"), ("ATM", "kanser"), ("SCN9A", "nöroloji"), ("KCNQ2", "nöroloji")]
GECIS = {"A": "G", "G": "A", "C": "T", "T": "C"}


def test_genleri():
    import re
    genler = {g.split()[0].upper() for liste in KATMANLAR.values() for g in liste if not g.lower().startswith(("rs", "chr"))}
    if os.path.exists(TEST_SNAPSHOT):
        for l in open(TEST_SNAPSHOT, encoding="utf-8"):
            g = (json.loads(l).get("kayit") or {}).get("gen")
            if g:
                genler.add(g.upper())
    return genler


def tekrar_dene(is_, *argumanlar, deneme=4):
    """Ensembl/VEP geçici hatalarında (500, zaman aşımı) bekleyip yeniden dener; olmazsa None."""
    for i in range(deneme):
        try:
            return is_(*argumanlar)
        except Exception as e:
            print(f"  {argumanlar[0]}: {type(e).__name__}: {str(e)[:80]} (deneme {i + 1}/{deneme})")
            time.sleep(5 * (i + 1))
    return None


def rsid_koordinati(rs, surum):
    """rsID -> 'chrN:pos:REF>ALT' (yalnız tek bazlık değişim); geri çözümde aynı protein/cDNA çıkmazsa None."""
    kart = c02.anlamlandir_rsid(rs, surum=surum)
    if "hata" in kart:
        if "500" in str(kart["hata"]) or "ulaşılamadı" in str(kart["hata"]):
            raise RuntimeError(kart["hata"])           # geçici sunucu hatası: tekrar_dene yeniden dener
        return None
    ref = (kart.get("alel") or "").split("/")[0]
    alt = kart.get("secilen_alel") or (kart.get("alel") or "/").split("/")[1]
    if len(ref) != 1 or len(alt) != 1:
        return None
    koord = f"chr{kart['kromozom']}:{kart['pozisyon']}:{ref}>{alt}"
    girdi = koord if surum == "GRCh38" else f"GRCh37:{koord}"
    geri = c02.anlamlandir_herhangi(girdi) or {}
    if "500" in str(geri.get("hata", "")):
        raise RuntimeError(geri["hata"])
    if "hata" in geri or (geri.get("protein_kisa") or geri.get("hgvsc")) != (kart.get("protein_kisa") or kart.get("hgvsc")):
        print(f"  {rs} {surum}: geri çözüm uyuşmadı ({geri.get('protein_kisa') or geri.get('hata')} != {kart.get('protein_kisa')}); atlandı")
        return None
    return girdi


def intron_koordinati(gen):
    # Önce yalnız kanonik transkriptin kimliği, sonra o transkriptin ekzonları: genin bütün transkriptlerini birden istemek
    # (expand=1) büyük genlerde (SCN1A, DMD) Ensembl'den 500 döndürüyor.
    v = c02._ensembl_get(f"{c02.SUNUCU['GRCh38']}/lookup/symbol/homo_sapiens/{gen}", {})
    tid = (v.get("canonical_transcript") or "").split(".")[0]
    tr = c02._ensembl_get(f"{c02.SUNUCU['GRCh38']}/lookup/id/{tid}", {"expand": 1}) if tid else None
    if not tr or len(tr.get("Exon", [])) < 3:
        return None
    ex = sorted(tr["Exon"], key=lambda e: e["start"])
    pos = (ex[1]["end"] + ex[2]["start"]) // 2
    ref = c02._ensembl_get(f"{c02.SUNUCU['GRCh38']}/sequence/region/human/{v['seq_region_name']}:{pos}..{pos}:1", {}).get("seq", "").upper()
    if ref not in GECIS:
        return None
    return f"chr{v['seq_region_name']}:{pos}:{ref}>{GECIS[ref]}"


def kaydet(girdi, alan, bicim, test_pmid, f):
    s = kaynaklari_getir(girdi, adet=5)
    kayit = s["kayit"]
    if s["kademe"] in ("yok", "hata") or len(s["makaleler"]) < 3:
        print(f"  {girdi}: kademe {s['kademe']}, {len(s['makaleler'])} makale -> ATLANDI")
        return None
    etiket = model_etiketi(kayit, girdi)
    gen = kayit.get("gen") or "ilgili gen"
    app.SON_BAGLAM.clear()
    app.SON_BAGLAM.update(kademe=s["kademe"], gen=gen, varyant=girdi, etiket=etiket, n_kaynak=len(s["makaleler"]))
    satir = {"girdi": girdi, "alan": alan, "bicim": bicim, "kademe": s["kademe"], "gen": gen, "etiket": etiket,
             "sistem": app.sistem_metni(etiket, s["makaleler"], s["kademe"], gen), "ilk_soru": app.ilk_soru(etiket),
             "makaleler": [{k: m.get(k) for k in ("pmid", "alaka", "baslik", "ozet", "yil", "dergi")} for m in s["makaleler"]],
             "sorgular": s["sorgular"], "sayilar": s["sayilar"], "uyarilar": s["uyarilar"],
             "test_ile_ortak_pmid": sorted({m["pmid"] for m in s["makaleler"]} & test_pmid)}
    f.write(json.dumps(satir, ensure_ascii=False) + "\n")
    f.flush()
    print(f"  {girdi:38} {s['kademe']:7} {len(s['makaleler'])} makale | ad: {etiket}" +
          (f" | TEST İLE ORTAK PMID {satir['test_ile_ortak_pmid']}" if satir["test_ile_ortak_pmid"] else ""))
    return satir


def main():
    yasak = test_genleri() | EGITIM_GENLERI
    test_pmid = set()
    if os.path.exists(TEST_SNAPSHOT):
        for l in open(TEST_SNAPSHOT, encoding="utf-8"):
            test_pmid |= {m["pmid"] for m in json.loads(l)["makaleler"]}
    yapilan = set()
    if os.path.exists(CIKTI):
        yapilan = {json.loads(l)["girdi"] for l in open(CIKTI, encoding="utf-8") if l.strip()}
    plan = list(GIRDILER)
    print(f"{len(plan)} doğrudan girdi + {len(KOORDINAT_RSID)} koordinat + {len(GEN_DUZEYI)} gen düzeyi | daha önce toplanan {len(yapilan)}")
    print("koordinatlar türetiliyor...")
    for rs, alan, surum in KOORDINAT_RSID:
        g = tekrar_dene(rsid_koordinati, rs, surum)
        if g:
            plan.append((g, alan, "koordinat"))
    for gen, alan in GEN_DUZEYI:
        g = tekrar_dene(intron_koordinati, gen)
        if g:
            plan.append((g, alan, "gen_duzeyi"))
        time.sleep(0.2)
    with open(CIKTI, "a", encoding="utf-8") as f:
        for girdi, alan, bicim in plan:
            if girdi in yapilan:
                continue
            gen_adi = girdi.split()[0].upper() if bicim not in ("rsid", "koordinat", "gen_duzeyi") else None
            if gen_adi and gen_adi in yasak:
                print(f"  {girdi}: gen test setinde ya da eğitimde -> ATLANDI")
                continue
            try:
                satir = kaydet(girdi, alan, bicim, test_pmid, f)
            except Exception as e:
                print(f"  {girdi}: HATA {type(e).__name__}: {str(e)[:120]}")
                continue
            if satir and satir["gen"].upper() in yasak:
                print(f"    UYARI: {girdi} çözümlenen gen {satir['gen']} test setinde/eğitimde")
    satirlar = [json.loads(l) for l in open(CIKTI, encoding="utf-8") if l.strip()]
    from collections import Counter
    print(f"\n{len(satirlar)} girdi -> {CIKTI}")
    print("biçim:", dict(Counter(s["bicim"] for s in satirlar)), "| kademe:", dict(Counter(s["kademe"] for s in satirlar)))
    print("alan:", dict(Counter(s["alan"] for s in satirlar)))


if __name__ == "__main__":
    main()
