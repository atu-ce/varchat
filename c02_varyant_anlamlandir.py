"""
Varyant anlamlandırma (annotation) — v2: "anotasyon kartı".

Amaç: chr7:140753336:A>T gibi bir GENOMİK KOORDİNATI aranabilir ve anlaşılır bilgiye çevirmek:
gen, rsID, etki, HGVS c./p. adları, V600E kısa adı, toplum sıklığı, zararlılık skoru, klinik önem.

Neden gerekli: Koordinatın kendisi hiçbir makalede geçmez; gen adı, rsID ve V600E gibi adlar geçer.
Yani önce koordinatı "anlamlandırıp" aranabilir hale getiriyoruz. Kart, sonraki adımlarda
(sorgu kurma, ClinVar, prompt) tek kaynak olarak kullanılır.

Kabul edilen girdiler:
  - VCF tarzı koordinat : chr7:140753336:A>T · 7:140753336 A>T · chr7-140753336-A-T · chrM:3243:A>G (M -> MT)
                          indel: chr1:62578974:CAA>C  (VEP HGVS yazımına çevrilir: 1:g.62578975_62578976del)
                          sürüm öneki: GRCh37:chr7:140453136:A>T  /  hg19 chr7:140453136:A>T
  - HGVS genomik        : GRCh38:7:g.140753336A>T · 7:g.140753336A>T · NC_000007.14:g.140753336A>T
  - HGVS transkript     : NM_004333.6:c.1799T>A · ENST00000646891.2:c.1799T>A · NP_004324.2:p.Val600Glu
    ("BRAF:p.V600E" gibi gen sembolü + protein yazımı HGVS sayılmaz; o yol gen doğrulama + sorgu kurucudan geçer.)

Doğrulama:
  - Referans harf DOĞRULANIR: tek harf değişimlerinde VEP'in HGVS ucu (uyuşmazlıkta 400), silme/eklemelerde
    Ensembl dizi servisiyle genomdaki harfler okunup karşılaştırılır (VEP silinen diziyi kontrol etmez).
    Eski "region" ucu referansı hiç kontrol etmiyordu; yanlış harf ya da yanlış sürüm sessizce yanlış gene çözülüyordu.
  - Sürüm öneki yoksa GRCh38 varsayılır; referans uyuşmazsa GRCh37 denenir ve uyarı yazılır.
  - Ağ/sunucu hataları istisna olarak sızmaz; {'hata': ...} döner (bir kez yeniden denenir).

Kaynak: Ensembl REST (ücretsiz, anahtar gerektirmez). GRCh38: rest.ensembl.org, GRCh37: grch37.rest.ensembl.org
"""

import re
import sys
import time

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):       # Jupyter/Colab gibi ortamlarda stdout'un reconfigure'u yoktur
    pass

SUNUCU = {"GRCh38": "https://rest.ensembl.org", "GRCh37": "https://grch37.rest.ensembl.org"}
# hgvs: c./p. adları · canonical/mane: kanonik transkript işareti · af_gnomad*: toplum sıklığı · CADD: zararlılık skoru
VEP_PARAM = {"hgvs": 1, "canonical": 1, "mane": 1, "af_gnomade": 1, "af_gnomadg": 1, "CADD": 1}
ZAMAN_ASIMI = 30

AMINO_3TO1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Glu": "E", "Gln": "Q", "Gly": "G", "His": "H",
    "Ile": "I", "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W",
    "Tyr": "Y", "Val": "V", "Ter": "*", "Sec": "U",
}
TUMLEYEN = str.maketrans("ACGT", "TGCA")
KOMSU_ETKI = {"upstream_gene_variant", "downstream_gene_variant"}

