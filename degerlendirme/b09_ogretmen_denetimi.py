"""
BENCHMARK 9 — EĞİTİM VERİSİ (ÖĞRETMEN) DENETİMİ: fine_tune/egitim_verisi.jsonl'daki 204 örnek cevap kendi kaynaklarına sadık mı?

Neden: Eğitim örneklerinin cevaplarını Temmuz 2026'da bir yapay zekâ (Claude, "öğretmen") yazdı; insan uzman kontrol etmedi.
Öğretmen kaynakta olmayan bilgi eklediyse, eğitilen model de bunu öğrenir (5 Ekim: varchat'in sadakati tabandan düşük çıktı).

Yöntem (ölçümdeki yargıçla AYNI istem ve karar türleri: b07.yargila):
  - özet / takip / çok turlu takip: son cevap cümlelere bölünür; atıflı her cümle, atıf verdiği kaynak(lar)ın başlık+özetine
    karşı yargılanır (DESTEKLENIYOR / DESTEKLENMIYOR / CELISIYOR); atıfsız cümle ve kaynak sayısını aşan atıf ayrıca sayılır.
  - ret ("bilgi yok") örnekleri: yargıca "bu soru bu kaynaklarla cevaplanabilir mi?" sorulur; cevaplanabiliyorsa ret YANLIŞTIR.
  Aynı (varyant, soru, cevap) bir kez yargılanır (tekrar eden örnek varsa).

Kullanım: python degerlendirme/b09_ogretmen_denetimi.py --yargic qwen2.5:32b [--sinir N]   (N: deneme için ilk N örnek)
Çıktı (degerlendirme/sonuclar/, kaldığı yerden devam eder):
  ogretmen_denetimi__yargic-<ad>.jsonl   örnek başına kararlar
  ogretmen_ozet__yargic-<ad>.json        tür / bölme / varyant tablosu
  ogretmen_sorunlu__yargic-<ad>.csv      desteklenmeyen ve çelişen cümleler + yanlış retler (insan incelemesi için)
"""

import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import ollama

import b07_sadakat as b07
import c04_varchat_ollama as app

BURASI = os.path.dirname(os.path.abspath(__file__))
VERI = os.path.join(os.path.dirname(BURASI), "fine_tune", "egitim_verisi.jsonl")
KAYNAK_DESENI = re.compile(r"^\[(\d+)\] Başlık: (.*?)\n\s*Özet: (.*?)(?=\n\n\[\d+\] Başlık: |\Z)", re.M | re.S)

RET_SISTEM = (
    "Sen titiz bir bilimsel yargıçsın. Sana birkaç makale özeti (KAYNAK) ve bir SORU verilecek. Görevin: bu sorunun "
    "YALNIZCA verilen kaynaklarla (en azından kısmen) cevaplanıp cevaplanamayacağını söylemek. Kendi bilgini kullanma.\n"
    'Yalnızca şu JSON ile cevap ver: {"cevaplanabilir": true|false, "gerekce": "<bir cümle; varsa kaynak numarası>"}'
)


def arguman(ad, varsayilan=None):
    return sys.argv[sys.argv.index(ad) + 1] if ad in sys.argv else varsayilan


def kaynaklari_ayir(sistem):
    """System mesajındaki KAYNAKLAR bloğu -> {n: {'baslik', 'ozet'}}"""
    blok = sistem.split("KAYNAKLAR:", 1)[1].strip() if "KAYNAKLAR:" in sistem else ""
    return {int(n): {"baslik": b.strip(), "ozet": o.strip()} for n, b, o in KAYNAK_DESENI.findall(blok)}


