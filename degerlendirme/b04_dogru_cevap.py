"""
BENCHMARK 4 — DOĞRU CEVAP LİSTESİ (ground truth) — adım 8 (v2, 26 Eylül denetimi sonrası).

Soru: "Bu varyanttan bahseden makaleler hangileri?" için bağımsız bir liste.
Kaynak: NCBI LitVar2 (varyant -> PMID listesi; tmVar anotasyonu, tam metin/PMC dahil).
        LitVar aynı varyantı rsID'li ve rsID'siz AYRI kayıtlarda tutabilir ('HBB E26K' = #3043#p.E26K ∪ rs33950507 [E27K, VEP numaralaması]);
        bu yüzden girdiyle UYUŞAN TÜM kayıtların PMID'leri birleştirilir (v1 gen eşleşen İLK adayı alıyordu: 'MTHFR A1298C' -> C677T listesi).
Not: LitVar/tmVar, literatürdeki eski adı ('c.677C>T', '6174delT') bazen başka bir rsID'ye normalize eder (rs1217691063, rs786204278);
o kayıtların makaleleri yine bizim varyantı o adla anan makalelerdir, bu yüzden LİTERAL ad eşleşmesi rsID'den bağımsız kabul edilir.
Uyuşma kuralı (gen eşleşmesi zorunlu; en az biri):
  - girdi rsID'si == adayın rsID'si (c06.ESKI_ADLAR tablosundan gelen rsID dahil: 'MTHFR A1298C' -> rs1801131)
  - adayın adı/HGVS'i girdinin yazımlarından biri (E6V, Glu6Val, E7V, c.79G>A, 35delG, 5382insC ...)
  - nükleotid tarzı eski ad <-> HGVS: 'A1298C' <-> 'c.1298A>C', 'G20210A' <-> 'g.20210G>A'
  - rsID'li aday: VEP'in o rsID için verdiği protein/cDNA yazımı girdiyle kesişiyor (rs33950507 -> p.Glu27Lys -> E27K; EZH2 Y641N -> Y646N)
PubTator3 varlık kimliği yalnızca META VERİ (per-makale doğrulama b05'te export anotasyonuyla yapılır); insan türü ve LitVar kimliği eşleşmesi aranır.
C katmanı rsID'leri için VEP'ten GRCh38/GRCh37 koordinat biçimi türetilir; hedef alel HARF değil PROTEİN DEĞİŞİMİ ile seçilir
(rs6025: GRCh37 referansı Leiden alelini taşır -> o sürümde satır üretilmez, uyarı yazılır).

Ek kurallar (4 Ekim):
  - Doğru = makale bu gendeki bu değişimi anıyor (insanda YA DA model organizmadaki karşılığında: 'Gnas R201C' taşıyan fare çalışması da
    doğrudur; LitVar'ın insan rsID listeleri bu makaleleri zaten içerir, hakem kuralı da aynıdır). rsID'siz '#<GeneID>#' kayıtlarında tür
    NCBI Gene'den okunur ve insan dışıysa satırın uyarilar alanına NOT düşülür, kayıt ELENMEZ (fare Hbb #15127; 'hindi' GJB2 #100551196
    aslında tmVar'ın 'Turkey' kelimesini tür sanmasıdır: makaleler Türk hasta çalışmalarıdır).
  - Aynı varyantın GT'si girdi biçiminden bağımsız olsun: rsID/koordinat girdisinde c06.ESKI_ADLAR'daki eski adlar da aranır
    (rs6025 -> 'F5 R506Q' kayıtları da birleşir; böylece 'rs6025' ile 'F5 R506Q' aynı listeyi alır).
  - VEP geçici hatası boş küme olarak ÖNBELLEĞE ALINMAZ; denenemeyen 'vep' eşleşmesi satırın uyarilar alanına yazılır.

Çıktı: degerlendirme/sonuclar/dogru_cevap.jsonl  (tarih damgalı; git'e girer). Yeni liste önce geçici dosyaya yazılır; eskisi
sonuclar/yedek/dogru_cevap_<tarih_saat>.jsonl olarak saklanır (koşu yarıda kalırsa eski liste yerinde kalır, aynı gün ikinci koşu ezmez).
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import requests

import c02_varyant_anlamlandir as c02
from c06_clinvar import ESKI_ADLAR
from c07_sorgu_kur import varyant_kaydi
from test_seti import KATMANLAR, KOORDINAT_TURET

LITVAR = "https://www.ncbi.nlm.nih.gov/research/litvar2-api/"
PUBTATOR = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/"
CIKTI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sonuclar", "dogru_cevap.jsonl")
ARALIK = 0.4
NUK = re.compile(r"^([acgt])(\d+)([acgt])$")                 # c677t, a1298c, g20210a (nükleotid tarzı eski ad; küçük harf)
HGVS_NUK = re.compile(r"^[cg]\.(\d+)([acgt])>([acgt])$")     # LitVar hgvs: c.677C>T / g.20210G>A (küçük harfe çevrilmiş)
ONEK = re.compile(r"^(p\.|c\.|g\.)")
GEN_ESDEGER = {"U2AF1": {"U2AF1L5"}}                         # aynı lokusun kopyası; LitVar bazı kayıtları paralog adıyla tutar
_VEP_ONBELLEK = {}
_VEP_HATALARI = []                                           # bu girdide VEP'e ulaşılamayan rsID'ler (satır uyarısına yazılır)
_TUR_ONBELLEK = {}                                           # GeneID -> (insan_mi, tür adı)
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def _get(url, params=None, timeout=60):
    time.sleep(ARALIK)
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _temiz(ad):
    return ONEK.sub("", (ad or "").strip().lower())


def _bicimler(kayit):
    """Girdinin karşılaştırılabilir yazımları (küçük harf, p./c./g. öneksiz): e6v, glu6val, e7v, c.79g>a, 35delg ..."""
    adaylar = [kayit.get("protein_kisa"), kayit.get("protein_3harf"), *kayit.get("protein_diger", []),
               kayit.get("cdna"), *kayit.get("ek_terimler", [])]
    b = {_temiz(a) for a in adaylar if a}
    b |= {x[:-1] + "*" for x in b if x.endswith("x")}      # R175X -> R175* (c07 '*'ı PubMed jokeri diye X yazar)
    b |= {x[:-3] + "*" for x in b if x.endswith("ter")}
    return b


def _nuk_esdeger(bicimler, ad):
    """'a1298c' <-> 'c.1298a>c' / 'g.20210g>a': nükleotid tarzı eski ad ile HGVS aynı değişim mi?"""
    m_ad = HGVS_NUK.match((ad or "").lower())
    if not m_ad:
        return False
    hedef = (m_ad.group(1), m_ad.group(2), m_ad.group(3))
    for b in bicimler:
        m = NUK.match(b)
        if m and (m.group(2), m.group(1), m.group(3)) == hedef:
            return True
    return False


def _vep_bicimleri(rsid):
    """rsID'nin VEP kartındaki protein/cDNA yazımları (önbellekli): {'e27k', 'glu27lys', 'c.79g>a', ...}
    VEP geçici hatasında bir kez daha dener; yine olmazsa boş küme döner ama ÖNBELLEĞE ALMAZ ve _VEP_HATALARI'na yazar."""
    if rsid in _VEP_ONBELLEK:
        return _VEP_ONBELLEK[rsid]
    sorun = None
    for deneme in range(2):
        try:
            kart = c02.anlamlandir_rsid(rsid)
        except Exception as e:
            sorun = type(e).__name__
            time.sleep(3)
            continue
        if "hata" in kart and str(kart["hata"]).startswith("VEP hatası"):
            sorun = kart["hata"][:60]
            time.sleep(3)
            continue
        b = set()
        if "hata" not in kart:                                   # 'rsID VEP'te bulunamadı' kalıcıdır: boş küme önbelleğe girer
            for v in (kart.get("protein_kisa"), kart.get("protein_3harf"), *kart.get("protein_diger", [])):
                if v:
                    b.add(_temiz(v))
            if kart.get("hgvsc") and ":c." in kart["hgvsc"]:
                b.add(_temiz("c." + kart["hgvsc"].split(":c.", 1)[1]))
        _VEP_ONBELLEK[rsid] = b
        return b
    _VEP_HATALARI.append(f"{rsid}: VEP'e ulaşılamadı ({sorun}); bu aday için 'vep' eşleşmesi denenemedi")
    return set()