# VCF tarzı yazım: [chr]7[:| |-|_]140753336[:| |-|_]?A[>|/|-]T  (kromozom 1-22, X, Y, M/MT; alel yalnızca ACGT)
KOORDINAT = re.compile(
    r"^(?:chr)?(?P<chrom>2[0-2]|1[0-9]|[1-9]|X|Y|M|MT)[:\s_-]+(?P<pos>\d+)[:\s_-]*(?P<ref>[ACGT]+)[>/-](?P<alt>[ACGT]+)$",
    re.IGNORECASE,
)
# HGVS: yalnızca gerçek dizi kimlikleri (NC_/NM_/NP_/NR_/NG_, ENST/ENSP/ENSG) ya da kromozom + g.
HGVS = re.compile(
    r"^(?:(?:N[CMPRG]_\d+(?:\.\d+)?|ENS[TPG]\d+(?:\.\d+)?):[gcnmp]\.|(?:chr)?(?:2[0-2]|1[0-9]|[1-9]|X|Y|MT|M):g\.)",
    re.IGNORECASE,
)
SURUM_ONEKI = re.compile(r"^(?P<surum>GRCh38|GRCh37|hg38|hg19)[:\s]+(?P<geri>.+)$", re.IGNORECASE)
SURUM_ADI = {"grch38": "GRCh38", "hg38": "GRCh38", "grch37": "GRCh37", "hg19": "GRCh37"}
REF_UYUSMAZLIK = re.compile(r"\(([ACGTN-]{1,60})\) does not match reference allele given by HGVS notation.*?\(([ACGTN-]{1,60})\)")


class VepHata(Exception):
    """VEP'in reddettiği istek (referans uyuşmazlığı vb.) ya da sunucu/ağ hatası."""


def surum_ayir(metin):
    """'GRCh37:chr7:...' -> ('GRCh37', 'chr7:...'); önek yoksa (None, metin). Sondaki noktalama kırpılır."""
    temiz = metin.strip().rstrip(",;.")
    m = SURUM_ONEKI.match(temiz)
    if m:
        return SURUM_ADI[m.group("surum").lower()], m.group("geri").strip().rstrip(",;.")
    return None, temiz


def koordinati_coz(metin):
    """VCF tarzı yazımı (kromozom, pozisyon, ref, alt, sürüm) olarak çözer. Tanınmazsa None."""
    surum, geri = surum_ayir(metin)
    m = KOORDINAT.match(geri)
    if not m:
        return None
    chrom = m.group("chrom").upper()
    chrom = "MT" if chrom == "M" else chrom          # Ensembl mitokondri için 'MT' bekler
    return chrom, int(m.group("pos")), m.group("ref").upper(), m.group("alt").upper(), surum


def hgvs_genomik(chrom, pos, ref, alt):
    """VCF (ref, alt) çiftini HGVS g. yazımına çevirir: SNV, silme, ekleme, delins. ref == alt ise None.

    VCF 'CAA>C' der (ilk harf çapa, sonrası silindi); HGVS 'şu aralık silindi' der. Ortak baş/son harfler kırpılır.
    """
    if ref == alt:
        return None
    i = 0
    while i < min(len(ref), len(alt)) and ref[i] == alt[i]:
        i += 1
    r, a, p = ref[i:], alt[i:], pos + i
    j = 0
    while j < min(len(r), len(a)) and r[len(r) - 1 - j] == a[len(a) - 1 - j]:
        j += 1
    if j:
        r, a = r[: len(r) - j], a[: len(a) - j]
    if len(r) == 1 and len(a) == 1:
        return f"{chrom}:g.{p}{r}>{a}"
    if not a:                                        # silme
        return f"{chrom}:g.{p}del" if len(r) == 1 else f"{chrom}:g.{p}_{p + len(r) - 1}del"
    if not r:                                        # ekleme: p-1 ile p arasına
        return f"{chrom}:g.{p - 1}_{p}ins{a}"
    if len(r) == 1:                                  # delins
        return f"{chrom}:g.{p}delins{a}"
    return f"{chrom}:g.{p}_{p + len(r) - 1}delins{a}"


def _ensembl_get(url, params=None, ham=False):
    """Ensembl REST GET: 400 -> VepHata(mesaj); 429/5xx/ağ hatasında bir kez yeniden dener; yine olmazsa VepHata."""
    son = None
    for deneme in range(2):
        try:
            cevap = requests.get(url, headers={"Accept": "text/plain" if ham else "application/json"},
                                 params=params, timeout=ZAMAN_ASIMI)
        except requests.RequestException as e:
            son = f"ağ hatası ({type(e).__name__})"
            time.sleep(1.5)
            continue
        if cevap.status_code == 400:
            try:
                mesaj = cevap.json().get("error", "")
            except ValueError:
                mesaj = cevap.text
            raise VepHata(str(mesaj)[:300])
        if cevap.status_code in (429, 500, 502, 503, 504):
            son = f"Ensembl sunucusu {cevap.status_code}"
            time.sleep(float(cevap.headers.get("Retry-After", 2)) if cevap.status_code == 429 else 2)
            continue
        if not cevap.ok:
            raise VepHata(f"Ensembl HTTP {cevap.status_code}")
        if ham:
            return cevap.text
        try:
            return cevap.json()
        except ValueError:
            raise VepHata("Ensembl geçersiz cevap döndürdü (JSON değil)")
    raise VepHata(son or "Ensembl'e ulaşılamadı")


