# -*- coding: utf-8 -*-
"""sonuc_1..6.json (v3 denetimi) -> fine_tune/denetim_v3.json + özet istatistik."""
import collections
import json
import os
import re

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # repo kökü (fine_tune/v4_kayit/<klasör>/)
BURASI = os.path.dirname(os.path.abspath(__file__))
v3 = [json.loads(l) for l in open(os.path.join(KOK, "fine_tune", "egitim_verisi_v3.jsonl"), encoding="utf-8") if l.strip()]
GECERLI = {"AYNEN", "DUZELTILDI", "SIL", "RET_DOGRU", "RET_YANLIS"}
# Denetçi kararının elle geri çevrildiği örnekler (gerekçesiyle; tezde raporlanır)
ELLE = {172: ("RET_DOGRU", "Soru diyet önerisi istiyor; [2]'deki bilgi in silico doking (çay polifenolleri p53'e bağlanır). Bu bir diyet "
                           "önerisi değil; cevaba koymak deney bağlamını düşürme hatasını öğretir. Ret korunur.")}
ATIF_SONU = re.compile(r"\[\d+\](?:\s*,?\s*\[\d+\])*[.)]?\s*$")

kararlar, sorunlar, cumle_say = {}, [], collections.Counter()
for n in range(1, 7):
    yol = os.path.join(BURASI, f"sonuc_{n}.json")
    if not os.path.exists(yol):
        print(f"EKSİK: sonuc_{n}.json")
        continue
    d = json.load(open(yol, encoding="utf-8"))
    for k in d["ornekler"]:
        i = int(k["index"])
        if i in ELLE:
            k = dict(k, denetci_karari=k["karar"], karar=ELLE[i][0], elle_gerekce=ELLE[i][1], duzeltilmis_cevap=None)
        if k["karar"] not in GECERLI:
            sorunlar.append(f"{i}: geçersiz karar {k['karar']}")
        if i in kararlar:
            sorunlar.append(f"{i}: iki kez karar")
        if v3[i]["varyant"] != k.get("varyant", v3[i]["varyant"]):
            sorunlar.append(f"{i}: varyant uyuşmuyor ({k.get('varyant')} != {v3[i]['varyant']})")
        if k["karar"] in ("DUZELTILDI", "RET_YANLIS") and k.get("duzeltilmis_cevap"):
            cumleler = [c for c in re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9])|\n+", k["duzeltilmis_cevap"].strip()) if c.strip()]
            atifsiz = [c for c in cumleler if not ATIF_SONU.search(c)]
            if atifsiz:
                sorunlar.append(f"{i}: düzeltilmiş cevapta atıfsız cümle: {atifsiz[0][:80]}")
        for c in k.get("cumleler") or []:
            cumle_say[c.get("karar", "?")] += 1
        kararlar[i] = k
eksik = [i for i in range(len(v3)) if i not in kararlar]
print(f"{len(kararlar)}/{len(v3)} örnek kararlı; eksik: {eksik[:20]}{'...' if len(eksik) > 20 else ''}")
print("sorunlar:", len(sorunlar))
for s in sorunlar[:30]:
    print("  ", s)
tur_karar = collections.Counter((v3[i]["tur"], k["karar"]) for i, k in kararlar.items())
print("\ntür x karar:")
for tur in sorted({t for t, _ in tur_karar}):
    print(f"  {tur:16}", {k: v for (t, k), v in sorted(tur_karar.items()) if t == tur})
print("\ncümle kararları:", dict(cumle_say))
print("genel:", dict(collections.Counter(k["karar"] for k in kararlar.values())))
json.dump({"kaynak": "Claude alt ajanları, 6 paket, kaynak başlık+özet ile cümle cümle", "ornekler": [kararlar[i] for i in sorted(kararlar)]},
          open(os.path.join(KOK, "fine_tune", "denetim_v3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("-> fine_tune/denetim_v3.json")