def _insan_geni_mi(gene_id):
    """NCBI Gene: GeneID insan mı? (insan_mi, tür_adı). Doğrulanamazsa (True, None): yanlışlıkla kayıt atmayalım."""
    if gene_id in _TUR_ONBELLEK:
        return _TUR_ONBELLEK[gene_id]
    try:
        veri = _get(ESUMMARY, {"db": "gene", "id": gene_id, "retmode": "json"})
        org = ((veri.get("result") or {}).get(str(gene_id)) or {}).get("organism") or {}
        if not org:
            return True, None
        _TUR_ONBELLEK[gene_id] = (str(org.get("taxid")) == "9606", org.get("scientificname"))
    except Exception:
        return True, None
    return _TUR_ONBELLEK[gene_id]


def _eski_ad_rsid(kayit):
    """c06.ESKI_ADLAR: klinikte kullanılan eski ad -> rsID ('MTHFR A1298C' -> rs1801131, 'BRCA1 5382insC' -> rs80357906)."""
    gen = kayit.get("gen") or ""
    adaylar = [kayit.get("girdi", ""), f"{gen} {kayit.get('protein_kisa') or ''}", f"{gen} {(kayit.get('ek_terimler') or [''])[0]}"]
    for a in adaylar:
        a = a.strip().upper()
        if a in ESKI_ADLAR:
            return ESKI_ADLAR[a]
    return None