def vep_hgvs(hgvs, surum="GRCh38"):
    """VEP HGVS ucunu çağırır; referans uyuşmazlığında/sunucu hatasında VepHata fırlatır."""
    veri = _ensembl_get(f"{SUNUCU[surum]}/vep/human/hgvs/{hgvs}", VEP_PARAM)
    if not veri:
        raise VepHata("VEP boş sonuç döndürdü")
    return veri[0]


def referans_oku(chrom, pos, uzunluk, surum="GRCh38"):
    """Genomdaki harfleri okur (silme/eklemede referansı doğrulamak için; VEP silinen diziyi kontrol etmez)."""
    metin = _ensembl_get(f"{SUNUCU[surum]}/sequence/region/human/{chrom}:{pos}..{pos + uzunluk - 1}:1", ham=True)
    return metin.strip().upper()


def protein_kisa(hgvsp):
    """'ENSP00000493543.1:p.Val600Glu' -> ('Val600Glu', 'V600E'); 'p.Phe508TrpfsTer5' -> ('Phe508TrpfsTer5', 'F508Wfs*5')."""
    if not hgvsp or "p." not in hgvsp:
        return None, None
    p = hgvsp.split("p.", 1)[1].replace("(", "").replace(")", "")
    kisa = re.sub(r"[A-Z][a-z]{2}", lambda m: AMINO_3TO1.get(m.group(0), m.group(0)), p)
    return p, kisa


# Çok alelli rsID'de alel seçimi: ClinVar önemi en ağır olan alel > en sık alel > en ağır etkili alel
KLINIK_AGIRLIK = [(("pathogenic", "likely_pathogenic"), 3),
                  (("drug_response", "risk_factor", "protective", "association", "affects"), 2)]


def _klinik_agirlik(terimler):
    """['pathogenic', 'drug_response'] -> 3. ClinVar kaydı var ama önemsiz/belirsiz -> 1; hiç yok -> 0."""
    en = 0
    for t in terimler:
        parcalar = set(t.lower().replace(",", "/").split("/"))
        puan = next((p for adlar, p in KLINIK_AGIRLIK if parcalar & set(adlar)), 1)
        en = max(en, puan)
    return en


def klinik_alel_sec(veri):
    """Çok alelli kayıtta (rs6025: C/A/T) kartın kurulacağı alt aleli seçer. (alel, neden) | (None, None) tek alelliyse.
    Sıra: ClinVar ağırlığı (patojenik 3 > ilaç yanıtı/risk 2 > başka kayıt 1) > gnomAD sıklığı > en ağır etkiyi taşıması.
    rs6025 -> T (Leiden, R534Q; A = R534L kayıtsız), rs33950507 -> T (HbE E27K; A = stop), rs1799853 -> T (CYP2C9*2)."""
    alel = (veri.get("allele_string") or "/").split("/")
    if len(alel) <= 2:
        return None, None
    strand = veri.get("strand", 1)
    en_agir = veri.get("most_severe_consequence")
    klinik, frekans = {}, {}
    for c in veri.get("colocated_variants") or []:
        for parca in (c.get("clin_sig_allele") or "").split(";"):
            a, _, s = parca.partition(":")
            if a and s:
                klinik.setdefault(a, []).append(s)
        for a, f in (c.get("frequencies") or {}).items():
            deger = max(v for v in (f.get("gnomade"), f.get("gnomadg"), 0) if v is not None)
            frekans[a] = max(frekans.get(a, 0), deger)
    agir_aleller = {t.get("variant_allele") for t in veri.get("transcript_consequences") or []
                    if en_agir in (t.get("consequence_terms") or [])}

    def puan(a):
        a_gen = a.translate(TUMLEYEN)[::-1] if (strand == -1 and a != "-") else a     # clin_sig_allele genomik zincirde
        return (_klinik_agirlik(klinik.get(a_gen, [])), max(frekans.get(a, 0), frekans.get(a_gen, 0)), a in agir_aleller)
    secilen = max(alel[1:], key=puan)          # eşitlikte allele_string sırası korunur
    p = puan(secilen)
    neden = "klinik" if p[0] >= 2 else ("clinvar_kaydi" if p[0] == 1 else ("siklik" if p[1] > 0 else "etki"))
    return secilen, neden


