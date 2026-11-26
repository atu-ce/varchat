"""
YARGIÇ, 14B HÜCRELERİ — e11'in aynı yöntemi, iki yeni modelin (qwen14-taban, varchat-14b) atıflı iddiaları için.

Aynı kalanlar (Ekim'deki e11 ile): yargıç (Claude Opus 5.5 alt ajanları), yönerge (e11.YONERGE, buradan içe aktarılır), kör paketler
(model adı ve çapa olduğu gizli, karışık sıra), birim (atıflı cümle; atıfsız cümle yargılanmaz), iddialara bölme kuralı (e05).
Böylece 2x2 tablosu kurulur: 7B / 14B x eğitimsiz (qwen-taban / qwen14-taban) / eğitimli (varchat-v2 / varchat-14b).

Tek ek, ÇAPA: Ekim'de etiketlenmiş 250 iddia (125 qwen-taban + 125 varchat-v2; Ekim kararlarının oranında, tohum 42) yeni paketlere
kör karıştırılır. Kural, sonuç görülmeden 2026-11-25'te sabitlendi: çapalarda Ekim kararı ile bugünkü karar arasında 3 sınıflı Cohen
kappa >= 0.80 ise yargıç tutarlı sayılır ve 7B hücreleri Ekim kararlarıyla kalır; değilse 2x2 hesaplanmaz, dört hücre yeniden
etiketlenmelidir (yeni dosyalara). Ekim'de birebir aynısı (girdi, cümle, atıf) etiketlenmiş iddia eski kararını alır, yeniden sorulmaz.

Etiketlenemeyen girdiler (ENGELLENEN): Opus 5.5'in güvenlik filtresi 12 girdide etiketlemeyi durdurdu; bu girdiler dört hücreden de
çıkarılır, 2x2 kalan 44 girdiyle hesaplanır. 7B hücrelerinin 56 girdilik Ekim sonuçları karşılaştırma için özete ayrıca yazılır.

Üretim hatası (e04: modelin tekrar döngüsü, cevap yok): iddiası yoktur, 'uretim_hatasi' olarak ayrıca sayılır (5 Ekim kuralı).
Duyarlılık: karşılaştırmalar, dört hücrenin hepsinde cevabı olan girdilerle bir kez daha hesaplanır.

Kullanım:
  python evaluation/e13_judge_14b.py hazirla <calisma_dizini> [paket_sayisi]   kör paketler + gizli anahtar (repo dışı)
  python evaluation/e13_judge_14b.py topla <calisma_dizini>                    etiket_<N>.json -> results/yargic_kontrol_14b.jsonl
  python evaluation/e13_judge_14b.py hazirla2 <calisma_dizini_2>              2. tur (çapa kuralı tutmadıysa): Ekim modelleri bugünkü yargıçla
  python evaluation/e13_judge_14b.py topla2 <calisma_dizini_2>                -> results/yargic_kontrol_2x2.jsonl
  python evaluation/e13_judge_14b.py ozet                                      -> results/yargic_kontrol_ozet_2x2.json
Yeni dosyalar; Ekim'in yargic_kontrol.jsonl / yargic_kontrol_ozet.json dosyalarına dokunulmaz.

2. TUR (2026-11-25: çapa kappa 0.787 < 0.80, kural tutmadı): Ekim'de etiketlenmiş modeller (qwen-taban, varchat-v2 ve yan kontrol için
qwen2.5:7b, qwen2.5:14b) ENGELLENEN dışındaki 44 girdide bugünkü yargıçla etiketlenir; bugün çapa olarak etiketlenmiş iddialar yeniden
sorulmaz. Böylece bütün modeller aynı girdilerde, aynı yargıç ve aynı günün kararlarıyla karşılaştırılır.

ATIF DUYARLILIĞI (özetteki ana ölçü, 2026-11-24'te danışmanın kararıyla 'kaynak sadakati'nin yerine): ALCE'deki 'citation recall'
(Gao vd., EMNLP 2023; tanım Liu vd., 2023'ten). Cevap başına: gösterdiği kaynaklarca desteklenen cümle / bütün cümleler (atıfsız cümle
desteklenmemiş sayılır); sonra cevapların ortalaması (ALCE'nin resmî eval.py'sindeki gibi cevap başına ortalama, havuzlanmış oran DEĞİL;
havuzlanmış hâli e06'daki 'sadakat_tum_cumleler'dir). Cümlesi olmayan cevaplar (yalnız 'bilgi yok' diyen ya da üretilemeyen) ortalamaya
girmez, sayıları ayrıca yazılır (Ahmet'in kararı, 2026-11-24). Özette 'atif_duyarliligi' anahtarıyla; ayrı bir şey olan 'duyarlilik'
anahtarı ise duyarlılık ANALİZİdir (her hücrede cevabı olan girdilerle tekrar hesap).
"""

import collections
import glob
import json
import os
import random
import sys
from datetime import date

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [BURASI, os.path.dirname(BURASI)]
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import e06_compare as e06
from e11_judge_check import KARARLAR, UCUNCU, YONERGE
import m01_main as app