def litvar_bul(kayit):
    """Girdiyle uyuşan TÜM LitVar2 kayıtları ve notlar: ([{'id','rsid','ad','pmid_sayisi','neden'}, ...], [not, ...])
    (rsID'li ve PMID'i çok olan önce). İnsan dışı kayıtlar elenir ve notlara yazılır."""
    gen = (kayit.get("gen") or "").upper()
    gen_kumesi = {gen} | GEN_ESDEGER.get(gen, set())
    rsidler = {r.lower() for r in kayit.get("rsid") or []}
    eski = _eski_ad_rsid(kayit)
    if eski:
        rsidler.add(eski.lower())
    bicimler = _bicimler(kayit)
    notlar = []
    # Eski adlar (ters yön): rsID'si bizim varyant olan klinik adlar da aranır ve yazımları eşleşmeye eklenir
    eski_adlar = [ad for ad, rs in ESKI_ADLAR.items() if rs.lower() in rsidler and ad.split()[0] == gen and " " in ad]
    bicimler |= {_temiz(ad.split(None, 1)[1]) for ad in eski_adlar}
    sorgular = sorted(rsidler) + eski_adlar
    if gen and kayit.get("protein_kisa"):
        sorgular.append(f"{gen} {kayit['protein_kisa']}")
        sorgular += [f"{gen} {d}" for d in kayit.get("protein_diger", []) if len(d) >= 3]
    if gen and kayit.get("cdna"):
        sorgular.append(f"{gen} {kayit['cdna']}")
    if gen and kayit.get("ek_terimler"):
        sorgular.append(f"{gen} {kayit['ek_terimler'][0]}")
    bulunan = {}
    for q in dict.fromkeys(sorgular):
        try:
            adaylar = _get(LITVAR + "variant/autocomplete/", {"query": q})
        except Exception:
            continue
        for a in adaylar or []:
            kimlik = a.get("_id")
            if not kimlik or kimlik in bulunan:
                continue
            genler = {g.upper() for g in (a.get("gene") or [])}
            if gen and not (gen_kumesi & genler):
                continue                                             # gen eşleşmesi zorunlu
            m_gid = re.match(r"^litvar@#(\d+)#", kimlik)
            if m_gid:
                insan, tur = _insan_geni_mi(m_gid.group(1))
                if not insan:                                         # elenmez: model organizma çalışması da varyantı anar
                    notlar.append(f"{kimlik}: tür etiketi insan dışı ({tur}); gen adı ve değişim eşleştiği için tutuldu")
            a_rs = (a.get("rsid") or "").lower() or None
            ad, isim = a.get("hgvs") or "", a.get("name") or ""
            if a_rs and a_rs in rsidler:
                neden = "rsid"
            elif _temiz(ad) in bicimler or _temiz(isim) in bicimler:
                neden = "ad"
            elif _nuk_esdeger(bicimler, ad) or _nuk_esdeger(bicimler, isim):
                neden = "nukleotid"
            elif a_rs and (_vep_bicimleri(a_rs) & bicimler):
                neden = "vep"
            else:
                continue
            bulunan[kimlik] = {"id": kimlik, "rsid": a_rs, "ad": isim or ad, "pmid_sayisi": int(a.get("pmids_count") or 0), "neden": neden}
    kayitlar = [k for k in bulunan.values() if k]
    return sorted(kayitlar, key=lambda k: (k["rsid"] is None, -k["pmid_sayisi"])), notlar