def kart_olustur(veri, surum, alt_sec=None):
    """VEP cevabından anotasyon kartı çıkarır. alt_sec: çok alelli kayıtta kartın kurulacağı alel (klinik_alel_sec)."""
    uyarilar = []
    alel = (veri.get("allele_string") or "/").split("/")
    alt = alt_sec or (alel[1] if len(alel) > 1 else None)
    # VEP allele_string girdinin zincirinde gelir (transkript girdisinde ters zincir olabilir); clin_sig_allele ve
    # frequencies ise GENOMİK ileri zincirdedir -> alt'ı genomik zincire çevir (çok alelli sitelerde karışmasın)
    strand = veri.get("strand", 1)
    alt_genomik = alt.translate(TUMLEYEN)[::-1] if (alt and strand == -1 and alt != "-") else alt
    en_agir = veri.get("most_severe_consequence")
    tcs = veri.get("transcript_consequences") or []
    dogrudan = [t for t in tcs if not set(t.get("consequence_terms") or []) <= KOMSU_ETKI]   # komşu genleri ele
    aday = dogrudan or tcs
    if tcs and not dogrudan:
        uyarilar.append("Varyant bir genin içinde değil; yalnızca yakınındaki genler listelendi (gen düzeyi literatür beklenmez).")

    # Kanonik transkript: (çok alelli kayıtta) seçilen alele ait > en ağır etkiyi taşıyan > MANE Select > canonical > protein kodlayan
    def puan(t):
        return (not alt_sec or t.get("variant_allele") == alt_sec, en_agir in (t.get("consequence_terms") or []),
                bool(t.get("mane_select")), t.get("canonical") == 1, t.get("biotype") == "protein_coding", bool(t.get("gene_symbol")))
    kanonik = max(aday, key=puan) if aday else None
    kanonik_gen = kanonik.get("gene_symbol") if kanonik else None
    genler = sorted({t.get("gene_symbol") for t in aday if t.get("gene_symbol")} - {kanonik_gen})
    if kanonik_gen:
        genler.insert(0, kanonik_gen)
    hgvsc = kanonik.get("hgvsc") if kanonik else None
    hgvsp = kanonik.get("hgvsp") if kanonik else None
    if alt_sec and kanonik and kanonik.get("consequence_terms"):
        en_agir = kanonik["consequence_terms"][0]    # etki, SEÇİLEN alelin etkisi (rs33950507: missense, başka alelin 'stop'u değil)
    p3, p1 = protein_kisa(hgvsp)
    # Çok alelli kayıtta (rsID girdisi) aynı kanonik transkriptteki DİĞER alellerin protein adları (rs113488022: V600E, V600A, V600G)
    protein_diger = []
    if kanonik:
        for t in tcs:
            if t.get("transcript_id") == kanonik.get("transcript_id") and t.get("hgvsp") and t["hgvsp"] != hgvsp:
                p3x, p1x = protein_kisa(t["hgvsp"])
                protein_diger += [x for x in (p1x, p3x) if x and x not in protein_diger]
    cadd = next((t["cadd_phred"] for t in tcs if t.get("cadd_phred") is not None), None)

    rsid, clin, pubmed, gnomad, en_sik_pop = [], [], [], None, None
    for c in veri.get("colocated_variants") or []:
        kimlik = str(c.get("id", ""))
        if kimlik.startswith("rs"):
            rsid.append(kimlik)
        # Klinik önem ALELE özgü olmalı (rs334: A patojenik, G muhtemelen benign)
        csa = c.get("clin_sig_allele")
        eslesen = []
        if csa:
            ciftler = [p.partition(":") for p in csa.split(";")]
            if any(a for a, _, _ in ciftler):                       # alel anahtarları dolu (SNV)
                eslesen = [s for a, _, s in ciftler if a == alt_genomik and s]
            else:                                                   # indel: VEP alel anahtarını boş verir
                kayit_alel = (c.get("allele_string") or "/").split("/")
                if len(kayit_alel) <= 2:
                    eslesen = [s for _, _, s in ciftler if s]
                else:
                    uyari = f"ClinVar önemi çok alelli kayıttan ({c.get('allele_string')}) alele ayrılamadı; ClinVar katmanı doğrulayacak."
                    if uyari not in uyarilar:
                        uyarilar.append(uyari)
        elif c.get("clin_sig"):
            eslesen = list(c["clin_sig"])
        clin += [s for s in eslesen if s not in clin]
        for p in c.get("pubmed") or []:
            if p not in pubmed:
                pubmed.append(p)
        # frequencies sözlüğü clin_sig_allele'in aksine GİRDİNİN zincirindeki alelle anahtarlanır (canlı gözlem)
        frekanslar = c.get("frequencies") or {}
        frek = (frekanslar.get(alt) or frekanslar.get(alt_genomik)) if alt else None
        if frek:
            toplam = frek.get("gnomade") if frek.get("gnomade") is not None else frek.get("gnomadg")
            if toplam is not None and (gnomad is None or toplam > gnomad):
                gnomad = toplam
            for k, v in frek.items():
                if k.startswith(("gnomade_", "gnomadg_")) and v is not None and (en_sik_pop is None or v > en_sik_pop[1]):
                    en_sik_pop = (k, v)

    return {
        "genom_surumu": surum,
        "kromozom": veri.get("seq_region_name"),
        "pozisyon": veri.get("start"),
        "alel": veri.get("allele_string"),
        "secilen_alel": alt,        # kartın kurulduğu alt alel (çok alelli rsID'de klinik_alel_sec)
        "genler": genler,               # ilk eleman kanonik gen; komşu (upstream/downstream) genler yok
        "kanonik_gen": kanonik_gen,
        "rsid": sorted(set(rsid)),
        "etki": en_agir,
        "hgvsc": hgvsc,
        "hgvsp": hgvsp,
        "protein_3harf": p3,        # Val600Glu  (ClinVar başlık biçimi)
        "protein_kisa": p1,         # V600E      (makalelerin biçimi)
        "protein_diger": protein_diger,   # çok alelli kayıtta diğer alellerin adları (V600A, Val600Ala, ...)
        "gnomad_af": gnomad,        # toplum sıklığı (yoksa None = hiç gözlenmemiş ya da veri yok)
        "gnomad_en_sik": en_sik_pop,
        "cadd": cadd,
        "klinik_onem": clin,        # VEP'in dbSNP/ClinVar'dan derlediği, alele özgü
        "pubmed": pubmed,           # dbSNP/ClinVar kürasyonlu PMID'ler (varyanta ÖZGÜ)
        "uyarilar": uyarilar,
    }