SONUC = os.path.join(BURASI, "results")
SNAPSHOT = "arama_2026-10-05.jsonl"
EKIM = os.path.join(SONUC, "yargic_kontrol.jsonl")                 # Ekim'in Claude etiketleri (okunur, yazılmaz)
CIKTI = os.path.join(SONUC, "yargic_kontrol_14b.jsonl")
OZET = os.path.join(SONUC, "yargic_kontrol_ozet_2x2.json")
YENI = ["qwen14-taban", "varchat-14b"]                              # bu betikte etiketlenen modeller
EKIM_HUCRE = ["qwen-taban", "varchat-v2", "qwen2.5:14b"]            # Ekim kararlarıyla kullanılanlar (qwen2.5:14b yan kontrol)
CAPA = {"qwen-taban": 125, "varchat-v2": 125}
TOHUM = 42
ESIK = 0.80                                                          # çapa kuralı: 3 sınıflı kappa
# Opus 5.5'in güvenlik filtresi ('[bio]', biyoloji araştırmasına benzeyen içerik; 2026-11-25) 3. ve 5. paketlerde etiketlemeyi durdurdu;
# yeni bir Opus oturumu da durdu ve başka bir modele geçilmedi. Bu girdiler 2x2'nin DÖRT hücresinden de çıkarılır (Ahmet'in kararı,
# sonuçlar hesaplanmadan önce). GNAS R201C (3. paketin ilk girdisi) filtre devreye girmeden eksiksiz etiketlenmişti; içeride kalır.
ENGELLENEN = ["NOTCH1 L1601P", "ROS1 G2032R", "G6PD V68M", "rs4244285", "MET D1228N", "EZH2 Y646N",
              "SERPINA1 E342K", "GRCh37:chr10:96541616:G>A", "PAH R408W", "TTN R6318W", "rs121913671", "HBB E26K"]
ENGEL_NEDENI = "Opus 5.5 güvenlik filtresi ([bio]) etiketlemeyi durdurdu (paket 3 ve 5); dört hücreden de çıkarıldı"
HUCRE = {"7B eğitimsiz": "qwen-taban", "7B eğitimli": "varchat-v2", "14B eğitimsiz": "qwen14-taban", "14B eğitimli": "varchat-14b"}
CIFTLER = [("qwen-taban", "varchat-v2", "eğitim etkisi, 7B"), ("qwen14-taban", "varchat-14b", "eğitim etkisi, 14B"),
           ("qwen-taban", "qwen14-taban", "boy etkisi, eğitimsiz"), ("varchat-v2", "varchat-14b", "boy etkisi, eğitimli"),
           ("qwen2.5:7b", "qwen-taban", "yan kontrol: Ollama'nın hazır 7B dosyası -> kendi dosyamız"),
           ("qwen2.5:14b", "qwen14-taban", "yan kontrol: Ollama'nın hazır 14B dosyası -> kendi dosyamız")]
# 2. TUR (çapa kuralı tutmazsa): Ekim'de etiketlenmiş modeller, ENGELLENEN dışındaki girdilerde bugünkü yargıçla yeniden etiketlenir;
# bütün modeller (dört hücre + iki hazır dosya yan kontrolü) aynı girdilerde, aynı yargıç ve aynı günün etiketleriyle karşılaştırılır.
TUR2 = ["qwen-taban", "varchat-v2", "qwen2.5:7b", "qwen2.5:14b"]
CIKTI2 = os.path.join(SONUC, "yargic_kontrol_2x2.jsonl")            # her modelin her atıflı iddiası, bugünkü kararla


def kaynak_haritasi():
    return {json.loads(l)["girdi"]: json.loads(l)["makaleler"] for l in open(os.path.join(SONUC, SNAPSHOT), encoding="utf-8") if l.strip()}


def bol(cevap, n_kaynak):
    """e05'in kuralı (e05_faithfulness.py, yargılama döngüsü): cümlelere böl; ret cümlesi ve 4 kelimeden kısa cümle atılır;
    geçerli atıf numarası (1..kaynak sayısı) olmayan cümle atıfsızdır. [(cümle, (atıflar...)), ...] — sıra = e05'teki sıra."""
    out = []
    for c in app.cumlelere_bol(cevap or ""):
        if c == app.RET_CEVAP or len(c.split()) < 4:
            continue
        out.append((c, tuple(sorted({n for n in app.atif_numaralari(c) if 1 <= n <= n_kaynak}))))
    return out


def uretim_satirlari(model):
    yol = e06.son(SONUC, f"uretim_{e06.dosya_adi(model)}_*.jsonl")
    assert yol, f"{model}: üretim dosyası yok"
    satirlar = [json.loads(l) for l in open(yol, encoding="utf-8") if l.strip()]
    assert len(satirlar) == 56 and {r["snapshot"] for r in satirlar} == {SNAPSHOT}, f"{yol}: 56 satır ve {SNAPSHOT} olmalı"
    return yol, satirlar


def ekim_etiketleri():
    """(girdi, iddia, atıf) -> {karar, gerekce, modeller}; Ekim'de aynı metin bir kez etiketlendi."""
    tekil = {}
    for l in open(EKIM, encoding="utf-8"):
        r = json.loads(l)
        a = (r["girdi"], r["iddia"], tuple(r["atif"]))
        t = tekil.setdefault(a, {"karar": r["karar_claude"], "gerekce": r["gerekce_claude"], "modeller": set()})
        assert t["karar"] == r["karar_claude"], f"Ekim etiketinde aynı iddiaya iki karar: {a}"
        t["modeller"].add(r["model"])
    return tekil


def kural_kontrolu(kaynak, modeller=EKIM_HUCRE):
    """Bölme kuralı bugün de Ekim'in iddia listelerini üretiyor mu (32B sadakat dosyalarıyla, 56/56)?"""
    for m in modeller:
        uretim, sadakat, _ = e06.yukle(SONUC, m, "qwen2.5:32b")
        ayni = sum(bol(r.get("cevap"), len(kaynak[g])) == [(i["iddia"], tuple(i["atif"])) for i in (sadakat.get(g) or {}).get("iddialar", [])]
                   for g, r in uretim.items())
        print(f"bölme kuralı, {m}: {ayni}/56 girdide Ekim'in iddia listesiyle aynı")
        assert ayni == 56, "Bölme kuralı Ekim'dekinden farklı iddia üretiyor: dur, Claude'a sor"


