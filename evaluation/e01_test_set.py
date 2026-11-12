"""
DONDURULMUŞ TEST SETİ (adım 8) — fine-tune eğitim girdilerinin genleriyle (ilk sürüm 31 + ikinci sürüm 74 = 105 gen)
KESİŞMEYEN varyantlar, dört katman.

Neden: ilk arama ölçümünün (arşivdeki b01) 8 varyantı eğitim setindeydi; fine-tune sonrası aynı setle ölçüm "öğrendi" ile "hatırladı"yı ayıramaz.
Bu liste bir kez dondurulur ve eğitime ASLA katılmaz. Koordinat biçimleri VEP'ten türetilir (e02), elle yazılmaz.

Katmanlar:
  A_hotspot         : iyi çalışılmış somatik kanser varyantları (kolay; literatür bol)
  B_germline_yaygin : klinikte sık istenen kalıtsal varyantlar, çoğu ESKİ adla (ClinVar başlığıyla eşleşmez)
  C_kimlik          : rsID girdileri (+ e02'ün türettiği GRCh38/GRCh37 koordinat biçimleri = C_koordinat)
  D_literatursuz    : varyanta özgü yayını olmayan / özette anılmayan girdiler (beklenen davranış: 'gen düzeyi' uyarısı, varyant iddiası YOK)

Sürüm notu (26 Eylül 2026 denetimi):
  - rs113993960 (CFTR F508del) C katmanından çıkarıldı: CFTR eğitim genidir ve F508del eğitim setinde 158 kez geçiyordu (sızıntı).
    Yerine rs1799853 (CYP2C9 R144C, *2 aleli; ilaç yanıtı, LitVar ~950 PMID) alındı; CYP2C9 eğitim verisinde hiç geçmiyor.
  - KCNQ1 R555C D katmanından B'ye taşındı: LitVar'da 36 PMID'li gerçek bir LQT1 varyantı, 'literatürsüz' değil.
  - KOORDINAT_TURET hedefi HARF değil PROTEİN DEĞİŞİMİ: rs6025'te GRCh37 referansı Leiden alelini taşır (T/C), harf taşımak yanlış varyant üretiyordu.
"""

# Eğitim verisinin İLK sürümündeki (v3, 204 örnek) girdilerin genleri. İkinci sürümde eklenen 74 girdinin genleri bu listede
# YOKTUR; onlar tum_egitim_genleri() ile, veriyi üreten hattın kaynak dosyasından okunur (archive/dataset_build_v4/).
EGITIM_GENLERI = {"ABL1", "AKT1", "ALK", "AR", "BRAF", "CFTR", "CTNNB1", "DNMT3A", "EGFR", "ESR1", "FGFR3", "FLT3", "GNAQ",
                  "HFE", "HRAS", "IDH1", "IDH2", "JAK2", "KIT", "KRAS", "MPL", "MYD88", "NRAS", "PDGFRA", "PIK3CA", "POLE",
                  "PTEN", "RET", "SF3B1", "TERT", "TP53"}


def tum_egitim_genleri():
    """Eğitim verisindeki BÜTÜN girdilerin genleri: ilk sürümün 31 geni + ikinci sürümde eklenen girdilerin genleri (rsID ve
    koordinat girdilerinde VEP'in çözdüğü gen). İkinci sürümün kaynak dosyası yoksa yalnız ilk 31 gen döner.
    12 Kasım 2026 denetimi: sızıntı kontrolü yalnız ilk 31 gene bakıyordu; ikinci sürümün 74 geni kontrol dışıydı
    (kesişim onlarla da boş çıktı: 37 test geni, 105 eğitim geni)."""
    import json
    import os
    genler = set(EGITIM_GENLERI)
    kaynak = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "archive", "dataset_build_v4", "inputs",
                          "kaynaklar_v4.jsonl")
    if os.path.exists(kaynak):
        for satir in open(kaynak, encoding="utf-8"):
            if satir.strip():
                gen = json.loads(satir).get("gen")
                if gen:
                    genler.add(gen.upper())
    return genler

KATMANLAR = {
    "A_hotspot": [
        "MET D1228N", "ERBB2 L755S", "ROS1 G2032R", "SMO W535L", "EZH2 Y646N", "GNAS R201C", "U2AF1 S34F",
        "CSF3R T618I", "SMAD4 R361H", "CDK4 R24C", "NOTCH1 L1601P", "FBXW7 R465C", "RAC1 P29S", "MAP2K1 K57N", "SRSF2 P95H",
    ],
    "B_germline_yaygin": [
        "MTHFR C677T", "MTHFR A1298C", "F5 R506Q", "F2 G20210A", "SERPINA1 E342K", "SERPINA1 E264V", "HBB E6V", "HBB E26K",
        "GJB2 35delG", "BRCA1 5382insC", "BRCA2 6174delT", "PAH R408W", "G6PD V68M", "TPMT A154T", "KCNQ1 R555C",
    ],
    "C_kimlik": [
        "rs1801133", "rs6025", "rs4244285", "rs429358", "rs1799971", "rs4680", "rs1800497", "rs12913832",
        "rs121913671", "rs1799853",
    ],
    "D_literatursuz": [
        "chr1:17001759:A>T", "chr1:62578974:CAA>C", "TTN R6318W", "rs898043018", "rs199915737",
    ],
}