def _surumleri_dene(hgvs, surum, ref_kontrol=None):
    """Verilen sürümde; sürüm belirtilmemişse GRCh38 sonra GRCh37'de dener.
    ref_kontrol=(chrom, pos, ref): silme/eklemede genomdaki harfleri okuyup kullanıcının ref'iyle karşılaştırır.
    (kart | None, {surum: hata_mesaji}) döndürür."""
    denenecek = [surum] if surum else ["GRCh38", "GRCh37"]
    hatalar = {}
    for s in denenecek:
        try:
            if ref_kontrol:
                chrom, pos, ref = ref_kontrol
                genom = referans_oku(chrom, pos, len(ref), s)
                if genom != ref:
                    raise VepHata(f"Reference allele extracted from {chrom}:{pos} ({genom}) does not match "
                                  f"reference allele given by HGVS notation ({ref})")
            veri = vep_hgvs(hgvs, s)
        except VepHata as e:
            hatalar[s] = str(e)
            if not REF_UYUSMAZLIK.search(str(e)):
                break                                # referans hatası değilse başka sürüm denemek anlamsız
            continue
        kart = kart_olustur(veri, s)
        if not surum and s == "GRCh37":
            kart["uyarilar"].append("Referans harf GRCh38 ile uyuşmadı, GRCh37 ile eşleşti: koordinat büyük olasılıkla "
                                    "GRCh37 (hg19). Emin değilseniz sürümü belirtin: 'GRCh37:' öneki.")
        return kart, hatalar
    return None, hatalar


