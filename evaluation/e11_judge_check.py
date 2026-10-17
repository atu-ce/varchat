"""
YARGIÇ KONTROLÜ — e05'in yargıçlarını (qwen2.5:7b, qwen2.5:32b) daha güçlü bir üçüncü yargıçla karşılaştırır.

Üçüncü yargıç: Claude (Opus 5.5) alt ajanları, 17 Ekim 2026. İnsan etiketi DEĞİLDİR; tezde "daha güçlü model yargıcıyla doğrulama"
diye raporlanır. Bilinen yanlılık riski: varchat'in eğitim örneklerini de Claude yazdı. Azaltmak için değerlendirme KÖRDÜR:
iddialar hangi modelden geldiği ve 7B/32B kararları gizlenerek, karışık sırayla verilir; aynı metin bir kez etiketlenir.

Birim ve tanımlar e05 ile aynı: her atıflı cümle, YALNIZCA atıf verdiği kaynak(lar)ın başlık+özetine karşı
DESTEKLENIYOR / DESTEKLENMIYOR / CELISIYOR. Atıfsız cümleler yargılanmaz (ATIFSIZ, e05'teki gibi).

Kullanım:
  python evaluation/e11_judge_check.py hazirla <calisma_dizini> [paket_sayisi]   kör paketler + gizli anahtar (repo dışı)
  python evaluation/e11_judge_check.py topla <calisma_dizini>                    etiket_<N>.json -> results/yargic_kontrol.jsonl
  python evaluation/e11_judge_check.py ozet                                      -> results/yargic_kontrol_ozet.json
Çıktı (tek dosya + özet): her satır bir model cevabındaki bir iddia: model, girdi, katman, iddia, atif,
  karar_7b (ham 14B için yok), karar_32b, karar_claude, gerekce_claude.
"""

import collections
import glob
import json
import os
import random
import sys
from datetime import date

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import e06_compare as e06

SONUC = os.path.join(BURASI, "results")
GIRDI = os.path.join(BURASI, "results")
CIKTI = os.path.join(SONUC, "yargic_kontrol.jsonl")
OZET = os.path.join(SONUC, "yargic_kontrol_ozet.json")
MODELLER = ["qwen2.5:7b", "qwen-taban", "varchat", "varchat-v2", "qwen2.5:14b"]
KARARLAR = ("DESTEKLENIYOR", "DESTEKLENMIYOR", "CELISIYOR")
UCUNCU = "claude-opus-5.5"
CIFTLER = [("qwen-taban", "varchat-v2"), ("varchat", "varchat-v2"), ("varchat-v2", "qwen2.5:14b"), ("qwen2.5:7b", "qwen-taban")]

YONERGE = """Sen titiz bir bilimsel yargıçsın. Her İDDİA, bir genetik varyant asistanının Türkçe cevabından alınmış tek bir cümledir;
sonundaki [n] numaraları dayandığını söylediği kaynaklardır. Görevin: iddianın YALNIZCA atıf verdiği kaynak(lar)ın başlık ve
özetine dayanıp dayanmadığını söylemek. Kendi bilgini kullanma; atıf verilmeyen kaynaklara bakma.
- DESTEKLENIYOR: iddiadaki bilgi atıf verilen kaynakta açıkça var (çeviri/ifade farkı sorun değil).
- DESTEKLENMIYOR: iddia kaynakta yok ya da kaynaktan çıkarılamıyor.
- CELISIYOR: kaynak iddianın tersini söylüyor (örn. 'riski artırır' vs 'azaltır', 'neden olur' vs 'korur').
Netleştirmeler (iki yargıcın tutarsız davrandığı durumlar):
- İddia birden çok bilgi içeriyorsa HEPSİ kaynakta olmalı; biri eksikse ya da abartılmışsa (ilişkili -> neden olur, fare -> insan,
  tek çalışma -> genellikle, niteleyici düşmüş) DESTEKLENMIYOR.
- Kaynakta açıkça verilen bir bulgu için iddia farklı bir rakam, yön, popülasyon, gen/alel ya da hastalık veriyorsa CELISIYOR.
- Türkçesi anlamı çözülemeyecek kadar bozuk iddia DESTEKLENMIYOR.
Her iddia için: {"id": "...", "karar": "DESTEKLENIYOR|DESTEKLENMIYOR|CELISIYOR", "gerekce": "<bir cümle>"}"""


