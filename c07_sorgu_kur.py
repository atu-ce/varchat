"""
SORGU KURUCU + ALAKA KAPISI — girdiyi yapısal kayda çevirir, PubMed'i kademeli arar, kaynakları etiketler.

Neden: Eski hat koordinat girdisinde yalnızca GEN adını arıyordu (BRAF: 28.771 makale) ve gen düzeyi makaleleri
varyant hakkındaymış gibi özetliyordu. Kelime araması yazıma da duyarlıydı ("BRAF:p.V600E" -> 270 sonuç).

Akış:
  girdi -> varyant_kaydi()   : gen, rsID, protein değişimi (V600E ve Val600Glu), cDNA; koordinat/HGVS/rsID ise c02 kartı
        -> kaynaklari_getir() : 1) varyanta özgü PubMed sorgusu  "BRAF[tiab] AND (V600E[tiab] OR Val600Glu[tiab] OR rs113488022[tiab])"
                                2) VEP/dbSNP'nin kürasyonlu PMID listesi (varyanta ÖZGÜ; metinde ad geçmese de dbSNP bağlamış)
                                3) yetmezse gen düzeyi sorgu  "BRAF[tiab] AND (variant* OR mutation* OR polymorphism*)"
           her makale etiketlenir: 'varyant' (metinde varyant adı geçiyor) / 'kurasyon' (dbSNP bağlamış) /
                                   'gen' (yalnızca gen adı) / 'ilgisiz'
           kademe: 'varyant' / 'gen' / 'yok'  -> ana uygulama gen düzeyinde dürüst uyarı verir.
"""

import re
import sys

import c02_varyant_anlamlandir as c02
from c01_makale_getir import makale_ara_ayrintili, makale_detaylari_al, kunye

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

AMINO_1TO3 = {v: k for k, v in c02.AMINO_3TO1.items() if len(v) == 1 and v != "*"}
AMINO_1TO3["*"] = "Ter"

# Klinikte/literatürde yaygın takma adlar -> HGNC sembolü
GEN_ALIAS = {"P53": "TP53", "HER2": "ERBB2", "MLL": "KMT2A", "CMYC": "MYC", "C-MYC": "MYC", "FACTOR": "F5", "CKIT": "KIT"}
# ClinVar/VEP numarası = literatür numarası + kaydırma (HBB: Glu7Val vs Glu6Val; başlangıç metiyonini sayılıyor mu?)
ESKI_NUMARALAMA = {"HBB": 1}

_DEG = r"(?:[A-Za-z][a-z]{2}\d+(?:[A-Za-z][a-z]{2}|del|dup|fs\*?\d*|Ter|\*|X|=)|[A-Za-z]\d+(?:[A-Za-z]|del|dup|fs\*?\d*|\*|=))"
# "BRAF V600E", "BRAF:p.V600E", "BRAF p.Val600Glu", "CFTR F508del", "TERT promoter C228T", "JAK2V617F", "EGFR L858R/T790M"
GEN_DEGISIM = re.compile(
    r"^(?P<gen>[A-Za-z][A-Za-z0-9-]{1,14}?)(?:[\s:_/-]*(?:promoter|exon\s*\d+)?[\s:_/-]*)(?:p\.)?"
    r"(?P<deg>" + _DEG + r"(?:\s*[/,]\s*(?:p\.)?" + _DEG + r")*)$",
    re.IGNORECASE,
)
DEG_HERHANGI = re.compile(r"(?<![A-Za-z0-9])(?:p\.)?(" + _DEG + r")(?![A-Za-z0-9])")
DEG_1HARF = re.compile(r"^([A-Z])(\d+)([A-Z]|del|dup|fs\*?\d*|\*|X|=)$", re.IGNORECASE)
DEG_3HARF = re.compile(r"^([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|del|dup|fs\*?\d*|Ter|\*|=)$", re.IGNORECASE)
RSID = re.compile(r"^rs\s*(\d+)$", re.IGNORECASE)
KISALTMA_TANIMI = re.compile(r"((?:[A-Za-z][a-z]+\s+(?:of\s+|the\s+|in\s+|and\s+)?){1,6})\(\s*([A-Za-z0-9-]{2,10})\s*\)")