def _hata_aciklamasi(hatalar):
    """VEP hata mesajlarını kullanıcı diline çevirir."""
    referanslar = {}
    for s, mesaj in hatalar.items():
        m = REF_UYUSMAZLIK.search(mesaj)
        if m:
            referanslar[s] = (m.group(1), m.group(2))
    if referanslar and all(set(g) <= {"N"} for g, _ in referanslar.values()):
        return "Pozisyon kromozom sınırlarının dışında ya da dizisi bilinmeyen bir bölgede; koordinatı kontrol edin."
    if referanslar:
        verilen = next(iter(referanslar.values()))[1]
        genomda = ", ".join(f"{s}'de '{g}'" for s, (g, _) in referanslar.items())
        ek = "; ".join(f"{s}: {m[:120]}" for s, m in hatalar.items() if s not in referanslar)
        return (f"Referans harf uyuşmuyor: siz '{verilen}' dediniz, genomda {genomda} var. "
                "Koordinat başka bir sürüme ait ya da ters zincirden yazılmış olabilir." + (f" ({ek})" if ek else ""))
    return "VEP hatası: " + "; ".join(f"{s}: {m[:200]}" for s, m in hatalar.items())


def anlamlandir(varyant):
    """VCF tarzı koordinatı anotasyon kartına çevirir. Hata durumunda {'hata': ...} döner (istisna fırlatmaz)."""
    coz = koordinati_coz(varyant)
    if coz is None:
        return {"hata": "Koordinat biçimi tanınmadı. Örnek: chr7:140753336:A>T ya da GRCh37:chr7:140453136:A>T "
                        "(kromozom 1-22/X/Y/MT, aleller yalnızca A/C/G/T)", "girdi": varyant}
    chrom, pos, ref, alt, surum = coz
    if pos < 1:
        return {"hata": "Pozisyon 1'den küçük olamaz.", "girdi": varyant}
    hgvs = hgvs_genomik(chrom, pos, ref, alt)
    if hgvs is None:
        return {"hata": "Referans ve alternatif alel aynı; değişim yok.", "girdi": varyant}
    snv = len(ref) == 1 and len(alt) == 1
    kart, hatalar = _surumleri_dene(hgvs, surum, ref_kontrol=None if snv else (chrom, pos, ref))
    if kart is None:
        return {"hata": _hata_aciklamasi(hatalar), "girdi": varyant, "hgvs_g": hgvs}
    kart["girdi"] = varyant
    kart["hgvs_g"] = hgvs
    return kart


def anlamlandir_hgvs(hgvs):
    """HGVS girdisini (GRCh38:7:g.140753336A>T, 7:g.140753336A>T, NM_004333.6:c.1799T>A) karta çevirir."""
    surum, temiz = surum_ayir(hgvs)
    if temiz.lower().startswith("chr"):
        temiz = temiz[3:]
    kart, hatalar = _surumleri_dene(temiz, surum)
    if kart is None:
        return {"hata": _hata_aciklamasi(hatalar), "girdi": hgvs}
    kart["girdi"] = hgvs
    kart["hgvs_g"] = temiz
    return kart


def anlamlandir_rsid(rsid, surum="GRCh38"):
    """rsID'yi (rs334) VEP'in id ucuyla karta çevirir. Çok alelli sitede kart, ClinVar önemi en ağır (yoksa en sık) alele
    göre kurulur (klinik_alel_sec); diğer alellerin protein adları protein_diger'de kalır."""
    try:
        veri = _ensembl_get(f"{SUNUCU[surum]}/vep/human/id/{rsid.strip().lower()}", VEP_PARAM)
    except VepHata as e:
        return {"hata": f"VEP hatası: {e}", "girdi": rsid}
    if not veri:
        return {"hata": "rsID VEP'te bulunamadı", "girdi": rsid}
    alt, neden = klinik_alel_sec(veri[0])
    kart = kart_olustur(veri[0], surum, alt_sec=alt)
    kart["girdi"] = rsid
    kart["hgvs_g"] = None
    kart["alel_secim_nedeni"] = neden
    if alt:
        aciklama = {"klinik": "ClinVar'da klinik önemi olan", "clinvar_kaydi": "ClinVar kaydı olan",
                    "siklik": "toplumda en sık görülen", "etki": "en ağır etkili"}[neden]
        aleller = veri[0].get("allele_string") or ""
        aleller = aleller if len(aleller) <= 24 else f"{aleller.count('/') + 1} alel"      # poli-A tekrarları gibi uzun kayıtlar
        alt_ad = alt if len(alt) <= 8 else f"{len(alt)} baz"
        diger = [p for p in kart.get("protein_diger") or [] if not re.match(r"^[A-Z][a-z]{2}\d", p)]   # kısa adlar (R534L)
        kart["uyarilar"].append(f"Çok alelli kayıt ({aleller}); kart {aciklama} alele göre kuruldu "
                                f"({alt_ad}: {kart.get('protein_kisa') or kart.get('hgvsc') or '-'})"
                                + (f"; diğer aleller: {', '.join(diger)}" if diger else "") + ".")
    return kart


