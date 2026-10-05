"""
BENCHMARK 8 — MODEL KARŞILAŞTIRMASI (adım 9): b06 + b07 çıktılarından katman tablosu ve EŞLEŞTİRİLMİŞ istatistik.

Aynı 56 girdi, aynı istem, aynı yargıç; modeller girdi girdi eşleştirilir:
  - Sadakat (iddia düzeyi): kaynağın DESTEKLEDİĞİ iddia / yargılanan iddia. Fark için %95 bootstrap güven aralığı
    (girdiler yeniden örneklenir, 10.000 tekrar, tohum 42) ve işaret testi (girdi başına sadakat farkının yönü; kesin binom).
  - Atıfsız cümle oranı, çelişki, yalnızca ret ("bilgi yok") cevapları (McNemar, kesin binom), dil çöküşü, cevap uzunluğu.
Bağımlılık yok (scipy gerekmez).

Kullanım: python degerlendirme/b08_karsilastir.py [--dizin degerlendirme/colab_son] [--a qwen-taban] [--b varchat]
                                                  [--yargic qwen2.5:32b] [--uyum qwen2.5:32b]
                                                  [--ciftler "qwen-taban>varchat,varchat>qwen2.5:14b"]
  --ciftler: eşleştirilmiş karşılaştırılacak model çiftleri ("A>B": B - A raporlanır; model adlarında ':' olduğu için ayraç '>');
             verilmezse --a > --b
  --yargic: hangi yargıcın puanları kullanılsın (varsayılan: ana yargıç qwen2.5:7b; dosya adında '__yargic-' eki yok)
  --uyum  : ana yargıç ile verilen yargıç aynı iddialarda ne kadar anlaşıyor (yüzde uyum + Cohen kappa, model başına)
Çıktı   : <dizin>/karsilastirma_istatistik_<tarih>[__yargic-<ad>].json
"""

import glob
import json
import math
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

RET = "Bu konuda elimdeki kaynaklarda bilgi yok."
KARARLAR = ("DESTEKLENIYOR", "DESTEKLENMIYOR", "CELISIYOR")
KATMANLAR = ("A_hotspot", "B_germline_yaygin", "C_kimlik", "C_koordinat", "D_literatursuz")


def arguman(ad, varsayilan):
    return sys.argv[sys.argv.index(ad) + 1] if ad in sys.argv else varsayilan


def son(dizin, desen, ek_yok=False):
    d = glob.glob(os.path.join(dizin, desen))
    if ek_yok:
        d = [x for x in d if "__yargic-" not in os.path.basename(x)]     # ana yargıcın dosyaları
    return max(d, key=os.path.getmtime) if d else None


def dosya_adi(m):
    return m.replace(":", "-").replace("/", "-")


def sadakat_dosyasi(dizin, ad, yargic=None):
    if yargic:
        return son(dizin, f"sadakat_{ad}_*__yargic-{dosya_adi(yargic)}.jsonl")
    return son(dizin, f"sadakat_{ad}_*.jsonl", ek_yok=True)


def yukle(dizin, model, yargic=None):
    ad = dosya_adi(model)
    u, s = son(dizin, f"uretim_{ad}_*.jsonl"), sadakat_dosyasi(dizin, ad, yargic)
    if not u or not s:
        raise SystemExit(f"{model}: üretim ya da sadakat dosyası yok ({dizin})")
    uretim = {json.loads(l)["girdi"]: json.loads(l) for l in open(u, encoding="utf-8") if l.strip()}
    sadakat = {json.loads(l)["girdi"]: json.loads(l) for l in open(s, encoding="utf-8") if l.strip()}
    return uretim, sadakat, (os.path.basename(u), os.path.basename(s))