def _protein_bicimleri(deg):
    """'V600E' -> ('V600E', 'Val600Glu'); 'val600glu' -> aynı çift; 'F508del' -> ('F508del', 'Phe508del');
    'R175*' -> ('R175X', 'Arg175Ter')  ('*' PubMed'de joker olduğu için X yazımı)."""
    m3 = DEG_3HARF.match(deg)
    if m3:
        a, poz, b = m3.groups()
        a = a.capitalize()
        b = b.capitalize() if len(b) == 3 and b.isalpha() else b.lower()
        a1 = c02.AMINO_3TO1.get(a, a)
        b1 = c02.AMINO_3TO1.get(b, b) if len(b) == 3 and b.isalpha() else b
        if b1 == "*":
            b1 = "X"
        return f"{a1}{poz}{b1}", f"{a}{poz}{b}"
    m1 = DEG_1HARF.match(deg)
    if m1:
        a, poz, b = m1.group(1).upper(), m1.group(2), m1.group(3)
        b_kisa = b.upper() if len(b) == 1 else b.lower()
        if b_kisa in ("*", "X"):
            return f"{a}{poz}X", f"{AMINO_1TO3.get(a, a)}{poz}Ter"
        b3 = AMINO_1TO3.get(b_kisa, b_kisa) if len(b_kisa) == 1 else b_kisa
        return f"{a}{poz}{b_kisa}", f"{AMINO_1TO3.get(a, a)}{poz}{b3}"
    return deg, None


def _eski_numaralama(kayit, yon):
    """HBB gibi genlerde literatür (E6V) ile ClinVar/VEP (E7V) numaralaması 1 kayar; öteki yazımı da arama listesine ekler.
    yon=-1: VEP numarasından literatüre; yon=+1: kullanıcı literatür yazdıysa ClinVar biçimi."""
    kaydir = ESKI_NUMARALAMA.get(kayit.get("gen") or "")
    if not kaydir or not kayit.get("protein_kisa"):
        return
    m = DEG_1HARF.match(kayit["protein_kisa"])
    if m:
        a, poz, b = m.groups()
        yeni = f"{a}{int(poz) + kaydir * yon}{b}"
        kayit["protein_diger"] += [t for t in _protein_bicimleri(yeni) if t and t not in kayit["protein_diger"]]
        kayit["uyarilar"].append(f"{kayit['gen']} için farklı numaralama ({yeni}) da aranıyor.")


def varyant_kaydi(girdi):
    """Herhangi bir girdiyi yapısal kayda çevirir:
       {girdi, tur, gen, rsid[], protein_kisa, protein_3harf, protein_diger[], cdna, ek_terimler[], kart|None,
        pubmed_kurasyon[], uyarilar[], hata?}"""
    g = re.sub(r"[\s?!.,;]+$", "", girdi.strip())                      # "BRAF V600E?" -> "BRAF V600E"
    g = re.sub(r"^rs\s+(\d+)$", r"rs\1", g, flags=re.IGNORECASE)      # "rs 334" -> "rs334"
    kayit = {"girdi": g, "tur": None, "gen": None, "rsid": [], "protein_kisa": None, "protein_3harf": None,
             "protein_diger": [], "cdna": None, "ek_terimler": [], "kart": None, "pubmed_kurasyon": [], "uyarilar": []}
    tur = c02.girdi_turu(g)
    if tur in ("koordinat", "hgvs") or RSID.match(g):
        kart = c02.anlamlandir_rsid(g) if RSID.match(g) else c02.anlamlandir_herhangi(g)
        kayit["tur"] = "rsid" if RSID.match(g) else tur
        kayit["kart"] = kart
        if "hata" in kart:
            kayit["hata"] = kart["hata"]
            if RSID.match(g):
                kayit["rsid"] = [g.lower()]     # kart gelmese de rsID ile aranabilir
            return kayit
        kayit.update(gen=kart.get("kanonik_gen"), rsid=list(kart.get("rsid") or []),
                     protein_kisa=kart.get("protein_kisa"), protein_3harf=kart.get("protein_3harf"),
                     protein_diger=list(kart.get("protein_diger") or []),
                     pubmed_kurasyon=[str(p) for p in kart.get("pubmed") or []], uyarilar=list(kart.get("uyarilar") or []))
        if kart.get("hgvsc") and ":c." in kart["hgvsc"]:
            kayit["cdna"] = "c." + kart["hgvsc"].split(":c.", 1)[1]
        if RSID.match(g) and g.lower() not in kayit["rsid"]:
            kayit["rsid"].insert(0, g.lower())
        _eski_numaralama(kayit, -1)
        return kayit
    m = GEN_DEGISIM.match(g)
    if m:
        kayit["tur"] = "gen_degisim"
        kayit["gen"] = GEN_ALIAS.get(m.group("gen").upper(), m.group("gen").upper())
        degler = [d.strip() for d in re.split(r"\s*[/,]\s*", m.group("deg")) if d.strip()]
        kayit["protein_kisa"], kayit["protein_3harf"] = _protein_bicimleri(degler[0].replace("p.", ""))
        for d in degler[1:]:                                           # "EGFR L858R/T790M": ikinci değişim de aranır
            kayit["protein_diger"] += [t for t in _protein_bicimleri(d.replace("p.", "")) if t]
        if "promoter" in g.lower() or re.search(r"\bc\.", g):        # C228T gibi nükleotid değişimi: protein adı yok
            kayit["protein_3harf"] = None
        _eski_numaralama(kayit, +1)
        return kayit
    # Gen + serbest ifade: "MET exon 14 skipping", "F5 Leiden", "BRCA1 5382insC", "KRAS G12C hangi kanserlerde"
    m = re.match(r"^(?P<gen>[A-Za-z][A-Za-z0-9-]{1,14})\b[\s:_/-]*(?P<geri>.*)$", g)
    kayit["tur"] = "gen"
    kayit["gen"] = GEN_ALIAS.get((m.group("gen") if m else g.split()[0]).upper(), (m.group("gen") if m else g.split()[0]).upper())
    geri = (m.group("geri") if m else "").strip(" :-_/")
    if geri:
        d = DEG_HERHANGI.search(geri)
        if d:                                                          # ifadenin içinde bir değişim var
            kayit["tur"] = "gen_degisim"
            kayit["protein_kisa"], kayit["protein_3harf"] = _protein_bicimleri(d.group(1))
            _eski_numaralama(kayit, +1)
        else:                                                          # "exon 14 skipping", "Leiden", "5382insC"
            kayit["tur"] = "gen_ifade"
            kayit["ek_terimler"] = [geri]
    return kayit