def kaynak_haritasi(snapshot):
    yol = os.path.join(GIRDI, snapshot)
    return {json.loads(l)["girdi"]: json.loads(l)["makaleler"] for l in open(yol, encoding="utf-8") if l.strip()}


def yuklenmis(model, yargic):
    dosya = e06.sadakat_dosyasi(SONUC, e06.dosya_adi(model), yargic)
    return {json.loads(l)["girdi"]: json.loads(l) for l in open(dosya, encoding="utf-8")} if dosya else {}


def hazirla(dizin, paket_sayisi=14):
    os.makedirs(dizin, exist_ok=True)
    tekil = {}                        # (girdi, iddia, atif) -> oluşumlar
    snapshot = None
    for m in MODELLER:
        s32, s7 = yuklenmis(m, "qwen2.5:32b"), yuklenmis(m, None)
        for g, h in s32.items():
            snapshot = snapshot or h["snapshot"]
            h7 = {(i["iddia"], tuple(i["atif"])): i for i in (s7.get(g) or {}).get("iddialar", [])}
            for sira, i in enumerate(h["iddialar"]):
                if i["karar"] == "ATIFSIZ":
                    continue
                anahtar = (g, i["iddia"], tuple(i["atif"]))
                tekil.setdefault(anahtar, []).append({"model": m, "katman": h["katman"], "sira": sira, "karar_32b": i["karar"],
                                                      "karar_7b": (h7.get((i["iddia"], tuple(i["atif"]))) or {}).get("karar")})
    kaynak = kaynak_haritasi(snapshot)
    girdiye = collections.defaultdict(list)
    for anahtar in tekil:
        girdiye[anahtar[0]].append(anahtar)
    paketler = [[] for _ in range(paket_sayisi)]
    for g in sorted(girdiye, key=lambda g: -len(girdiye[g])):          # dengeli: en az iddialı pakete ekle
        min(paketler, key=lambda p: sum(len(girdiye[x]) for x in p)).append(g)
    rng = random.Random(42)
    gizli = {}
    for n, girdiler in enumerate(paketler, start=1):
        rng.shuffle(girdiler)
        icerik = []
        k = 0
        for g in girdiler:
            iddialar = list(girdiye[g])
            rng.shuffle(iddialar)
            ogeler = []
            for anahtar in iddialar:
                k += 1
                kimlik = f"P{n:02d}-{k:03d}"
                gizli[kimlik] = {"girdi": g, "iddia": anahtar[1], "atif": list(anahtar[2]), "olusumlar": tekil[anahtar]}
                ogeler.append({"id": kimlik, "iddia": anahtar[1], "atif": list(anahtar[2])})
            icerik.append({"girdi": g, "kaynaklar": {str(i): {"baslik": a["baslik"], "ozet": a["ozet"]}
                                                     for i, a in enumerate(kaynak[g], start=1)}, "iddialar": ogeler})
        json.dump({"paket": n, "yonerge": YONERGE, "girdiler": icerik}, open(os.path.join(dizin, f"paket_{n}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"paket_{n}: {len(girdiler)} girdi, {k} iddia")
    json.dump({"snapshot": snapshot, "iddialar": gizli}, open(os.path.join(dizin, "anahtar.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(tekil)} tekil iddia ({sum(len(v) for v in tekil.values())} oluşum, {len(MODELLER)} model) -> {dizin}")


def topla(dizin):
    gizli = json.load(open(os.path.join(dizin, "anahtar.json"), encoding="utf-8"))["iddialar"]
    etiket = {}
    for yol in sorted(glob.glob(os.path.join(dizin, "etiket_*.json"))):
        for e in json.load(open(yol, encoding="utf-8"))["etiketler"]:
            if e["karar"] not in KARARLAR:
                raise SystemExit(f"{yol}: geçersiz karar {e['karar']} ({e['id']})")
            etiket[e["id"]] = e
    eksik = sorted(set(gizli) - set(etiket))
    if eksik:
        raise SystemExit(f"{len(eksik)} iddianın etiketi yok: {eksik[:10]}")
    satirlar = []
    for kimlik, b in gizli.items():
        for o in b["olusumlar"]:
            satirlar.append({"model": o["model"], "girdi": b["girdi"], "katman": o["katman"], "sira": o["sira"], "iddia": b["iddia"],
                             "atif": b["atif"], "karar_7b": o["karar_7b"], "karar_32b": o["karar_32b"],
                             "karar_claude": etiket[kimlik]["karar"], "gerekce_claude": etiket[kimlik].get("gerekce", "")})
    satirlar.sort(key=lambda r: (MODELLER.index(r["model"]), r["girdi"], r["sira"]))
    with open(CIKTI, "w", encoding="utf-8") as f:
        for r in satirlar:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(etiket)} tekil iddia, {len(satirlar)} satır -> {CIKTI}")


def uyum(ciftler):
    n = len(ciftler)
    karisiklik = collections.Counter(ciftler)
    ikili = [(a == "DESTEKLENIYOR", b == "DESTEKLENIYOR") for a, b in ciftler]
    return {"iddia": n, "ayni_karar": round(sum(a == b for a, b in ciftler) / n, 3) if n else None,
            "kappa_3_sinif": e06.kappa(ciftler), "kappa_destek_mi": e06.kappa(ikili),
            "karisiklik_yargic_x_claude": {f"{a} / {b}": c for (a, b), c in sorted(karisiklik.items())}}


def ozet():
    satirlar = [json.loads(l) for l in open(CIKTI, encoding="utf-8")]
    sonuc = {"tarih": date.today().isoformat(), "ucuncu_yargic": UCUNCU, "kaynak": os.path.basename(CIKTI), "yargic_dogrulugu": {}, "tablo": {},
             "eslestirilmis": []}
    print(f"YARGIÇ DOĞRULUĞU ({UCUNCU} kararına göre; aynı iddialar)")
    for ad, alan in (("qwen2.5:7b", "karar_7b"), ("qwen2.5:32b", "karar_32b")):
        hepsi = [(r[alan], r["karar_claude"]) for r in satirlar if r[alan] in KARARLAR]
        sonuc["yargic_dogrulugu"][ad] = {"tumu": uyum(hepsi), "model_bazinda": {
            m: uyum([(r[alan], r["karar_claude"]) for r in satirlar if r["model"] == m and r[alan] in KARARLAR]) for m in MODELLER
            if any(r["model"] == m and r[alan] in KARARLAR for r in satirlar)}}
        t = sonuc["yargic_dogrulugu"][ad]["tumu"]
        print(f"  {ad:12} n={t['iddia']} aynı karar={t['ayni_karar']} kappa(3)={t['kappa_3_sinif']} kappa(destek mi)={t['kappa_destek_mi']}")
    # Claude kararlarıyla model ölçüleri: e05 satırları alınır, atıflı iddiaların kararı Claude'unkiyle değiştirilir
    karar = {(r["model"], r["girdi"], r["sira"]): r["karar_claude"] for r in satirlar}
    olcu = {}
    for m in MODELLER:
        uretim, sadakat, _ = e06.yukle(SONUC, m, "qwen2.5:32b")
        for g, h in sadakat.items():
            for sira, i in enumerate(h["iddialar"]):
                if i["karar"] != "ATIFSIZ":
                    i["karar"] = karar[(m, g, sira)]
        olcu[m] = {g: e06.girdi_olculeri(uretim[g], sadakat.get(g)) for g in uretim}
        katmanlar = sorted({o["katman"] for o in olcu[m].values()})
        sonuc["tablo"][m] = {k: e06.ozetle([o for o in olcu[m].values() if o["katman"] == k]) for k in katmanlar}
        sonuc["tablo"][m]["TÜMÜ"] = e06.ozetle(list(olcu[m].values()))
    print(f"\nSADAKAT ({UCUNCU} yargıçla)")
    for m in MODELLER:
        t = sonuc["tablo"][m]["TÜMÜ"]
        print(f"  {m:12} sadakat={t['sadakat']} çelişki={t['celiski_orani']} iddia={t['iddia']} "
              f"desteklenen={sum(o['destek'] for o in olcu[m].values())} atıfsız={t['atifsiz_orani']}")
    girdiler = sorted(set.intersection(*(set(o) for o in olcu.values())))
    sonuc["eslestirilmis"] = [e06.eslestir(olcu, girdiler, a, b) for a, b in CIFTLER]
    json.dump(sonuc, open(OZET, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n-> {OZET}")


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "hazirla":
        hazirla(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 14)
    elif komut == "topla":
        topla(sys.argv[2])
    elif komut == "ozet":
        ozet()
    else:
        print(__doc__)