def ret_yargila(soru, kaynaklar, model):
    """(cevaplanabilir: bool|None, gerekce). Model hatasında bir kez farklı tohumla yeniden dener."""
    metin = "\n\n".join(f"KAYNAK [{n}]: {k['baslik']}\n{k['ozet']}" for n, k in sorted(kaynaklar.items()))
    mesajlar = [{"role": "system", "content": RET_SISTEM}, {"role": "user", "content": f"{metin}\n\nSORU: {soru}\n\nKarar?"}]
    for ayar in (b07.YARGIC_AYARLARI, dict(b07.YARGIC_AYARLARI, temperature=0.3, seed=b07.YARGIC_AYARLARI["seed"] + 1)):
        try:
            j = json.loads(ollama.chat(model=model, format="json", options=ayar, messages=mesajlar)["message"]["content"])
            deger = j.get("cevaplanabilir")
            if isinstance(deger, str):
                deger = deger.strip().lower() in ("true", "evet", "yes")
            if isinstance(deger, bool):
                return deger, str(j.get("gerekce", ""))[:300]
        except (ollama.ResponseError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
            continue
    return None, "yargıç hatası"


def ornek_denetle(r, model):
    msgs = r["messages"]
    kaynaklar = kaynaklari_ayir(msgs[0]["content"])
    soru, cevap = msgs[-2]["content"], msgs[-1]["content"].strip()
    kayit = {"varyant": r["varyant"], "bolme": r["bolme"], "tur": r["tur"], "soru": soru, "kaynak_sayisi": len(kaynaklar)}
    if cevap == app.RET_CEVAP:
        cevaplanabilir, gerekce = ret_yargila(soru, kaynaklar, model)
        kayit.update(ret=True, cevaplanabilir=cevaplanabilir, gerekce=gerekce,
                     ret_dogru=None if cevaplanabilir is None else (not cevaplanabilir))
        return kayit
    iddialar, gecersiz = [], []
    for c in app.cumlelere_bol(cevap):
        if c == app.RET_CEVAP or len(c.split()) < 4:
            continue
        nums = app.atif_numaralari(c)
        gecersiz += [n for n in nums if n not in kaynaklar]
        nums = sorted({n for n in nums if n in kaynaklar})
        if not nums:
            iddialar.append({"iddia": c, "atif": [], "karar": "ATIFSIZ", "gerekce": ""})
            continue
        karar, gerekce, deneme = b07.yargila(app.ATIF.sub("", c).strip(), [(n, kaynaklar[n]) for n in nums], model)
        iddialar.append({"iddia": c, "atif": nums, "karar": karar, "gerekce": gerekce, "deneme": deneme})
    kayit.update(ret=False, iddialar=iddialar, gecersiz_atif=sorted(set(gecersiz)))
    return kayit


def anahtar(r):
    return hashlib.sha1(json.dumps([r["varyant"], r["messages"][-2]["content"], r["messages"][-1]["content"]],
                                   ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def tablo_yap(kayitlar, alan):
    gruplar = defaultdict(list)
    for k in kayitlar:
        gruplar[k[alan]].append(k)
    gruplar["TÜMÜ"] = list(kayitlar)
    tablo = {}
    for g, liste in gruplar.items():
        iddia = [i for k in liste if not k["ret"] for i in k["iddialar"]]
        yarg = [i for i in iddia if i["karar"] in b07.KARARLAR]
        retler = [k for k in liste if k["ret"]]
        tablo[g] = {"ornek": len(liste), "iddia": len(yarg),
                    "sadakat": round(sum(i["karar"] == "DESTEKLENIYOR" for i in yarg) / len(yarg), 3) if yarg else None,
                    "desteklenmeyen": sum(i["karar"] == "DESTEKLENMIYOR" for i in yarg),
                    "celisen": sum(i["karar"] == "CELISIYOR" for i in yarg),
                    "atifsiz": sum(i["karar"] == "ATIFSIZ" for i in iddia), "belirsiz": sum(i["karar"] == "BELIRSIZ" for i in iddia),
                    "gecersiz_atif": sum(len(k.get("gecersiz_atif") or []) for k in liste),
                    "ret": len(retler), "ret_dogru": sum(1 for k in retler if k.get("ret_dogru") is True),
                    "ret_yanlis": sum(1 for k in retler if k.get("ret_dogru") is False)}
    return tablo


def main():
    yargic = arguman("--yargic", app.MODEL)
    sinir = int(arguman("--sinir", "0") or 0)
    ek = "__yargic-" + yargic.replace(":", "-").replace("/", "-")
    cikti = os.path.join(BURASI, "sonuclar", f"ogretmen_denetimi{ek}.jsonl")
    satirlar = [json.loads(l) for l in open(VERI, encoding="utf-8") if l.strip()]
    if sinir:
        satirlar = satirlar[:sinir]
    try:
        ollama.show(yargic)
    except ollama.ResponseError as e:
        raise SystemExit(f"DURDU: yargıç '{yargic}' Ollama'da yok ({e}).")
    yapilan = {}
    if os.path.exists(cikti):
        for l in open(cikti, encoding="utf-8"):
            if l.strip():
                k = json.loads(l)
                if k.get("yargic_surumu") == b07.YARGIC_SURUMU:
                    yapilan[k["anahtar"]] = k
    tekil = {}
    for r in satirlar:
        tekil.setdefault(anahtar(r), r)
    print(f"eğitim verisi: {len(satirlar)} örnek, {len(tekil)} tekil cevap | yargıç {yargic} | daha önce yargılanmış {len(yapilan)}")
    with open(cikti, "a", encoding="utf-8") as f:
        for i, (a, r) in enumerate(tekil.items(), 1):
            if a in yapilan:
                continue
            k = ornek_denetle(r, yargic)
            k.update(anahtar=a, yargic=yargic, yargic_surumu=b07.YARGIC_SURUMU, tarih=date.today().isoformat())
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
            f.flush()
            yapilan[a] = k
            if k["ret"]:
                print(f"[{i}/{len(tekil)}] {r['varyant']:18} {r['tur']:16} ret {'DOĞRU' if k['ret_dogru'] else ('YANLIŞ' if k['ret_dogru'] is False else '?')}")
            else:
                say = defaultdict(int)
                for d in k["iddialar"]:
                    say[d["karar"]] += 1
                print(f"[{i}/{len(tekil)}] {r['varyant']:18} {r['tur']:16} destek {say['DESTEKLENIYOR']} yok {say['DESTEKLENMIYOR']} "
                      f"çelişki {say['CELISIYOR']} atıfsız {say['ATIFSIZ']} geçersiz atıf {len(k['gecersiz_atif'])}")
    # Her örneğe (tekrarlar dahil) kendi cevabının sonucunu bağla: tablolar 204 örnek üzerinden
    kayitlar = [dict(yapilan[anahtar(r)], tur=r["tur"], bolme=r["bolme"], varyant=r["varyant"]) for r in satirlar if anahtar(r) in yapilan]
    tekil_kayitlar = [yapilan[a] for a in tekil if a in yapilan]
    ozet = {"yargic": yargic, "tarih": date.today().isoformat(), "ornek": len(kayitlar), "tekil_cevap": len(tekil_kayitlar),
            "tur": tablo_yap(kayitlar, "tur"), "bolme": tablo_yap(kayitlar, "bolme"),
            "varyant_tekil": tablo_yap(tekil_kayitlar, "varyant"), "tekil_toplam": tablo_yap(tekil_kayitlar, "tur")["TÜMÜ"]}
    json.dump(ozet, open(os.path.join(BURASI, "sonuclar", f"ogretmen_ozet{ek}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(BURASI, "sonuclar", f"ogretmen_sorunlu{ek}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["varyant", "tur", "soru", "sorun", "cumle", "atif", "yargic_gerekcesi", "INSAN_KARARI", "not"])
        for k in tekil_kayitlar:
            if k["ret"] and k.get("ret_dogru") is False:
                w.writerow([k["varyant"], k["tur"], k["soru"], "YANLIŞ RET (kaynakta cevap var)", "", "", k["gerekce"], "", ""])
            for d in k.get("iddialar") or []:
                if d["karar"] in ("DESTEKLENMIYOR", "CELISIYOR"):
                    w.writerow([k["varyant"], k["tur"], k["soru"], d["karar"], d["iddia"], ",".join(map(str, d["atif"])), d["gerekce"], "", ""])
    t = ozet["tur"]
    print(f"\nÖĞRETMEN DENETİMİ (yargıç {yargic}) — {ozet['ornek']} örnek, {ozet['tekil_cevap']} tekil cevap")
    for g, v in t.items():
        print(f"  {g:16} örnek {v['ornek']:3} | iddia {v['iddia']:3} sadakat {v['sadakat']} | desteklenmeyen {v['desteklenmeyen']} "
              f"çelişen {v['celisen']} atıfsız {v['atifsiz']} geçersiz atıf {v['gecersiz_atif']} | ret {v['ret']} (doğru {v['ret_dogru']}, yanlış {v['ret_yanlis']})")
    for g, v in ozet["bolme"].items():
        if g != "TÜMÜ":
            print(f"  bölme {g:10} sadakat {v['sadakat']} (iddia {v['iddia']})")
    en_kotu = sorted(((v["sadakat"], g) for g, v in ozet["varyant_tekil"].items() if g != "TÜMÜ" and v["sadakat"] is not None))[:5]
    print("  en düşük sadakatli 5 varyant:", ", ".join(f"{g} {s}" for s, g in en_kotu))
    print(f"\nSorunlu cümleler (insan incelemesi için) -> sonuclar/ogretmen_sorunlu{ek}.csv")


if __name__ == "__main__":
    main()