def litvar_pmidler(kimlik):
    d = _get(LITVAR + f"variant/get/{kimlik.replace('@', '%40').replace('#', '%23')}/publications", timeout=120)
    return [str(p) for p in d.get("pmids", [])]


def pubtator_bul(kayit, litvar_kayitlar):
    """PubTator3 varlık kimliği (yalnızca meta veri). Sorgu 'GEN değişim' (gen adsız sorgu başka genlerin aynı adlı varyantlarını
    getirir); yalnızca İNSAN türü; LitVar kimliği aynı olan aday tercih edilir. (kimlik, makale_sayisi) | (None, 0)"""
    gen = (kayit.get("gen") or "").upper()
    litvar_idler = {k["id"].replace("litvar@", "") for k in litvar_kayitlar}
    rs_kayit_idler = {k["id"].replace("litvar@", "") for k in litvar_kayitlar if k.get("rsid")}
    rsidler = {r.lower() for r in kayit.get("rsid") or []} | {k["rsid"] for k in litvar_kayitlar if k.get("rsid")}
    sorgular = []
    if gen and kayit.get("protein_kisa"):
        sorgular.append(f"{gen} {kayit['protein_kisa']}")
    sorgular += sorted(rsidler)[:2]
    if gen and kayit.get("ek_terimler"):
        sorgular.append(f"{gen} {kayit['ek_terimler'][0]}")
    eslesen, yedek = [], None                     # LitVar kimliği eşleşenlerin HEPSİ toplanır; rsID kaydına bağlı olan tercih edilir
    for q in sorgular:                            # (F2 G20210A: 4 makalelik 'p.G20210A' değil, rs1799963 varlığı)
        try:
            adaylar = _get(PUBTATOR + "entity/autocomplete/", {"query": q, "concept": "variant", "limit": 10})
        except Exception:
            continue
        for a in adaylar or []:
            aciklama = (a.get("description") or "")
            if "(human)" not in aciklama:
                continue                                              # GJB2 (turkey), LOC... (common tobacco) elenir
            db_id = str(a.get("db_id") or "")
            if db_id in litvar_idler and a["_id"] not in [e[2] for e in eslesen]:
                eslesen.append((db_id in rs_kayit_idler, -len(eslesen), a["_id"]))
            elif gen and aciklama.upper().startswith(gen + " ") and db_id.split("#")[0].lower() in rsidler:
                yedek = yedek or a["_id"]
    secilen = max(eslesen)[2] if eslesen else yedek
    if not secilen:
        return None, 0
    try:
        d = _get(PUBTATOR + "search/", {"text": secilen, "page": 1})
        return secilen, int(d.get("count") or 0)
    except Exception:
        return secilen, 0