def model_etiketi(kayit, girdi=None):
    """Modele (system mesajı ve ilk soru) verilecek varyant adı. Kaynaklar varyantı gen + değişim ya da rsID ile anar, koordinatla
    anmaz; model 'chr1:11796321:G>A hakkında' sorulunca kaynaklarda bu diziyi bulamayıp 'bilgi yok' diyordu (5 Ekim, 11/11).
      'BRAF V600E', 'MET exon 14 skipping'  -> aynen (eğitim verisindeki biçim)
      'rs1801133'                           -> 'MTHFR A222V (rs1801133)'
      'chr1:11796321:G>A'                   -> 'MTHFR A222V (rs1801133; chr1:11796321:G>A)'
      'chr1:17001759:A>T' (intron)          -> 'ATP13A2 c.705+275T>A (rs898043018; chr1:17001759:A>T)'
    Gen ya da değişim çözülemediyse girdinin kendisi döner."""
    girdi = (girdi or kayit.get("girdi") or "").strip()
    tur = kayit.get("tur")
    if tur not in ("rsid", "koordinat", "hgvs"):
        return girdi
    gen = kayit.get("gen")
    degisim = kayit.get("protein_kisa") or kayit.get("cdna")
    if not gen or not degisim:
        return girdi
    kimlikler = list((kayit.get("rsid") or [])[:1])
    if tur in ("koordinat", "hgvs"):
        kimlikler.append(girdi)
    return f"{gen} {degisim}" + (f" ({'; '.join(kimlikler)})" if kimlikler else "")


def _tiab(terim):
    """PubMed alan etiketi: boşluk/özel karakter içerenler tırnaklanır."""
    return f'"{terim}"[tiab]' if re.search(r"[\s>.]", terim) else f"{terim}[tiab]"


def _terimler(kayit):
    adaylar = [kayit.get("protein_kisa"), kayit.get("protein_3harf"), *kayit.get("protein_diger", []),
               *kayit.get("rsid", []), kayit.get("cdna"), *kayit.get("ek_terimler", [])]
    # 'V600=' sinonim yazımı ve '*' (PubMed jokeri) sorguya girmez; E7V gibi 3 karakterli adlar geçerli
    return [t for t in dict.fromkeys(a for a in adaylar if a) if len(t) >= 3 and not t.endswith("=") and "*" not in t]


def pubmed_sorgulari(kayit):
    """(varyant düzeyi sorgu | None, gen düzeyi sorgu | None)."""
    gen = kayit.get("gen")
    varyant_blok = " OR ".join(_tiab(t) for t in _terimler(kayit))
    if gen and varyant_blok:
        k1 = f"{gen}[tiab] AND ({varyant_blok})"
    elif varyant_blok:
        k1 = varyant_blok
    else:
        k1 = None
    # Gen düzeyi: yalnızca sembol değil, varyant bağlamı da olsun (MET = metiyonin, CAT = katalaz gibi çakışmaları azaltır)
    k2 = f"{gen}[tiab] AND (variant*[tiab] OR mutation*[tiab] OR polymorphism*[tiab])" if gen else None
    return k1, k2