def girdi_turu(metin):
    """'koordinat' / 'hgvs' / None — sonraki adımlar (gen doğrulama, sorgu kurucu) için.
    'BRAF:p.V600E' gibi gen sembolü + protein yazımı None döner (VEP çözemez; gen yolu doğrular)."""
    _, geri = surum_ayir(metin)
    if koordinati_coz(metin):
        return "koordinat"
    if HGVS.match(geri):
        return "hgvs"
    return None


def anlamlandir_herhangi(metin):
    """Girdi türüne göre uygun çözücüyü çağırır; koordinat/HGVS değilse None."""
    tur = girdi_turu(metin)
    if tur == "koordinat":
        return anlamlandir(metin)
    if tur == "hgvs":
        return anlamlandir_hgvs(metin)
    return None


def kart_yazdir(kart):
    if "hata" in kart:
        print(f"  HATA: {kart['hata']}")
        return
    print(f"  {kart['genom_surumu']} {kart['kromozom']}:{kart['pozisyon']} {kart['alel']} | gen: {kart['kanonik_gen']} "
          f"(tümü: {', '.join(kart['genler']) or '-'}) | rsID: {', '.join(kart['rsid']) or '-'}")
    print(f"  etki: {kart['etki']} | c.: {kart['hgvsc']} | p.: {kart['protein_3harf']} = {kart['protein_kisa']}")
    print(f"  gnomAD: {kart['gnomad_af']} (en sık: {kart['gnomad_en_sik']}) | CADD: {kart['cadd']} | "
          f"klinik: {', '.join(kart['klinik_onem']) or '-'} | PMID sayısı: {len(kart['pubmed'])}")
    for u in kart["uyarilar"]:
        print(f"  UYARI: {u}")


def main():
    testler = [
        "chr7:140753336:A>T",            # BRAF V600E (GRCh38)
        "chr7:140753336:G>T",            # yanlış referans harf -> anlaşılır hata
        "chr7:140753336:AT>A",           # yanlış silme referansı (genomda 140753337 = C) -> hata (dizi servisi)
        "chr7:117559590:ATCT>A",         # CFTR F508del (VCF) -> Phe508del
        "chr7:117559590:A>ATCT",         # F508dup (ekleme); çok alelli ClinVar kaydı -> uyarı, klinik boş
        "chr7:140453136:A>T",            # GRCh37 koordinatı, öneksiz -> GRCh37'ye düşmeli + uyarı
        "chr11:5227002:T>A",             # rs334 (HBB) — alele özgü klinik önem
        "chrM:3243:A>G",                 # MELAS: kanonik gen MT-TL1, komşu genler listede yok
        "NM_004333.6:c.1799T>A",         # transkript girdisi (ters zincir) -> klinik önem V600E'nin olmalı
        "7:g.140753336A>G",              # V600A: çok alelli site, yanlış alelin (V600G) önemi gelmemeli
        "chr7:0:A>T",                    # pozisyon 0 -> VEP'e gitmeden hata
        "chr7:140753336:A>A",            # değişim yok -> hata
        "chr23:100:A>T",                 # geçersiz kromozom -> tanınmadı
        "BRAF:p.V600E",                  # HGVS değil -> None (gen yolu)
        "BRAF V600E",                    # koordinat değil -> None
    ]
    for t in testler:
        print(f"\n=== {t} ===")
        kart = anlamlandir_herhangi(t)
        if kart is None:
            print("  (koordinat/HGVS değil; anlamlandırma gerekmez)")
        else:
            kart_yazdir(kart)


if __name__ == "__main__":
    main()