def _aa_harfleri(p):
    """'D1228N' -> ('D', 'N'); 'P227=' -> ('P', '='): transkript numaralaması farklı olsa da aynı amino asit değişimi mi?"""
    m = re.match(r"^([A-Z])(\d+)([A-Z=*]|del|dup|fs.*)$", p or "")
    return (m.group(1), m.group(3)) if m else None


def koordinat_turet(rsid, hedef_protein):
    """Her sürümde alt alelleri tek tek VEP'e çözer; kanonik protein değişimi hedefle uyuşan aleli seçer.
    GRCh37'de kanonik transkript farklı numaralanabilir (MET D1228N = D1246N): GRCh38'de seçilen alelle AYNI ref>alt harfleri
    ve aynı amino asit değişimi (D->N) varsa kabul edilir. Hiçbir alel hedefi vermiyorsa o sürüm atlanır (rs6025 GRCh37: referans T,
    Leiden alelinin kendisi). Döndürür: ({surum: (koordinat, alt)}, uyarılar)."""
    sonuc, uyarilar = {}, []
    secim38 = None
    for surum in ("GRCh38", "GRCh37"):
        try:
            veri = c02._ensembl_get(f"{c02.SUNUCU[surum]}/vep/human/id/{rsid}", {})
        except c02.VepHata as e:
            uyarilar.append(f"{rsid} {surum}: VEP hatası ({str(e)[:80]})")
            continue
        if not veri:
            continue
        v = veri[0]
        aleller = (v.get("allele_string") or "").split("/")
        if len(aleller) < 2:
            continue
        ref, chrom, pos = aleller[0], v["seq_region_name"], v["start"]
        secilen = None
        for alt in aleller[1:]:
            koord = f"chr{chrom}:{pos}:{ref}>{alt}"
            girdi = koord if surum == "GRCh38" else f"GRCh37:{koord}"
            try:
                kart = c02.anlamlandir_herhangi(girdi) or {}
            except Exception as e:
                uyarilar.append(f"{girdi}: çözülemedi ({type(e).__name__})")
                continue
            if not kart or "hata" in kart:
                continue
            bicimler = {kart.get("protein_kisa"), *kart.get("protein_diger", [])}
            if hedef_protein in bicimler:
                secilen = (koord, alt)
                break
            if surum == "GRCh37" and secim38 == (ref, alt) and _aa_harfleri(kart.get("protein_kisa")) == _aa_harfleri(hedef_protein):
                uyarilar.append(f"{rsid} GRCh37: kanonik transkript numaralaması farklı ({kart.get('protein_kisa')} = {hedef_protein}); "
                                f"alel GRCh38 ile aynı ({ref}>{alt}), kabul edildi")
                secilen = (koord, alt)
                break
        if secilen:
            sonuc[surum] = secilen
            if surum == "GRCh38":
                secim38 = (ref, secilen[1])
        else:
            uyarilar.append(f"{rsid} {surum}: hiçbir alt alel {hedef_protein} vermiyor (allele_string {v.get('allele_string')}; "
                            f"referans hedef aleli taşıyor olabilir) -> satır üretilmedi")
    return sonuc, uyarilar