def _normalize(metin):
    m = metin.lower().replace("*", "x")
    m = re.sub(r"\s*>\s*", ">", m)             # "c.20A > T" -> "c.20a>t"
    m = re.sub(r"\s*:\s*c\.", ":c.", m)
    return m


def _baska_kisaltma_mi(metin_ham, gen):
    """'Transient tachypnea of newborn (TTN)' gibi, baş harfleri gen sembolünü veren bir kısaltma tanımı var mı?
    'titin (TTN)' bunu tetiklemez (baş harfler 'T' != 'TTN')."""
    for kelimeler, kisaltma in KISALTMA_TANIMI.findall(metin_ham):
        if kisaltma.upper() != gen.upper():
            continue
        bas = "".join(k[0] for k in kelimeler.split() if k.lower() not in ("of", "the", "in", "and")).upper()
        if len(gen) >= 2 and bas.endswith(gen.upper()):
            return True
    return False


def alaka_etiketi(makale, kayit):
    """'varyant' / 'gen' / 'ilgisiz'. Kelime sınırı: solda yalnızca gen adı bitişik olabilir (BRAFV600E), sağda harf/rakam olamaz."""
    metin_ham = f"{makale.get('baslik', '')} {makale.get('ozet', '')}"
    metin = _normalize(metin_ham)
    gen = (kayit.get("gen") or "").lower()
    adaylar = [kayit.get("protein_kisa"), kayit.get("protein_3harf"), *kayit.get("protein_diger", []),
               *kayit.get("rsid", []), *kayit.get("ek_terimler", [])]
    if kayit.get("cdna"):
        adaylar.append(kayit["cdna"].replace("c.", ""))
    for t in adaylar:
        if not t or len(t) < 3:
            continue
        t = _normalize(t)
        sol = rf"(?:(?<![a-z0-9])|(?<={re.escape(gen)}))" if gen else r"(?<![a-z0-9])"
        if re.search(sol + re.escape(t) + r"(?![a-z0-9])", metin):
            return "varyant"
    if gen and re.search(rf"(?<![a-z0-9]){re.escape(gen)}(?![a-z0-9])", metin):
        if _baska_kisaltma_mi(metin_ham, gen):          # 'TTN' = Transient Tachypnea of Newborn
            return "ilgisiz"
        return "gen"
    return "ilgisiz"


