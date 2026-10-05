# -*- coding: utf-8 -*-
"""dogrulama_N.json (doğrulanmış yeni örnekler) -> fine_tune/yeni_ornekler_v4.jsonl (birlestir_v4.py'nin girdisi) + istatistik."""
import collections
import glob
import json
import os
import re

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # repo kökü (fine_tune/v4_kayit/<klasör>/)
BURASI = os.path.dirname(os.path.abspath(__file__))
ATIF = re.compile(r"\[(\d+)\]")
ATIF_SONU = re.compile(r"\[\d+\](?:\s*,?\s*\[\d+\])*[.)]?\s*$")
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")

kaynak = {json.loads(l)["girdi"]: json.loads(l) for l in open(os.path.join(KOK, "fine_tune", "kaynaklar_v4.jsonl"), encoding="utf-8") if l.strip()}
# Doğrulamadan sonra elle yapılan düzeltmeler: (girdi, alan, eski parça, yeni parça, gerekçe) — tezde raporlanır
ELLE = [("rs9923231", "ozet",
         "rs9923231 polimorfizminin kardiyovasküler ve serebrovasküler hastalık yüksek riskiyle yakından ilişkili olduğunu bildirmiştir",
         "rs9923231 polimorfizminin kardiyovasküler ve serebrovasküler hastalıkla anlamlı biçimde ilişkili olduğunu bildirmiştir",
         "Kaynak 2 'yüksek risk' diyor ama rs9923231 için verdiği OR 0,74 (1'in altında); kendi içinde çelişen yön iddiası "
         "öğretilmesin diye yalnız ilişki + sayılar bırakıldı.")]
elle_uygulanan = []
karar = collections.Counter()
sorun, cikti = [], []


def cevap_kontrol(girdi, metin, n_kaynak, yer):
    cumleler = [c for c in re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9])|\n+", metin.strip()) if c.strip()]
    for c in cumleler:
        if not ATIF_SONU.search(c):
            sorun.append(f"{girdi} {yer}: atıfsız cümle: {c[:70]}")
    for n in ATIF.findall(metin):
        if not 1 <= int(n) <= n_kaynak:
            sorun.append(f"{girdi} {yer}: kaynak dışı atıf [{n}] (kaynak {n_kaynak})")
    if CJK.search(metin):
        sorun.append(f"{girdi} {yer}: yabancı alfabe")


for yol in sorted(glob.glob(os.path.join(BURASI, "dogrulama_*.json"))):
    d = json.load(open(yol, encoding="utf-8"))
    for g in d["girdiler"]:
        ad = g["girdi"]
        if ad not in kaynak:
            sorun.append(f"{ad}: kaynaklar_v4'te yok")
            continue
        n = len(kaynak[ad]["makaleler"])
        o = {"girdi": ad, "ozet": None, "takip": [], "cok_turlu": None, "ret_kapsam": [], "gen_ret": []}
        karar["ozet:" + str(g.get("ozet_karar"))] += 1
        if g.get("ozet") and g.get("ozet_karar") != "SIL":
            o["ozet"] = g["ozet"].strip()
            for ad_, alan_, eski, yeni, neden in ELLE:
                if ad_ == ad and alan_ == "ozet":
                    assert o["ozet"].count(eski) == 1, (ad, eski[:50])
                    o["ozet"] = o["ozet"].replace(eski, yeni)
                    elle_uygulanan.append(f"{ad} {alan_}: {neden}")
            cevap_kontrol(ad, o["ozet"], n, "ozet")
        for t in g.get("takip") or []:
            karar["takip:" + str(t.get("karar"))] += 1
            if t.get("karar") != "SIL" and t.get("cevap"):
                o["takip"].append({"soru": t["soru"], "cevap": t["cevap"].strip()})
                cevap_kontrol(ad, t["cevap"], n, "takip")
        c = g.get("cok_turlu")
        if c:
            karar["cok_turlu:" + str(c.get("karar"))] += 1
            if c.get("karar") != "SIL" and c.get("cevap"):
                o["cok_turlu"] = {"soru": c["soru"], "cevap": c["cevap"].strip()}
                cevap_kontrol(ad, c["cevap"], n, "cok_turlu")
        for alan in ("ret_kapsam", "gen_ret"):
            for r in g.get(alan) or []:
                karar[f"{alan}:{r.get('karar')}"] += 1
                soru = (r.get("duzeltilmis_soru") if r.get("karar") == "RET_YANLIS" else None) or r.get("soru")
                if r.get("karar") in ("RET_DOGRU", "RET_YANLIS") and soru:
                    o[alan].append(soru.strip())             # RET_YANLIS: doğrulayıcının önerdiği, kaynaklarda cevabı olmayan soru
        cikti.append(o)

eksik = sorted(set(kaynak) - {o["girdi"] for o in cikti})
print(f"{len(cikti)} girdi toplandı; cevabı olmayan: {eksik or 'yok'}")
print("kararlar:", dict(sorted(karar.items())))
print("elle düzeltme:", elle_uygulanan or "yok")
assert len(elle_uygulanan) == len(ELLE), "bir elle düzeltme uygulanamadı"
print(f"otomatik kontrol sorunları: {len(sorun)}")
for s in sorun[:40]:
    print("  ", s)
with open(os.path.join(KOK, "fine_tune", "yeni_ornekler_v4.jsonl"), "w", encoding="utf-8") as f:
    for o in cikti:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
print("-> fine_tune/yeni_ornekler_v4.jsonl")