def main():
    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    bugun = date.today().isoformat()
    satirlar, bos = [], []
    for katman, liste in KATMANLAR.items():
        for girdi in liste:
            kayit = varyant_kaydi(girdi)
            uyarilar = list(kayit.get("uyarilar") or [])
            kayitlar, notlar = litvar_bul(kayit)
            uyarilar += notlar + _VEP_HATALARI
            _VEP_HATALARI.clear()
            pmidler = []
            for k in kayitlar:
                try:
                    k["pmid_sayisi_gercek"] = 0
                    yeni = litvar_pmidler(k["id"])
                    k["pmid_sayisi_gercek"] = len(yeni)
                    pmidler += [p for p in yeni if p not in set(pmidler)]
                except Exception as e:
                    uyarilar.append(f"LitVar {k['id']}: PMID listesi alınamadı ({type(e).__name__})")
            pt_id, pt_sayi = pubtator_bul(kayit, kayitlar)
            satir = {"girdi": girdi, "katman": katman, "tarih": bugun,
                     "gen": kayit.get("gen"), "rsid": kayit.get("rsid"), "protein_kisa": kayit.get("protein_kisa"),
                     "protein_diger": kayit.get("protein_diger"), "cdna": kayit.get("cdna"), "ek_terimler": kayit.get("ek_terimler"),
                     "litvar_id": kayitlar[0]["id"] if kayitlar else None, "litvar_kayitlar": kayitlar,
                     "litvar_sayi": len(pmidler), "litvar_pmidler": pmidler,
                     "pubtator_id": pt_id, "pubtator_sayi": pt_sayi, "uyarilar": uyarilar}
            kimlikler = " + ".join(f"{k['id'].replace('litvar@', '')}[{k['neden']},{k['pmid_sayisi_gercek']}]" for k in kayitlar) or "-"
            print(f"{katman:18} {girdi:20} pmid={len(pmidler):5} litvar={kimlikler} pubtator={pt_id or '-'} ({pt_sayi})")
            for u in uyarilar:
                print(f"    UYARI: {u}")
            if not pmidler and not katman.startswith("D_"):
                bos.append(girdi)
            satirlar.append(satir)
            # C katmanı: koordinat biçimleri türet (aynı doğru cevap listesini paylaşır; alel hedef proteinle seçilir)
            if girdi in KOORDINAT_TURET:
                hedef = KOORDINAT_TURET[girdi]
                if kayit.get("protein_kisa") and kayit["protein_kisa"] != hedef and hedef not in (kayit.get("protein_diger") or []):
                    u = f"{girdi} kartı {kayit['protein_kisa']} diyor, test seti hedefi {hedef}; hedef esas alındı"
                    uyarilar.append(u)
                    print(f"    UYARI: {u}")
                koordlar, k_uyari = koordinat_turet(girdi, hedef)
                for u in k_uyari:
                    print(f"    UYARI: {u}")
                for surum, (koord, alt) in koordlar.items():
                    g2 = koord if surum == "GRCh38" else f"GRCh37:{koord}"
                    print(f"{'C_koordinat':18} {g2:34} (rsID {girdi} ile aynı liste; {surum} alt={alt} -> {hedef})")
                    satirlar.append(dict(satir, girdi=g2, katman="C_koordinat", kaynak_rsid=girdi, surum=surum, alel=alt,
                                         hedef_protein=hedef, uyarilar=uyarilar + k_uyari))
    gecici = CIKTI + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        for s in satirlar:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    if os.path.exists(CIKTI):                                    # eski liste ancak yenisi TAMAMLANINCA yedeğe alınır
        yedek_dizin = os.path.join(os.path.dirname(CIKTI), "yedek")
        os.makedirs(yedek_dizin, exist_ok=True)
        damga = datetime.fromtimestamp(os.path.getmtime(CIKTI)).strftime("%Y-%m-%d_%H%M%S")
        yedek = os.path.join(yedek_dizin, f"dogru_cevap_{damga}.jsonl")
        os.replace(CIKTI, yedek)
        print(f"(eski liste yedeklendi: yedek/{os.path.basename(yedek)})")
    os.replace(gecici, CIKTI)
    print(f"\n{len(satirlar)} satır -> {CIKTI}")
    if bos:
        print(f"Doğru cevap listesi BOŞ kalan (A/B/C) girdiler: {', '.join(bos)}")


if __name__ == "__main__":
    main()