def kaynaklari_getir(girdi, adet=5):
    """Kademeli arama + alaka kapısı. Sözlük:
       kayit, makaleler (alaka etiketli: varyant/kurasyon önce, sonra gen), kademe ('varyant'|'gen'|'yok'|'hata'),
       sayilar {varyant_toplam, gen_toplam, kurasyon}, sorgular {varyant, gen, ceviri, dusen}, uyarilar"""
    kayit = varyant_kaydi(girdi)
    sonuc = {"kayit": kayit, "makaleler": [], "kademe": "yok", "sayilar": {}, "sorgular": {}, "uyarilar": list(kayit["uyarilar"])}
    if "hata" in kayit and not kayit.get("rsid"):
        sonuc["kademe"] = "hata"
        sonuc["uyarilar"].append(kayit["hata"])
        return sonuc
    k1, k2 = pubmed_sorgulari(kayit)
    sonuc["sorgular"] = {"varyant": k1, "gen": k2}
    secilen, gorulen = [], set()

    def ekle(makaleler, kabul=("varyant",), ust_etiket=None):
        for m in makaleler:
            if m["pmid"] in gorulen or m["ozet"] == "(özet yok)" or (m.get("baslik") or "").strip().lower() in ("[not available]", "(başlık yok)"):
                continue                                  # özetsiz ya da başlıksız kayıt LLM'e verilmez
            m["alaka"] = alaka_etiketi(m, kayit)
            if m["alaka"] not in kabul:
                continue
            if ust_etiket and m["alaka"] != "varyant":
                m["alaka"] = ust_etiket          # 'kurasyon': dbSNP/ClinVar varyanta bağlamış, metinde ad geçmiyor
            gorulen.add(m["pmid"])
            secilen.append(m)
            if len(secilen) >= adet:
                return True
        return False

    # 1) Varyanta özgü sorgu (adayları bol tut: alaka kapısı eleyebilir)
    if k1:
        s1 = makale_ara_ayrintili(k1, adet * 2)
        sonuc["sayilar"]["varyant_toplam"] = s1["toplam"]
        sonuc["sorgular"]["ceviri"] = s1["ceviri"]
        sonuc["sorgular"]["dusen"] = s1["dusen"]
        # Yalnızca kullanıcının kendi yazdığı ifadeler düşünce uyar (otomatik türetilen Val600Glu gibi eşanlamlılar değil)
        kullanici_dusen = [d for d in s1["dusen"] if d.lower() in kayit["girdi"].lower()]
        if kullanici_dusen:
            sonuc["uyarilar"].append(f"PubMed şu ifadeleri bulamayıp sorgudan attı: {', '.join(kullanici_dusen)}")
        if s1["pmidler"]:
            ekle(makale_detaylari_al(s1["pmidler"]), kabul=("varyant",))
    # 2) Kürasyonlu PMID'ler (VEP/dbSNP): varyanta özgü; metinde ad geçmese de kabul (etiket 'kurasyon'); yeni yıl öne
    if len(secilen) < adet and kayit.get("pubmed_kurasyon"):
        adaylar = [p for p in kayit["pubmed_kurasyon"] if p not in gorulen][:200]
        sonuc["sayilar"]["kurasyon"] = len(kayit["pubmed_kurasyon"])
        if adaylar:
            ms = makale_detaylari_al(adaylar)
            ms.sort(key=lambda m: (alaka_etiketi(m, kayit) != "varyant", -(int(m["yil"]) if str(m.get("yil", "")).isdigit() else 0)))
            ekle(ms, kabul=("varyant", "gen", "ilgisiz"), ust_etiket="kurasyon")
    varyant_sayisi = sum(m["alaka"] in ("varyant", "kurasyon") for m in secilen)
    # 3) Gen düzeyi (yalnızca boşluk kalırsa; 'ilgisiz' alınmaz)
    if len(secilen) < adet and k2:
        s2 = makale_ara_ayrintili(k2, adet * 2)
        sonuc["sayilar"]["gen_toplam"] = s2["toplam"]
        if s2["pmidler"]:
            ekle(makale_detaylari_al(s2["pmidler"]), kabul=("gen",))
    sonuc["makaleler"] = secilen
    sonuc["kademe"] = "varyant" if varyant_sayisi else ("gen" if secilen else "yok")
    if sonuc["kademe"] == "gen":
        sonuc["uyarilar"].append("Bu varyanta özgü makale bulunamadı; kaynaklar GEN düzeyindedir.")
    elif varyant_sayisi < len(secilen):
        sonuc["uyarilar"].append(f"{varyant_sayisi} kaynak varyanta özgü, {len(secilen) - varyant_sayisi} kaynak gen düzeyi.")
    return sonuc


def baglam_metni(makaleler):
    """Modele verilecek numaralı kaynak metni (fine-tune verisiyle BİREBİR aynı biçim; gen düzeyi kaynaklar işaretlenir).
    Künye prompt'a girmez (eğitim/kullanım eşitliği); kaynak listesinde kullanıcıya gösterilir."""
    parcalar = []
    for i, m in enumerate(makaleler, start=1):
        etiket = " (GEN DÜZEYİ: varyantın kendisini anmıyor)" if m.get("alaka") == "gen" else ""
        parcalar.append(f"[{i}] Başlık: {m['baslik']}{etiket}\n    Özet: {m['ozet']}")
    return "\n\n".join(parcalar)


def main():
    testler = ["BRAF V600E", "rs113488022", "rs334", "HBB E6V", "TP53 R175*", "EGFR L858R/T790M",
               "MET exon 14 skipping", "TTN R6318W", "chr1:17001759:A>T", "p53 R175H"]
    for t in testler:
        print(f"\n=== {t} ===")
        s = kaynaklari_getir(t, adet=5)
        k = s["kayit"]
        print(f"  kayıt: tür={k['tur']} gen={k['gen']} rsID={k['rsid']} p={k['protein_kisa']}/{k['protein_3harf']} "
              f"diğer={k['protein_diger']} cDNA={k['cdna']} ek={k['ek_terimler']} kürasyon={len(k['pubmed_kurasyon'])}")
        print(f"  sorgu: {s['sorgular'].get('varyant')} | sayılar: {s['sayilar']} | kademe: {s['kademe']}")
        for m in s["makaleler"]:
            print(f"    [{m['alaka']:8}] {m['pmid']} {m['baslik'][:66]} | {kunye(m)}")
        for u in s["uyarilar"]:
            print(f"  UYARI: {u}")


if __name__ == "__main__":
    main()
