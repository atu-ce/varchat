"""
DONDURULMUŞ TEST SETİ (adım 8) — fine-tune eğitim setiyle (31 gen) KESİŞMEYEN varyantlar, dört katman.

Neden: b01'in 8 varyantı eğitim setindeydi; fine-tune sonrası aynı setle ölçüm "öğrendi" ile "hatırladı"yı ayıramaz.
Bu liste bir kez dondurulur ve eğitime ASLA katılmaz. Koordinat biçimleri VEP'ten türetilir (b04), elle yazılmaz.

Katmanlar:
  A_hotspot         : iyi çalışılmış somatik kanser varyantları (kolay; literatür bol)
  B_germline_yaygin : klinikte sık istenen kalıtsal varyantlar, çoğu ESKİ adla (ClinVar başlığıyla eşleşmez)
  C_kimlik          : rsID girdileri (+ b04'ün türettiği GRCh38/GRCh37 koordinat biçimleri = C_koordinat)
  D_literatursuz    : varyanta özgü yayını olmayan / özette anılmayan girdiler (beklenen davranış: 'gen düzeyi' uyarısı, varyant iddiası YOK)

Sürüm notu (26 Eylül 2026 denetimi):
  - rs113993960 (CFTR F508del) C katmanından çıkarıldı: CFTR eğitim genidir ve F508del eğitim setinde 158 kez geçiyordu (sızıntı).
    Yerine rs1799853 (CYP2C9 R144C, *2 aleli; ilaç yanıtı, LitVar ~950 PMID) alındı; CYP2C9 eğitim verisinde hiç geçmiyor.
  - KCNQ1 R555C D katmanından B'ye taşındı: LitVar'da 36 PMID'li gerçek bir LQT1 varyantı, 'literatürsüz' değil.
  - KOORDINAT_TURET hedefi HARF değil PROTEİN DEĞİŞİMİ: rs6025'te GRCh37 referansı Leiden alelini taşır (T/C), harf taşımak yanlış varyant üretiyordu.
"""

EGITIM_GENLERI = {"ABL1", "AKT1", "ALK", "AR", "BRAF", "CFTR", "CTNNB1", "DNMT3A", "EGFR", "ESR1", "FGFR3", "FLT3", "GNAQ",
                  "HFE", "HRAS", "IDH1", "IDH2", "JAK2", "KIT", "KRAS", "MPL", "MYD88", "NRAS", "PDGFRA", "PIK3CA", "POLE",
                  "PTEN", "RET", "SF3B1", "TERT", "TP53"}

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

# C katmanı: b04 bu rsID'ler için GRCh38 (çıplak) ve GRCh37 ('GRCh37:' önekli) koordinat biçimi türetir (C_koordinat).
# Hedef, VEP numaralamasıyla PROTEİN DEĞİŞİMİ: b04 her sürümde alt alelleri tek tek çözer, hedefi veren aleli seçer;
# hiçbir alel vermiyorsa (GRCh37'de rs6025 referansı zaten Leiden alelidir) o sürüm için satır üretmez ve uyarı yazar.
KOORDINAT_TURET = {"rs1801133": "A222V", "rs6025": "R534Q", "rs4244285": "P227=", "rs121913671": "D1228N",
                   "rs1799853": "R144C", "rs429358": "C130R"}

# D katmanı: doğru cevap listesi yok (ya da özette anılmıyor); ölçü P@5 değil, BEKLENEN KADEME:
# sistem varyanta özgü iddia yapmamalı -> kademe 'gen' (gen düzeyi kaynak + uyarı) ya da 'yok' kabul; 'varyant' = yanlış varyant iddiası.
BEKLENEN_KADEME = {g: ("gen", "yok") for g in KATMANLAR["D_literatursuz"]}


def hepsi():
    for katman, liste in KATMANLAR.items():
        for g in liste:
            yield katman, g


def gen_kesisimi():
    """Test setindeki gen sembolleri (rsID/koordinat girdilerinin VEP çözümü dahil, b04 çıktısı varsa) eğitim setiyle kesişiyor mu?
    Boş küme beklenir. Not: gen DÜZEYİNDE bazı semboller (CDK4, MET, MAP2K1, ERBB2) eğitim özet metinlerinde anılıyor;
    kesişimsizlik VARYANT düzeyindedir, tezde 'gen düzeyinde sızıntı yok' denmemeli."""
    import json
    import os
    genler = {g.split()[0].upper() for k, g in hepsi() if not g.lower().startswith(("rs", "chr", "grch"))}
    gt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sonuclar", "dogru_cevap.jsonl")
    if os.path.exists(gt):
        for satir in open(gt, encoding="utf-8"):
            d = json.loads(satir)
            if d.get("gen"):
                genler.add(d["gen"].upper())
    return genler & EGITIM_GENLERI


if __name__ == "__main__":
    n = sum(len(v) for v in KATMANLAR.values())
    print(f"{n} girdi, {len(KATMANLAR)} katman; eğitim geniyle kesişim: {gen_kesisimi() or 'yok'}")