def girdi_olculeri(r, h):
    """Bir girdi için ölçüler (üretim satırı r, sadakat satırı h)."""
    iddialar = (h or {}).get("iddialar") or []
    yarg = [i for i in iddialar if i["karar"] in KARARLAR]
    cevap = (r.get("cevap") or "").strip()
    return {"katman": r["katman"], "destek": sum(i["karar"] == "DESTEKLENIYOR" for i in yarg), "yarg": len(yarg),
            "celiski": sum(i["karar"] == "CELISIYOR" for i in yarg), "cumle": len(iddialar),
            "atifsiz": sum(i["karar"] == "ATIFSIZ" for i in iddialar), "belirsiz": sum(i["karar"] == "BELIRSIZ" for i in iddialar),
            "ret": cevap == RET, "uzunluk": len(cevap.split()), "cjk": ((r.get("denetim") or {}).get("cjk_orani") or 0) > 0.02,
            "hata": bool(r.get("hata")), "sure": r.get("sure_s") or 0}


def ozetle(olcu):
    y = sum(o["yarg"] for o in olcu)
    c = sum(o["cumle"] for o in olcu)
    n = len(olcu) or 1
    return {"girdi": len(olcu), "iddia": y, "sadakat": round(sum(o["destek"] for o in olcu) / y, 3) if y else None,
            "celiski_orani": round(sum(o["celiski"] for o in olcu) / y, 3) if y else None,
            "atifsiz_orani": round(sum(o["atifsiz"] for o in olcu) / c, 3) if c else None,
            "yalniz_ret": sum(o["ret"] for o in olcu), "dil_cokusu": sum(o["cjk"] for o in olcu), "uretim_hatasi": sum(o["hata"] for o in olcu),
            "belirsiz": sum(o["belirsiz"] for o in olcu), "ort_kelime": round(sum(o["uzunluk"] for o in olcu) / n, 1),
            "ort_cumle": round(c / n, 1), "ort_sure_s": round(sum(o["sure"] for o in olcu) / n, 1)}


def binom_iki_yonlu(k, n):
    """Kesin iki yönlü binom testi (p=0.5): işaret testi ve McNemar için."""
    if n == 0:
        return None
    uc = min(k, n - k)
    p = sum(math.comb(n, i) for i in range(uc + 1)) / 2 ** n * 2
    return round(min(1.0, p), 4)


def bootstrap_fark(a_olcu, b_olcu, tekrar=10000, tohum=42):
    """Sadakat farkı (B - A), iddia düzeyinde; girdiler eşleştirilmiş yeniden örneklenir. (fark, alt, üst)"""
    rng = random.Random(tohum)
    n = len(a_olcu)

    def oran(liste):
        y = sum(o["yarg"] for o in liste)
        return sum(o["destek"] for o in liste) / y if y else 0.0
    fark = oran(b_olcu) - oran(a_olcu)
    farklar = []
    for _ in range(tekrar):
        idx = [rng.randrange(n) for _ in range(n)]
        farklar.append(oran([b_olcu[i] for i in idx]) - oran([a_olcu[i] for i in idx]))
    farklar.sort()
    return round(fark, 3), round(farklar[int(0.025 * tekrar)], 3), round(farklar[int(0.975 * tekrar)], 3)


def kappa(ciftler):
    """Cohen kappa: iki yargıcın aynı iddialara verdiği kararlar [(k1, k2), ...]."""
    n = len(ciftler)
    if not n:
        return None
    po = sum(a == b for a, b in ciftler) / n
    siniflar = {a for a, _ in ciftler} | {b for _, b in ciftler}
    pe = sum((sum(a == s for a, _ in ciftler) / n) * (sum(b == s for _, b in ciftler) / n) for s in siniflar)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def yargic_uyumu(dizin, model, yargic):
    """Ana yargıç (7B) ile ikinci yargıç aynı iddialarda ne kadar anlaşıyor? Yalnız ikisinin de karar verdiği iddialar."""
    ad = dosya_adi(model)
    d1, d2 = sadakat_dosyasi(dizin, ad), sadakat_dosyasi(dizin, ad, yargic)
    if not d1 or not d2:
        return None

    def kararlar(yol):
        k = {}
        for l in open(yol, encoding="utf-8"):
            if l.strip():
                h = json.loads(l)
                for i in h["iddialar"]:
                    if i["karar"] in KARARLAR:
                        k[(h["girdi"], i["iddia"])] = i["karar"]
        return k
    k1, k2 = kararlar(d1), kararlar(d2)
    ortak = sorted(set(k1) & set(k2))
    ciftler = [(k1[x], k2[x]) for x in ortak]
    ikili = [(a == "DESTEKLENIYOR", b == "DESTEKLENIYOR") for a, b in ciftler]
    return {"iddia": len(ortak), "uyum": round(sum(a == b for a, b in ciftler) / len(ortak), 3) if ortak else None,
            "kappa_3_sinif": kappa(ciftler), "kappa_destek_mi": kappa(ikili),
            "sadakat_ana": round(sum(a == "DESTEKLENIYOR" for a, _ in ciftler) / len(ortak), 3) if ortak else None,
            "sadakat_ikinci": round(sum(b == "DESTEKLENIYOR" for _, b in ciftler) / len(ortak), 3) if ortak else None}