def katmanli_sec(havuz, n, rng):
    """havuz: [(anahtar, karar)]; her karar türünden havuzdaki oranında (en büyük kalan yöntemiyle) n tane."""
    grup = collections.defaultdict(list)
    for a, k in havuz:
        grup[k].append(a)
    pay = {k: n * len(v) / len(havuz) for k, v in grup.items()}
    adet = {k: int(p) for k, p in pay.items()}
    for k in sorted(pay, key=lambda k: -(pay[k] - adet[k]))[:n - sum(adet.values())]:
        adet[k] += 1
    return [a for k in sorted(grup) for a in rng.sample(sorted(grup[k]), adet[k])]


def hazirla(dizin, paket_sayisi=9):
    repo = os.path.dirname(BURASI)
    assert os.path.commonpath([os.path.abspath(dizin), repo]) != repo, "Çalışma dizini repo DIŞINDA olmalı (gizli anahtar)"
    assert not glob.glob(os.path.join(dizin, "paket_*.json")), f"{dizin} içinde paketler zaten var; yeni bir dizin ver"
    os.makedirs(dizin, exist_ok=True)
    kaynak = kaynak_haritasi()
    kural_kontrolu(kaynak)
    ekim = ekim_etiketleri()
    yeni, ekimden = {}, {}                 # anahtar -> oluşumlar
    for m in YENI:
        yol, satirlar = uretim_satirlari(m)
        hata = [r["girdi"] for r in satirlar if not r.get("cevap")]
        n = 0
        for r in satirlar:
            for sira, (c, atif) in enumerate(bol(r.get("cevap"), len(kaynak[r["girdi"]]))):
                if not atif:
                    continue
                a = (r["girdi"], c, atif)
                (ekimden if a in ekim else yeni).setdefault(a, []).append({"model": m, "katman": r["katman"], "sira": sira})
                n += 1
        print(f"{m}: {os.path.basename(yol)} | atıflı iddia {n} | cevapsız (üretim hatası) {hata or 'yok'}")
    print(f"Ekim'de birebir aynısı etiketli (eski kararını alır): {len(ekimden)} | yeni tekil iddia: {len(yeni)}")

    rng = random.Random(TOHUM)
    capalar = {}
    for m, n in CAPA.items():
        havuz = [(a, t["karar"]) for a, t in sorted(ekim.items()) if m in t["modeller"] and a not in capalar]
        for a in katmanli_sec(havuz, n, rng):
            capalar[a] = m
    print(f"çapa: {len(capalar)} ({dict(collections.Counter(capalar.values()))}) | kararları: "
          f"{dict(collections.Counter(ekim[a]['karar'] for a in capalar))}")

    girdiye = collections.defaultdict(list)
    for a in list(yeni) + list(capalar):
        girdiye[a[0]].append(a)
    paketler = [[] for _ in range(paket_sayisi)]
    for g in sorted(girdiye, key=lambda g: (-len(girdiye[g]), g)):        # dengeli: en az iddialı pakete ekle (e11 gibi)
        min(paketler, key=lambda p: sum(len(girdiye[x]) for x in p)).append(g)
    gizli = {}
    for no, girdiler in enumerate(paketler, start=1):
        rng.shuffle(girdiler)
        icerik, k = [], 0
        for g in girdiler:
            iddialar = sorted(girdiye[g])
            rng.shuffle(iddialar)
            ogeler = []
            for a in iddialar:
                k += 1
                kimlik = f"P{no:02d}-{k:03d}"
                if a in capalar:
                    gizli[kimlik] = {"tur": "capa", "girdi": g, "iddia": a[1], "atif": list(a[2]), "capa_modeli": capalar[a],
                                     "ekim_modelleri": sorted(ekim[a]["modeller"]), "karar_ekim": ekim[a]["karar"]}
                else:
                    gizli[kimlik] = {"tur": "yeni", "girdi": g, "iddia": a[1], "atif": list(a[2]), "olusumlar": yeni[a]}
                ogeler.append({"id": kimlik, "iddia": a[1], "atif": list(a[2])})
            icerik.append({"girdi": g, "kaynaklar": {str(i): {"baslik": m["baslik"], "ozet": m["ozet"]}
                                                     for i, m in enumerate(kaynak[g], start=1)}, "iddialar": ogeler})
        json.dump({"paket": no, "yonerge": YONERGE, "girdiler": icerik}, open(os.path.join(dizin, f"paket_{no}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"paket_{no}: {len(girdiler)} girdi, {k} iddia")
    json.dump({"tarih": date.today().isoformat(), "snapshot": SNAPSHOT, "esik_kappa_3_sinif": ESIK, "capa": CAPA, "tohum": TOHUM,
               "iddialar": gizli,
               "ekimden": [{"girdi": a[0], "iddia": a[1], "atif": list(a[2]), "karar": ekim[a]["karar"], "gerekce": ekim[a]["gerekce"],
                            "ekim_modelleri": sorted(ekim[a]["modeller"]), "olusumlar": o} for a, o in ekimden.items()]},
              open(os.path.join(dizin, "anahtar.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(gizli)} iddia ({len(yeni)} yeni + {len(capalar)} çapa) {paket_sayisi} pakette -> {dizin}")


def etiketleri_oku(dizin, gizli, engel=frozenset()):
    """etiket_<N>.json dosyaları: her dosya paket_<N>.json'daki kimlikleri (engel hariç) birebir, birer kez içermeli; karar geçerli olmalı;
    sonunda gizli anahtardaki her kimlik (engel hariç) etiketli olmalı. kimlik -> etiket."""
    etiket = {}
    for yol in sorted(glob.glob(os.path.join(dizin, "etiket_*.json"))):
        no = int(os.path.basename(yol)[len("etiket_"):-len(".json")])
        dosya = json.load(open(yol, encoding="utf-8"))
        bekl = {i["id"] for g in json.load(open(os.path.join(dizin, f"paket_{no}.json"), encoding="utf-8"))["girdiler"]
                for i in g["iddialar"]} - set(engel)
        kimlikler = [e["id"] for e in dosya["etiketler"]]
        if dosya.get("paket") != no or len(kimlikler) != len(set(kimlikler)) or set(kimlikler) != bekl:
            raise SystemExit(f"{yol}: paket_{no}.json'daki kimliklerle birebir örtüşmüyor (eksik {len(bekl - set(kimlikler))}, "
                             f"fazla {len(set(kimlikler) - bekl)}, tekrar {len(kimlikler) - len(set(kimlikler))})")
        for e in dosya["etiketler"]:
            if e["id"] not in gizli:
                raise SystemExit(f"{yol}: bilinmeyen kimlik {e['id']}")
            if e["karar"] not in KARARLAR:
                raise SystemExit(f"{yol}: geçersiz karar {e['karar']} ({e['id']})")
            if e["id"] in etiket:
                raise SystemExit(f"{yol}: {e['id']} iki kez etiketlenmiş")
            etiket[e["id"]] = e
    eksik = sorted(set(gizli) - set(etiket) - set(engel))
    if eksik:
        raise SystemExit(f"{len(eksik)} iddianın etiketi yok: {eksik[:10]}")
    return etiket


def bugunku_etiketler_tur1():
    """1. turun BUGÜNKÜ kararları: (girdi, iddia, atıf) -> (karar, gerekce, kaynak). Ekim'den alınan karar ('ekim') sayılmaz."""
    d = {}
    for l in open(CIKTI, encoding="utf-8"):
        r = json.loads(l)
        if r.get("kaynak_etiket") == "ekim":
            continue
        a = (r["girdi"], r["iddia"], tuple(r["atif"]))
        v = (r["karar_claude"], r["gerekce_claude"], "capa" if r["capa"] else "tur1")
        assert d.setdefault(a, v)[0] == v[0], f"1. turda aynı iddiaya iki karar: {a}"
    return d


def atifli_iddialar(modeller, kaynak):
    """(girdi, iddia, atıf) -> [oluşum]: ENGELLENEN dışındaki girdilerde, cevabı olan satırların atıflı iddiaları (e05 kuralı)."""
    out = collections.defaultdict(list)
    for m in modeller:
        _, satirlar = uretim_satirlari(m)
        for r in satirlar:
            if r["girdi"] in ENGELLENEN or not r.get("cevap"):
                continue
            for sira, (c, atif) in enumerate(bol(r["cevap"], len(kaynak[r["girdi"]]))):
                if atif:
                    out[(r["girdi"], c, atif)].append({"model": m, "katman": r["katman"], "sira": sira})
    return out


def hazirla2(dizin, iddia_basina=100):
    """2. tur: TUR2 modellerinin (ve 14B'nin) bugün henüz etiketlenmemiş atıflı iddiaları, aynı kör paket biçiminde."""
    repo = os.path.dirname(BURASI)
    assert os.path.commonpath([os.path.abspath(dizin), repo]) != repo, "Çalışma dizini repo DIŞINDA olmalı (gizli anahtar)"
    assert not glob.glob(os.path.join(dizin, "paket_*.json")), f"{dizin} içinde paketler zaten var; yeni bir dizin ver"
    assert not capa_uyumu([json.loads(l) for l in open(CIKTI, encoding="utf-8")])["gecti"], "Çapa kuralı tuttu: 2. tura gerek yok"
    os.makedirs(dizin, exist_ok=True)
    kaynak = kaynak_haritasi()
    kural_kontrolu(kaynak, TUR2)
    bugun = bugunku_etiketler_tur1()
    hepsi = atifli_iddialar(TUR2 + YENI, kaynak)
    gerek = sorted(a for a in hepsi if a not in bugun)
    for m in TUR2 + YENI:
        print(f"{m}: {sum(any(o['model'] == m for o in v) for v in hepsi.values())} tekil atıflı iddia "
              f"({len(kaynak) - len(ENGELLENEN)} girdi) | bugün henüz etiketlenmemiş: {sum(any(o['model'] == m for o in hepsi[a]) for a in gerek)}")
    girdiye = collections.defaultdict(list)
    for a in gerek:
        girdiye[a[0]].append(a)
    paket_sayisi = max(1, round(len(gerek) / iddia_basina))
    paketler = [[] for _ in range(paket_sayisi)]
    for g in sorted(girdiye, key=lambda g: (-len(girdiye[g]), g)):
        min(paketler, key=lambda p: sum(len(girdiye[x]) for x in p)).append(g)
    rng = random.Random(TOHUM)
    gizli = {}
    for no, girdiler in enumerate(paketler, start=1):
        rng.shuffle(girdiler)
        icerik, k = [], 0
        for g in girdiler:
            iddialar = sorted(girdiye[g])
            rng.shuffle(iddialar)
            ogeler = []
            for a in iddialar:
                k += 1
                kimlik = f"R{no:02d}-{k:03d}"
                gizli[kimlik] = {"girdi": g, "iddia": a[1], "atif": list(a[2]), "olusumlar": hepsi[a]}
                ogeler.append({"id": kimlik, "iddia": a[1], "atif": list(a[2])})
            icerik.append({"girdi": g, "kaynaklar": {str(i): {"baslik": m["baslik"], "ozet": m["ozet"]}
                                                     for i, m in enumerate(kaynak[g], start=1)}, "iddialar": ogeler})
        json.dump({"paket": no, "yonerge": YONERGE, "girdiler": icerik}, open(os.path.join(dizin, f"paket_{no}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"paket_{no}: {len(girdiler)} girdi, {k} iddia")
    json.dump({"tarih": date.today().isoformat(), "snapshot": SNAPSHOT, "tur": 2, "iddialar": gizli},
              open(os.path.join(dizin, "anahtar.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(gizli)} iddia {paket_sayisi} pakette -> {dizin}")


def topla2(dizin):
    """2. turun etiketleri + 1. turun bugünkü kararları -> results/yargic_kontrol_2x2.jsonl (her modelin her atıflı iddiası)."""
    anahtar = json.load(open(os.path.join(dizin, "anahtar.json"), encoding="utf-8"))
    gizli = anahtar["iddialar"]
    etiket = etiketleri_oku(dizin, gizli)
    bugun = bugunku_etiketler_tur1()
    for kimlik, b in gizli.items():
        a = (b["girdi"], b["iddia"], tuple(b["atif"]))
        assert a not in bugun, f"{kimlik}: 1. turda zaten etiketli"
        bugun[a] = (etiket[kimlik]["karar"], etiket[kimlik].get("gerekce", ""), "tur2")
    hepsi = atifli_iddialar(TUR2 + YENI, kaynak_haritasi())
    eksik = [a for a in hepsi if a not in bugun]
    assert not eksik, f"{len(eksik)} iddianın bugünkü kararı yok"
    satirlar = []
    for a, olusumlar in hepsi.items():
        karar, gerekce, kaynak = bugun[a]
        for o in olusumlar:
            satirlar.append({"model": o["model"], "girdi": a[0], "katman": o["katman"], "sira": o["sira"], "iddia": a[1], "atif": list(a[2]),
                             "karar_claude": karar, "gerekce_claude": gerekce, "etiket_turu": kaynak, "tarih": anahtar["tarih"]})
    satirlar.sort(key=lambda r: ((TUR2 + YENI).index(r["model"]), r["girdi"], r["sira"]))
    with open(CIKTI2, "w", encoding="utf-8", newline="\n") as f:
        for r in satirlar:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(etiket)} yeni etiket (2. tur) | {len(satirlar)} satır, {len({(r['girdi'], r['iddia'], tuple(r['atif'])) for r in satirlar})} tekil iddia, "
          f"{len(TUR2 + YENI)} model -> {CIKTI2}")
    print("etiket türleri:", dict(collections.Counter(r["etiket_turu"] for r in satirlar)))


def topla(dizin):
    anahtar = json.load(open(os.path.join(dizin, "anahtar.json"), encoding="utf-8"))
    gizli = anahtar["iddialar"]
    engel = {k for k, b in gizli.items() if b["girdi"] in ENGELLENEN}       # etiketlenemeyen girdilerin iddiaları (etiket beklenmez)
    assert {b["girdi"] for b in gizli.values()} >= set(ENGELLENEN), "ENGELLENEN listesinde paketlerde olmayan girdi var"
    etiket = etiketleri_oku(dizin, gizli, engel)
    print(f"etiketlenemeyen (ENGELLENEN, {len(ENGELLENEN)} girdi): {len(engel)} iddia "
          f"({sum(gizli[k]['tur'] == 'capa' for k in engel)} çapa) — 2x2'nin dört hücresinden de çıkarılır")
    satirlar = []
    for kimlik, b in gizli.items():
        if kimlik in engel:
            continue
        ortak = {"girdi": b["girdi"], "iddia": b["iddia"], "atif": b["atif"], "karar_claude": etiket[kimlik]["karar"],
                 "gerekce_claude": etiket[kimlik].get("gerekce", ""), "kimlik": kimlik, "tarih": anahtar["tarih"]}
        if b["tur"] == "capa":
            satirlar.append({"capa": True, "model": b["capa_modeli"], "ekim_modelleri": b["ekim_modelleri"], "karar_ekim": b["karar_ekim"], **ortak})
        else:
            for o in b["olusumlar"]:
                satirlar.append({"capa": False, "model": o["model"], "katman": o["katman"], "sira": o["sira"], "kaynak_etiket": "yeni", **ortak})
    for b in anahtar["ekimden"]:
        for o in b["olusumlar"]:
            satirlar.append({"capa": False, "model": o["model"], "katman": o["katman"], "sira": o["sira"], "kaynak_etiket": "ekim",
                             "girdi": b["girdi"], "iddia": b["iddia"], "atif": b["atif"], "karar_claude": b["karar"],
                             "gerekce_claude": b["gerekce"], "ekim_modelleri": b["ekim_modelleri"], "tarih": "2026-10-17"})
    satirlar.sort(key=lambda r: (r["capa"], r["model"], r["girdi"], r.get("sira", 0), r["iddia"]))
    with open(CIKTI, "w", encoding="utf-8", newline="\n") as f:
        for r in satirlar:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(etiket)} etiket, {len(satirlar)} satır ({sum(r['capa'] for r in satirlar)} çapa) -> {CIKTI}")


def capa_uyumu(satirlar):
    def ciftler_(m=None):
        return [(r["karar_ekim"], r["karar_claude"]) for r in satirlar if r["capa"] and (m is None or r["model"] == m)]
    ciftler = ciftler_()
    ikili = [(a == "DESTEKLENIYOR", b == "DESTEKLENIYOR") for a, b in ciftler]
    k3 = e06.kappa(ciftler)
    model_bazinda = {}
    for m in CAPA:
        c = ciftler_(m)
        model_bazinda[m] = {"iddia": len(c), "ayni_karar": round(sum(a == b for a, b in c) / len(c), 3), "kappa_3_sinif": e06.kappa(c)}
    return {"planlanan": sum(CAPA.values()), "iddia": len(ciftler), "ayni_karar": round(sum(a == b for a, b in ciftler) / len(ciftler), 3),
            "kappa_3_sinif": k3, "kappa_destek_mi": e06.kappa(ikili), "esik_kappa_3_sinif": ESIK, "gecti": k3 >= ESIK,
            "karisiklik_ekim_x_bugun": {f"{a} / {b}": c for (a, b), c in sorted(collections.Counter(ciftler).items())},
            "model_bazinda": model_bazinda}


def olculer(satirlar, dislanan, modeller=None):
    """Her hücre için girdi -> e06.girdi_olculeri ('dislanan' girdiler hariç). 7B hücreleri ve yan kontrol: Ekim kararları
    (e11.ozet ile aynı yol); 14B hücreleri: cevap e05 kuralıyla yeniden bölünür, atıflı iddia bu betiğin etiketini alır."""
    modeller = modeller or EKIM_HUCRE + YENI
    kaynak = kaynak_haritasi()
    olcu = {}
    ekim = {}
    for l in open(EKIM, encoding="utf-8"):
        r = json.loads(l)
        ekim[(r["model"], r["girdi"], r["sira"])] = r["karar_claude"]
    for m in [x for x in modeller if x not in YENI]:                  # Ekim'de etiketlenmiş modeller
        uretim, sadakat, _ = e06.yukle(SONUC, m, "qwen2.5:32b")
        for g, h in sadakat.items():
            for sira, i in enumerate(h["iddialar"]):
                if i["karar"] != "ATIFSIZ":
                    i["karar"] = ekim[(m, g, sira)]
        olcu[m] = {g: e06.girdi_olculeri(uretim[g], sadakat.get(g)) for g in uretim if g not in dislanan}
    yeni = {(r["model"], r["girdi"], r["sira"]): r for r in satirlar if not r["capa"]}
    for m in [x for x in YENI if x in modeller]:
        _, uretim = uretim_satirlari(m)
        olcu[m] = {}
        for r in uretim:
            if r["girdi"] in dislanan:
                continue
            h = None
            if r.get("cevap"):
                iddialar = []
                for sira, (c, atif) in enumerate(bol(r["cevap"], len(kaynak[r["girdi"]]))):
                    if not atif:
                        iddialar.append({"iddia": c, "atif": [], "karar": "ATIFSIZ"})
                        continue
                    e = yeni.get((m, r["girdi"], sira))
                    assert e and e["iddia"] == c and tuple(e["atif"]) == atif, f"{m} {r['girdi']} #{sira}: etiket yok ya da cümle farklı"
                    iddialar.append({"iddia": c, "atif": list(atif), "karar": e["karar_claude"]})
                h = {"iddialar": iddialar}
            olcu[m][r["girdi"]] = e06.girdi_olculeri(r, h)
    return olcu


def olculer_bugun(modeller, dislanan):
    """2. tur: her model için girdi -> e06.girdi_olculeri; cevap e05 kuralıyla bölünür, her atıflı iddia yargic_kontrol_2x2.jsonl'deki
    bugünkü kararı alır (aynı metin bir kez etiketlendi)."""
    etiketler = {}
    for l in open(CIKTI2, encoding="utf-8"):
        r = json.loads(l)
        a = (r["girdi"], r["iddia"], tuple(r["atif"]))
        assert etiketler.setdefault(a, r["karar_claude"]) == r["karar_claude"], f"aynı iddiaya iki karar: {a}"
    kaynak = kaynak_haritasi()
    olcu = {}
    for m in modeller:
        _, uretim = uretim_satirlari(m)
        olcu[m] = {}
        for r in uretim:
            if r["girdi"] in dislanan:
                continue
            h = None
            if r.get("cevap"):
                iddialar = []
                for c, atif in bol(r["cevap"], len(kaynak[r["girdi"]])):
                    if not atif:
                        iddialar.append({"iddia": c, "atif": [], "karar": "ATIFSIZ"})
                        continue
                    assert (r["girdi"], c, atif) in etiketler, f"{m} {r['girdi']}: bugünkü kararı olmayan iddia"
                    iddialar.append({"iddia": c, "atif": list(atif), "karar": etiketler[(r["girdi"], c, atif)]})
                h = {"iddialar": iddialar}
            olcu[m][r["girdi"]] = e06.girdi_olculeri(r, h)
    return olcu


def etkilesim(olcu, girdiler, tekrar=10000, tohum=TOHUM):
    """(14B eğitim etkisi) - (7B eğitim etkisi). Dört hücre aynı girdilerde; bootstrap'ta aynı girdi (ya da aynı varyant kümesi)
    dört hücreye birlikte girer (e06.bootstrap_fark'ın dört hücreli hâli). Her oran: toplam pay / toplam payda."""
    L = {k: [olcu[m][g] for g in girdiler] for k, m in HUCRE.items()}
    grup = collections.defaultdict(list)
    for i, k in enumerate(e06.kume_anahtarlari(girdiler)):
        grup[k].append(i)
    gruplar = list(grup.values())

    def oran(liste, pay, payda):
        y = sum(o[payda] for o in liste)
        return sum(o[pay] for o in liste) / y if y else 0.0
    sonuc = {}
    for ad, (pay, payda) in e06.ORANLAR.items():
        def etkiler(idx):
            s = {k: oran([L[k][i] for i in idx], pay, payda) for k in L}
            return s["7B eğitimli"] - s["7B eğitimsiz"], s["14B eğitimli"] - s["14B eğitimsiz"]
        e7, e14 = etkiler(range(len(girdiler)))
        ga = {}
        for tur in ("girdi", "kume"):
            rng = random.Random(tohum)
            farklar = []
            for _ in range(tekrar):
                if tur == "kume":
                    idx = [i for _ in range(len(gruplar)) for i in gruplar[rng.randrange(len(gruplar))]]
                else:
                    idx = [rng.randrange(len(girdiler)) for _ in girdiler]
                a, b = etkiler(idx)
                farklar.append(b - a)
            farklar.sort()
            ga[tur] = [round(farklar[int(0.025 * tekrar)], 3), round(farklar[int(0.975 * tekrar)], 3)]
        sonuc[ad] = {"egitim_etkisi_7b": round(e7, 3), "egitim_etkisi_14b": round(e14, 3), "etkilesim_14b_eksi_7b": round(e14 - e7, 3),
                     "guven_95": ga["girdi"], "guven_95_kume": ga["kume"]}
    return {"girdi": len(girdiler), "kume_sayisi": len(gruplar), "oranlar": sonuc}


def atif_duyarliligi_degeri(olculer):
    """ALCE citation recall, cevap başına ortalama: her cevapta desteklenen / bütün cümleler, sonra ortalama. Cümlesi olmayan cevap
    (yalnız ret ya da üretim hatası) dışarıda. (değer ya da None, ortalamaya giren cevap sayısı)"""
    v = [o["destek"] / o["cumle"] for o in olculer if o["cumle"] > 0]
    return (sum(v) / len(v) if v else None), len(v)


def atif_duyarliligi(olcu, girdiler, tekrar=10000, tohum=TOHUM):
    """Her model için atıf duyarlılığı + CIFTLER farkları + etkileşim, varyant kümesi bootstrap'ıyla %95 GA (e06.kume_anahtarlari;
    her tekrarda bütün modeller aynı kümelerle, e13.etkilesim ile aynı düzen)."""
    grup = collections.defaultdict(list)
    for i, k in enumerate(e06.kume_anahtarlari(girdiler)):
        grup[k].append(i)
    gruplar = list(grup.values())
    modeller = list(olcu)
    deger = lambda m, idx: atif_duyarliligi_degeri([olcu[m][girdiler[i]] for i in idx])[0]
    ciftler = [(a, b, ad) for a, b, ad in CIFTLER if a in olcu and b in olcu]
    hucre_var = all(m in olcu for m in HUCRE.values())

    def hepsi(idx):
        s = {m: deger(m, idx) for m in modeller}
        f = {ad: s[b] - s[a] for a, b, ad in ciftler}
        if hucre_var:
            f["etkileşim"] = (s[HUCRE["14B eğitimli"]] - s[HUCRE["14B eğitimsiz"]]) - (s[HUCRE["7B eğitimli"]] - s[HUCRE["7B eğitimsiz"]])
        return s, f

    s0, f0 = hepsi(range(len(girdiler)))
    rng = random.Random(tohum)
    orn = collections.defaultdict(list)
    for _ in range(tekrar):
        idx = [i for _ in range(len(gruplar)) for i in gruplar[rng.randrange(len(gruplar))]]
        s, f = hepsi(idx)
        for k, v in {**s, **f}.items():
            orn[k].append(v)
    ga = lambda k: [round(sorted(orn[k])[int(0.025 * tekrar)], 3), round(sorted(orn[k])[int(0.975 * tekrar)], 3)]
    sonuc = {"tanim": "ALCE citation recall: cevap başına desteklenen / bütün cümleler, cevapların ortalaması; cümlesi olmayan cevap dışarıda",
             "girdi": len(girdiler), "kume_sayisi": len(gruplar), "modeller": {}, "farklar": []}
    for m in modeller:
        o = [olcu[m][g] for g in girdiler]
        sonuc["modeller"][m] = {"deger": round(s0[m], 3), "guven_95_kume": ga(m), "dahil_cevap": atif_duyarliligi_degeri(o)[1],
                                "disarida_yalniz_ret": sum(x["cumle"] == 0 and x["ret"] for x in o),
                                "disarida_uretim_hatasi": sum(x["cumle"] == 0 and x["hata"] for x in o)}
    for a, b, ad in ciftler:
        sonuc["farklar"].append({"ad": ad, "a": a, "b": b, "fark_b_eksi_a": round(f0[ad], 3), "guven_95_kume": ga(ad)})
    if hucre_var:
        sonuc["etkilesim"] = {"egitim_etkisi_7b": round(f0["eğitim etkisi, 7B"], 3), "egitim_etkisi_14b": round(f0["eğitim etkisi, 14B"], 3),
                              "etkilesim_14b_eksi_7b": round(f0["etkileşim"], 3), "guven_95_kume": ga("etkileşim")}
    return sonuc


def karsilastir(olcu, girdiler, baslik):
    print(f"\n===== {baslik}: {len(girdiler)} girdi =====")
    ciftler = []
    for a, b, ad in [c for c in CIFTLER if c[0] in olcu and c[1] in olcu]:
        e = e06.eslestir(olcu, girdiler, a, b)
        ciftler.append({"ad": ad, **e})
    et = etkilesim(olcu, girdiler)
    for ad, o in et["oranlar"].items():
        print(f"ETKİLEŞİM {ad:22} 7B etkisi {o['egitim_etkisi_7b']:+.3f} | 14B etkisi {o['egitim_etkisi_14b']:+.3f} | fark "
              f"{o['etkilesim_14b_eksi_7b']:+.3f} GA küme {o['guven_95_kume'][0]:+.3f} .. {o['guven_95_kume'][1]:+.3f}")
    ad_ = atif_duyarliligi(olcu, girdiler)
    for m, o in ad_["modeller"].items():
        print(f"ATIF DUYARLILIĞI {m:13} {o['deger']:.3f} GA küme {o['guven_95_kume'][0]:.3f} .. {o['guven_95_kume'][1]:.3f} "
              f"(dahil {o['dahil_cevap']}, yalnız ret {o['disarida_yalniz_ret']}, üretim hatası {o['disarida_uretim_hatasi']})")
    for f in ad_["farklar"] + ([{"ad": "etkileşim (14B - 7B)", "fark_b_eksi_a": ad_["etkilesim"]["etkilesim_14b_eksi_7b"],
                                  "guven_95_kume": ad_["etkilesim"]["guven_95_kume"]}] if "etkilesim" in ad_ else []):
        print(f"ATIF DUYARLILIĞI {f['ad']:55} {f['fark_b_eksi_a']:+.3f} GA küme {f['guven_95_kume'][0]:+.3f} .. {f['guven_95_kume'][1]:+.3f}")
    return {"girdi": len(girdiler), "eslestirilmis": ciftler, "etkilesim": et, "atif_duyarliligi": ad_}


def ozet():
    satirlar = [json.loads(l) for l in open(CIKTI, encoding="utf-8")]
    capa = capa_uyumu(satirlar)
    print(f"ÇAPA: {capa['iddia']} iddia | aynı karar {capa['ayni_karar']} | kappa(3) {capa['kappa_3_sinif']} | "
          f"kappa(destek mi) {capa['kappa_destek_mi']} | eşik {ESIK} -> {'GEÇTİ' if capa['gecti'] else 'GEÇMEDİ'}")
    sonuc = {"etiket_tarihi": sorted({r["tarih"] for r in satirlar if r.get("kaynak_etiket") != "ekim"}), "hesap_tarihi": date.today().isoformat(),
             "ucuncu_yargic": UCUNCU, "kaynak": os.path.basename(CIKTI), "capa": capa}
    if not capa["gecti"]:
        if not os.path.exists(CIKTI2):
            sonuc["kural"] = "çapa uyumu eşiğin altında: Ekim etiketleriyle birleştirilmez, dört hücre yeniden etiketlenmeli (yeni dosyalara)"
            json.dump(sonuc, open(OZET, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
            print(f"\n{sonuc['kural']}\n-> {OZET}")
            return
        sonuc["kural"] = ("çapa uyumu eşiğin altında: Ekim etiketleri kullanılmadı; bütün modeller ENGELLENEN dışındaki girdilerde "
                          "bugünkü yargıçla (2. tur)")
        sonuc["kaynak"] = [os.path.basename(CIKTI), os.path.basename(CIKTI2)]
        modeller = TUR2 + YENI
        olcu = olculer_bugun(modeller, set(ENGELLENEN))
    else:
        sonuc["kural"] = "çapa uyumu eşiğin üstünde: 7B hücreleri ve yan kontrol Ekim kararlarıyla, 14B hücreleri bu etiketlerle"
        modeller = EKIM_HUCRE + YENI
        olcu = olculer(satirlar, set(ENGELLENEN))
    sonuc["engellenen"] = {"girdiler": ENGELLENEN, "neden": ENGEL_NEDENI}
    # Karşılaştırma için: Ekim yargısıyla (e11 kararları) Ekim modelleri, bütün girdilerde ve aynı dışlamayla
    sonuc["ekim_yargisi"] = {f"{n}_girdi": {m: e06.ozetle(list(o[m].values())) for m in o}
                             for n, o in ((56, olculer(satirlar, set(), TUR2)), (56 - len(ENGELLENEN), olculer(satirlar, set(ENGELLENEN), TUR2)))}
    sonuc["tablo"] = {}
    print(f"\nSADAKAT ({UCUNCU} yargıçla)")
    for m in modeller:
        katmanlar = sorted({o["katman"] for o in olcu[m].values()})
        sonuc["tablo"][m] = {k: e06.ozetle([o for o in olcu[m].values() if o["katman"] == k]) for k in katmanlar}
        t = sonuc["tablo"][m]["TÜMÜ"] = e06.ozetle(list(olcu[m].values()))
        print(f"  {m:13} sadakat={t['sadakat']} çelişki={t['celiski_orani']} iddia={t['iddia']} desteklenen={t['desteklenen']} "
              f"atıfsız={t['atifsiz_orani']} ret={t['yalniz_ret']} dil çöküşü={t['dil_cokusu']} üretim hatası={t['uretim_hatasi']}")
    sonuc["hucreler"] = HUCRE
    girdiler = sorted(set.intersection(*(set(o) for o in olcu.values())))
    sonuc["ana"] = karsilastir(olcu, girdiler, "ANA (bütün girdiler; cevapsız satır üretim hatası olarak)")
    tam = [g for g in girdiler if not any(olcu[m][g]["hata"] for m in olcu)]
    sonuc["duyarlilik"] = {"aciklama": "yalnız her hücrede cevabı olan girdiler", "cikarilan": sorted(set(girdiler) - set(tam)),
                           **karsilastir(olcu, tam, "DUYARLILIK (her hücrede cevabı olan girdiler)")}
    json.dump(sonuc, open(OZET, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(f"\n-> {OZET}")


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "hazirla":
        hazirla(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 9)
    elif komut == "topla":
        topla(sys.argv[2])
    elif komut == "hazirla2":
        hazirla2(sys.argv[2])
    elif komut == "topla2":
        topla2(sys.argv[2])
    elif komut == "ozet":
        ozet()
    else:
        print(__doc__)