# C katmanı: e02 bu rsID'ler için GRCh38 (çıplak) ve GRCh37 ('GRCh37:' önekli) koordinat biçimi türetir (C_koordinat).
# Hedef, VEP numaralamasıyla PROTEİN DEĞİŞİMİ: e02 her sürümde alt alelleri tek tek çözer, hedefi veren aleli seçer;
# hiçbir alel vermiyorsa (GRCh37'de rs6025 referansı zaten Leiden alelidir) o sürüm için satır üretmez ve uyarı yazar.
KOORDINAT_TURET = {"rs1801133": "A222V", "rs6025": "R534Q", "rs4244285": "P227=", "rs121913671": "D1228N",
                   "rs1799853": "R144C", "rs429358": "C130R"}

# AYNI VARYANTIN FARKLI YAZIMLARI. Test seti aynı varyantı bilerek birkaç biçimde sorar (gen+değişim, rsID, GRCh38/GRCh37
# koordinat): amaç girdi biçimine dayanıklılığı ölçmek. Ama bu satırlar istatistikte BAĞIMSIZ gözlem değildir: 56 satır = 40 farklı
# varyant. Güven aralığı hesaplanırken aynı varyantın satırları birlikte örneklenir (küme bootstrap, e06). Anahtar = rsID.
# Türetilmiş koordinat satırlarının (C_koordinat) anahtarı e02 çıktısındaki 'kaynak_rsid' alanından okunur.
AYNI_VARYANT = {
    "MET D1228N": "rs121913671", "MTHFR C677T": "rs1801133", "F5 R506Q": "rs6025",      # A/B'deki ad = C'deki rsID
    "chr1:17001759:A>T": "rs898043018", "chr1:62578974:CAA>C": "rs199915737",           # D: aynı varyantın koordinat ve rsID yazımı
}

# D katmanı: doğru cevap listesi yok (ya da özette anılmıyor); ölçü P@5 değil, BEKLENEN KADEME:
# sistem varyanta özgü iddia yapmamalı -> kademe 'gen' (gen düzeyi kaynak + uyarı) ya da 'yok' kabul; 'varyant' = yanlış varyant iddiası.
BEKLENEN_KADEME = {g: ("gen", "yok") for g in KATMANLAR["D_literatursuz"]}


def hepsi():
    for katman, liste in KATMANLAR.items():
        for g in liste:
            yield katman, g


def gen_kesisimi():
    """Test setindeki gen sembolleri (rsID/koordinat girdilerinin VEP çözümü dahil, e02 çıktısı varsa) eğitim setiyle kesişiyor mu?
    Boş küme beklenir. Not: gen DÜZEYİNDE bazı semboller (CDK4, MET, MAP2K1, ERBB2) eğitim özet metinlerinde anılıyor;
    kesişimsizlik VARYANT düzeyindedir, tezde 'gen düzeyinde sızıntı yok' denmemeli."""
    import json
    import os
    genler = {g.split()[0].upper() for k, g in hepsi() if not g.lower().startswith(("rs", "chr", "grch"))}
    gt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "dogru_cevap.jsonl")
    if os.path.exists(gt):
        for satir in open(gt, encoding="utf-8"):
            d = json.loads(satir)
            if d.get("gen"):
                genler.add(d["gen"].upper())
    return genler & tum_egitim_genleri()


def kume_haritasi():
    """{girdi: küme anahtarı}: aynı varyantın bütün yazımları aynı anahtarı alır (tek yazımlı varyantın anahtarı kendisidir).
    Doğru cevap listesindeki (e02) 56 satır üzerinden kurulur; liste yoksa yalnız AYNI_VARYANT döner."""
    import json
    import os
    harita = dict(AYNI_VARYANT)
    gt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "dogru_cevap.jsonl")
    if os.path.exists(gt):
        for satir in open(gt, encoding="utf-8"):
            if satir.strip():
                d = json.loads(satir)
                harita[d["girdi"]] = d.get("kaynak_rsid") or harita.get(d["girdi"]) or d["girdi"]
    return harita


def kume_kontrolu():
    """AYNI_VARYANT bildirimlerini doğru cevap listesiyle sınar: bildirilen rsID o girdinin kaydında gerçekten var mı?
    (girdinin VEP rsID'si ya da LitVar'ın o ada bağladığı rsID). Uyuşmayanların listesi döner; boş liste beklenir."""
    import json
    import os
    gt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "dogru_cevap.jsonl")
    if not os.path.exists(gt):
        return []
    satirlar = {json.loads(l)["girdi"]: json.loads(l) for l in open(gt, encoding="utf-8") if l.strip()}
    sorunlu = []
    for girdi, rsid in AYNI_VARYANT.items():
        d = satirlar.get(girdi) or {}
        bilinen = set(d.get("rsid") or []) | {k.get("rsid") for k in d.get("litvar_kayitlar") or []}
        if rsid not in bilinen:
            sorunlu.append((girdi, rsid, sorted(x for x in bilinen if x)))
    return sorunlu


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    n = sum(len(v) for v in KATMANLAR.values())
    print(f"{n} girdi, {len(KATMANLAR)} katman; eğitim genleri: {len(tum_egitim_genleri())} "
          f"(ilk sürüm {len(EGITIM_GENLERI)}); test genleriyle kesişim: {gen_kesisimi() or 'yok'}")
    h = kume_haritasi()
    print(f"ölçüm satırı: {len(h)} | farklı varyant (küme): {len(set(h.values()))} | "
          f"birden çok yazımı olan varyant: {sum(1 for k in set(h.values()) if list(h.values()).count(k) > 1)}")
    print(f"AYNI_VARYANT bildirimleri doğru cevap listesiyle uyuşmuyor: {kume_kontrolu() or 'yok (hepsi doğrulandı)'}")