def eslestir(olcu, girdiler, a_ad, b_ad):
    """A -> B eşleştirilmiş karşılaştırma (aynı girdiler)."""
    A, B = [olcu[a_ad][g] for g in girdiler], [olcu[b_ad][g] for g in girdiler]
    fark, alt, ust = bootstrap_fark(A, B)
    iki_yargili = [(a, b) for a, b in zip(A, B) if a["yarg"] and b["yarg"]]
    artan = sum(1 for a, b in iki_yargili if b["destek"] / b["yarg"] > a["destek"] / a["yarg"])
    azalan = sum(1 for a, b in iki_yargili if b["destek"] / b["yarg"] < a["destek"] / a["yarg"])
    atif_art = sum(1 for a, b in zip(A, B) if a["cumle"] and b["cumle"] and b["atifsiz"] / b["cumle"] < a["atifsiz"] / a["cumle"])
    atif_az = sum(1 for a, b in zip(A, B) if a["cumle"] and b["cumle"] and b["atifsiz"] / b["cumle"] > a["atifsiz"] / a["cumle"])
    ret_yalniz_a = sum(1 for a, b in zip(A, B) if a["ret"] and not b["ret"])
    ret_yalniz_b = sum(1 for a, b in zip(A, B) if b["ret"] and not a["ret"])
    ist = {"a": a_ad, "b": b_ad, "girdi": len(girdiler),
           "sadakat_fark_b_eksi_a": fark, "sadakat_fark_guven_95": [alt, ust],
           "sadakat_isaret_testi": {"b_daha_iyi": artan, "a_daha_iyi": azalan, "esit": len(iki_yargili) - artan - azalan,
                                    "p": binom_iki_yonlu(artan, artan + azalan)},
           "atifsiz_isaret_testi": {"b_daha_az_atifsiz": atif_art, "a_daha_az_atifsiz": atif_az, "p": binom_iki_yonlu(atif_art, atif_art + atif_az)},
           "yalniz_ret_mcnemar": {"yalniz_a_reddetti": ret_yalniz_a, "yalniz_b_reddetti": ret_yalniz_b,
                                  "p": binom_iki_yonlu(ret_yalniz_a, ret_yalniz_a + ret_yalniz_b)}}
    print(f"\nEŞLEŞTİRİLMİŞ: {a_ad} -> {b_ad} ({len(girdiler)} girdi)")
    print(f"   sadakat farkı {fark:+.3f}  (%95 bootstrap GA: {alt:+.3f} .. {ust:+.3f})")
    s = ist["sadakat_isaret_testi"]
    print(f"   girdi başına sadakat: {b_ad} daha iyi {s['b_daha_iyi']}, {a_ad} daha iyi {s['a_daha_iyi']}, eşit {s['esit']} | işaret testi p={s['p']}")
    s = ist["atifsiz_isaret_testi"]
    print(f"   atıfsız cümle oranı: {b_ad} daha az {s['b_daha_az_atifsiz']}, {a_ad} daha az {s['a_daha_az_atifsiz']} | p={s['p']}")
    s = ist["yalniz_ret_mcnemar"]
    print(f"   yalnız 'bilgi yok': yalnız {a_ad} {s['yalniz_a_reddetti']}, yalnız {b_ad} {s['yalniz_b_reddetti']} | McNemar p={s['p']}")
    return ist


