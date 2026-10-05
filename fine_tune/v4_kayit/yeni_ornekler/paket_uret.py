# -*- coding: utf-8 -*-
"""kaynaklar_v4.jsonl -> yazım paketleri (paket_N.json). Her girdi için istenen örnek sayısı türüne göre."""
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # repo kökü (fine_tune/v4_kayit/<klasör>/)
BURASI = os.path.dirname(os.path.abspath(__file__))
PAKET_SAYISI = int(sys.argv[1]) if len(sys.argv) > 1 else 8

satirlar = [json.loads(l) for l in open(os.path.join(KOK, "fine_tune", "kaynaklar_v4.jsonl"), encoding="utf-8") if l.strip()]
girdiler = []
# ~500 toplam hedefi (v3'ten 204 + yeni ~300) ve ret oranı ~%28 (v3 ile aynı; fazla ret modeli gereksiz reddetmeye iter)
varyant_sira = 0
for s in satirlar:
    if s["kademe"] == "gen":
        istenen = {"ozet": 1, "takip": 1, "cok_turlu": 0, "ret_kapsam": 0, "gen_ret": 2}
    else:
        istenen = {"ozet": 1, "takip": 1, "cok_turlu": 1, "ret_kapsam": 1 if varyant_sira % 2 == 0 else 0, "gen_ret": 0}
        varyant_sira += 1
    girdiler.append({"girdi": s["girdi"], "etiket": s["etiket"], "kademe": s["kademe"], "gen": s["gen"], "alan": s["alan"],
                     "bicim": s["bicim"], "ilk_soru": s["ilk_soru"], "istenen": istenen,
                     "kaynaklar": {str(i): {"baslik": m["baslik"], "ozet": m["ozet"], "alaka": m["alaka"]}
                                   for i, m in enumerate(s["makaleler"], start=1)}})
# alanlar paketlere dağılsın diye sırayla dağıt (round-robin)
paketler = [[] for _ in range(PAKET_SAYISI)]
for i, g in enumerate(girdiler):
    paketler[i % PAKET_SAYISI].append(g)
for n, p in enumerate(paketler, start=1):
    with open(os.path.join(BURASI, f"paket_{n}.json"), "w", encoding="utf-8") as f:
        json.dump({"paket": n, "girdiler": p}, f, ensure_ascii=False, indent=1)
    print(f"paket_{n}: {len(p)} girdi, {sum(len(json.dumps(g, ensure_ascii=False)) for g in p) // 1000} bin karakter")
toplam = sum(sum(g["istenen"].values()) for g in girdiler)
print(f"{len(girdiler)} girdi -> {toplam} örnek istenecek (+ ret_yabanci ~{len(girdiler) // 2})")