def main():
    dizin = arguman("--dizin", os.path.join(os.path.dirname(os.path.abspath(__file__)), "sonuclar"))
    a_ad, b_ad = arguman("--a", "qwen-taban"), arguman("--b", "varchat")
    ciftler = [tuple(x.strip() for x in c.split(">", 1)) for c in (arguman("--ciftler", None) or "").split(",") if ">" in c]
    ciftler = ciftler or [(a_ad, b_ad)]
    yargic = arguman("--yargic", None)
    adaylar = ("qwen2.5:7b", "qwen-taban", "varchat", "qwen2.5:14b") + tuple(x for c in ciftler for x in c)
    modeller = [m for m in dict.fromkeys(adaylar)
                if son(dizin, f"uretim_{dosya_adi(m)}_*.jsonl") and sadakat_dosyasi(dizin, dosya_adi(m), yargic)]
    if not modeller:
        raise SystemExit(f"{dizin} içinde {'yargıç ' + yargic + ' için ' if yargic else ''}sadakat dosyası yok")
    print(f"yargıç: {yargic or 'ana (qwen2.5:7b)'}")
    veri = {m: yukle(dizin, m, yargic) for m in dict.fromkeys(modeller)}
    girdiler = sorted(set.intersection(*(set(v[0]) for v in veri.values())))
    olcu = {m: {g: girdi_olculeri(v[0][g], v[1].get(g)) for g in girdiler} for m, v in veri.items()}

    tablo = {}
    for k in KATMANLAR + ("TÜMÜ",):
        tablo[k] = {m: ozetle([o for o in olcu[m].values() if k == "TÜMÜ" or o["katman"] == k]) for m in olcu}

    print(f"dizin: {dizin} | ortak girdi: {len(girdiler)} | modeller: {', '.join(olcu)}\n")
    basliklar = [("sadakat", "Sadakat ↑"), ("atifsiz_orani", "Atıfsız cümle ↓"), ("celiski_orani", "Çelişki ↓"),
                 ("yalniz_ret", "Yalnız 'bilgi yok' ↓"), ("dil_cokusu", "Dil çöküşü ↓"), ("iddia", "Yargılanan iddia"),
                 ("ort_cumle", "Ort. cümle"), ("ort_sure_s", "Ort. süre (sn)")]
    for k, satir in tablo.items():
        print(f"== {k} (n={satir[modeller[0]]['girdi']})")
        for anahtar, ad in basliklar:
            print(f"   {ad:22} " + "  ".join(f"{m}={satir[m][anahtar]}" for m in olcu))

    # ---- eşleştirilmiş karşılaştırmalar: her çift için A -> B
    ist = [eslestir(olcu, girdiler, a, b) for a, b in ciftler if a in olcu and b in olcu]
    if len(ist) == 1:
        ist = ist[0]                                  # eski biçimle uyumlu (tek çift)

    uyum = {}
    if "--uyum" in sys.argv:
        ikinci = arguman("--uyum", None)
        print(f"\nYARGIÇ UYUMU: ana (qwen2.5:7b) ile {ikinci}, aynı iddialarda")
        for m in olcu:
            u = yargic_uyumu(dizin, m, ikinci)
            if u:
                uyum[m] = u
                print(f"   {m:11} iddia {u['iddia']:3} | uyum {u['uyum']} | kappa (3 sınıf) {u['kappa_3_sinif']} | "
                      f"kappa (destek mi) {u['kappa_destek_mi']} | sadakat ana {u['sadakat_ana']} -> {ikinci} {u['sadakat_ikinci']}")

    ek = f"__yargic-{dosya_adi(yargic)}" if yargic else ""
    cikti = os.path.join(dizin, f"karsilastirma_istatistik_{date.today().isoformat()}{ek}.json")
    json.dump({"tarih": date.today().isoformat(), "yargic": yargic or "qwen2.5:7b", "dosyalar": {m: v[2] for m, v in veri.items()},
               "girdi": len(girdiler), "tablo": tablo, "eslestirilmis": ist, "yargic_uyumu": uyum},
              open(cikti, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n-> {cikti}")


if __name__ == "__main__":
    main()
