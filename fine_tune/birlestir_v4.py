"""
FINE-TUNE v4 — BİRLEŞTİRME: v3'ün 204 örneği (denetlenmiş ve düzeltilmiş) + v4 yeni örnekler -> egitim_verisi.jsonl

Girdiler (hepsi fine_tune/ altında):
  egitim_verisi_v3.jsonl  v3'ün 204 örneği (değişmez kopya; yoksa mevcut egitim_verisi.jsonl'dan bir kez oluşturulur)
  denetim_v3.json         v3 denetim kararları (index başına): AYNEN | DUZELTILDI | SIL | RET_DOGRU | RET_YANLIS
  kaynaklar_v4.jsonl      yeni girdilerin kaynakları + canlı sistemle AYNI system mesajı ve ilk soru (kaynak_topla_v4.py)
  yeni_ornekler_v4.jsonl  yeni girdiler için öğretmen cevapları (doğrulanmış): ozet, takip, cok_turlu, ret_kapsam, gen_ret
Çıktı: egitim_verisi.jsonl (v4; Colab defteri bunu okur). Her satır: messages, varyant, bolme, tur, surum ('v3'|'v4'), bicim, alan.

Kurallar:
  - v3 düzeltilmiş örnek: son asistan cevabı denetimdeki düzeltilmiş metinle değişir. Çok turlu örneklerde ÖNCEKİ özet de aynı
    varyantın düzeltilmiş özetiyle değişir; özet silindiyse o varyantın çok turlu örnekleri de çıkarılır.
  - RET_YANLIS: kaynak soruyu aslında cevaplıyorsa denetçinin yazdığı kaynaklı cevapla 'takip' örneğine dönüşür.
  - Yeni 'ret_yabanci': yeni girdilerin yarısına, AYNI bölmeden başka bir yeni girdinin takip sorusu -> "bilgi yok". Soru o girdinin
    genini, değişimini ya da rsID'sini AÇIKÇA anmalı ve bunların hiçbiri bu girdinin kaynaklarında geçmemeli (adsız "bu varyant ..."
    soruları başka bağlamda cevaplanabilir olduğu için kullanılmaz).
  - Bölme gen bazlı: v3 doğrulama genleri + yeni girdilerden VAL_YENI genleri doğrulamaya.

Kullanım: python fine_tune/birlestir_v4.py
"""

import collections
import json
import os
import random
import re
import shutil

BURASI = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(BURASI, "egitim_verisi_v3.jsonl")
DENETIM = os.path.join(BURASI, "denetim_v3.json")
KAYNAK_V4 = os.path.join(BURASI, "kaynaklar_v4.jsonl")
YENI = os.path.join(BURASI, "yeni_ornekler_v4.jsonl")
CIKTI = os.path.join(BURASI, "egitim_verisi.jsonl")

RET_CEVAP = "Bu konuda elimdeki kaynaklarda bilgi yok."
VAL_GENLER_V3 = {"AKT1", "DNMT3A", "HFE", "HRAS", "IDH2", "MYD88"}
VAL_YENI = {"LRRK2", "MEFV", "CALR", "ALDH2", "RHO", "PCSK9", "NF1", "SCN1A"}   # yeni girdilerden doğrulamaya (~%10)
MAX_TOKEN_TAHMIN = 4800        # Colab defterinde MAX_LEN 4608. Karakter/3.2 tahmini v3'te gerçeği ~%9 aşıyordu (tahmin 4287 / gerçek
                               # 3929 token): 4800 tahmin ≈ 4400 gerçek token, MAX_LEN'in altında güvenlik payı


def gecer_mi(sembol, metin):
    return bool(sembol) and re.search(rf"(?<![A-Za-z0-9]){re.escape(sembol)}(?![A-Za-z0-9])", metin, re.I) is not None


def varyant_adlari(kay):
    """Bir girdinin soruda anılabilecek adları: gen, değişim (etiketin 2. parçası) ve rsID'ler."""
    parcalar = kay["etiket"].split()
    degisim = parcalar[1] if len(parcalar) > 1 and not parcalar[1].startswith("(") else ""
    return [a for a in [kay["gen"], degisim, *re.findall(r"rs\d+", kay["etiket"])] if a]


def token_tahmini(messages):
    return int(sum(len(m["content"]) for m in messages) / 3.2) + 6 * len(messages)


def bolme(gen):
    return "val" if (gen or "").upper() in (VAL_GENLER_V3 | VAL_YENI) else "train"


def v3_yukle():
    if not os.path.exists(V3):
        shutil.copy(CIKTI, V3)                       # ilk çalıştırmada v3'ün değişmez kopyası
        print(f"(v3 kopyası oluşturuldu: {os.path.basename(V3)})")
    return [json.loads(l) for l in open(V3, encoding="utf-8") if l.strip()]


def v3_isle(satirlar, kararlar, sayac):
    """Denetim kararlarını uygular; (çıktı satırları, silinen özet varyantları)."""
    duzelt_ozet, silinen_ozet = {}, set()
    for i, r in enumerate(satirlar):
        k = kararlar.get(i)
        if r["tur"] == "ozet" and k:
            if k["karar"] == "DUZELTILDI" and k.get("duzeltilmis_cevap"):
                duzelt_ozet[r["varyant"]] = k["duzeltilmis_cevap"].strip()
            elif k["karar"] == "SIL":
                silinen_ozet.add(r["varyant"])
    cikti = []
    for i, r in enumerate(satirlar):
        k = kararlar.get(i)
        if k is None:
            raise SystemExit(f"v3 örnek {i} için denetim kararı yok")
        msgs = [dict(m) for m in r["messages"]]
        tur = r["tur"]
        if k["karar"] == "SIL":
            sayac["v3_silinen"] += 1
            continue
        if k["karar"] == "DUZELTILDI":
            msgs[-1]["content"] = k["duzeltilmis_cevap"].strip()
            sayac["v3_duzeltilen"] += 1
        elif k["karar"] == "RET_YANLIS":
            if not (k.get("duzeltilmis_cevap") or "").strip():
                sayac["v3_silinen"] += 1
                continue
            msgs[-1]["content"] = k["duzeltilmis_cevap"].strip()
            tur = "takip"                                   # kaynak soruyu cevaplıyor: ret değil, kaynaklı cevap örneği
            sayac["v3_ret_cevaba_donen"] += 1
        else:
            sayac["v3_ret_dogru" if k["karar"] == "RET_DOGRU" else "v3_aynen"] += 1
        if tur == "takip_cok_turlu":
            if r["varyant"] in silinen_ozet:
                sayac["v3_silinen"] += 1
                continue
            if r["varyant"] in duzelt_ozet:
                msgs[2]["content"] = duzelt_ozet[r["varyant"]]
        cikti.append({"messages": msgs, "varyant": r["varyant"], "bolme": r["bolme"], "tur": tur, "surum": "v3",
                      "bicim": "gen_degisim", "alan": "kanser/çeşitli"})
    return cikti


def v4_yeni(kaynaklar, yeni, sayac):
    cikti, takip_havuzu = [], []
    for g, kay in kaynaklar.items():
        o = yeni.get(g)
        if not o:
            continue
        sistem, ilk = kay["sistem"], kay["ilk_soru"]
        b = bolme(kay["gen"])
        ortak = {"varyant": g, "bolme": b, "surum": "v4", "bicim": kay["bicim"], "alan": kay["alan"]}

        def ekle(tur, mesajlar):
            cikti.append(dict(ortak, messages=mesajlar, tur=tur))

        if o.get("ozet"):
            ekle("ozet", [{"role": "system", "content": sistem}, {"role": "user", "content": ilk},
                          {"role": "assistant", "content": o["ozet"].strip()}])
        for t in o.get("takip") or []:
            ekle("takip", [{"role": "system", "content": sistem}, {"role": "user", "content": t["soru"].strip()},
                           {"role": "assistant", "content": t["cevap"].strip()}])
            takip_havuzu.append((g, kay, t["soru"].strip()))
        c = o.get("cok_turlu")
        if c and o.get("ozet"):
            ekle("takip_cok_turlu", [{"role": "system", "content": sistem}, {"role": "user", "content": ilk},
                                     {"role": "assistant", "content": o["ozet"].strip()},
                                     {"role": "user", "content": c["soru"].strip()}, {"role": "assistant", "content": c["cevap"].strip()}])
        for soru in o.get("ret_kapsam") or []:
            ekle("ret_kapsam_disi", [{"role": "system", "content": sistem}, {"role": "user", "content": soru.strip()},
                                     {"role": "assistant", "content": RET_CEVAP}])
        for j, soru in enumerate(o.get("gen_ret") or []):
            if j == 0 and o.get("ozet"):              # gen özetinden hemen sonra varyantı sormak: canlı kullanımın en olası akışı
                ekle("ret_gen_duzeyi_cok_turlu", [{"role": "system", "content": sistem}, {"role": "user", "content": ilk},
                                                  {"role": "assistant", "content": o["ozet"].strip()},
                                                  {"role": "user", "content": soru.strip()}, {"role": "assistant", "content": RET_CEVAP}])
            else:
                ekle("ret_gen_duzeyi", [{"role": "system", "content": sistem}, {"role": "user", "content": soru.strip()},
                                        {"role": "assistant", "content": RET_CEVAP}])
    # ret_yabanci: yeni girdilerin yarısı, aynı bölmeden başka girdinin takip sorusu
    rng = random.Random(42)
    kullanilan = set()
    for j, (g, kay) in enumerate(sorted(kaynaklar.items())):
        if j % 2 or g not in yeni:
            continue
        metin = kay["sistem"].split("KAYNAKLAR:", 1)[-1]
        adaylar = []
        for g2, kay2, soru in takip_havuzu:
            if g2 == g or soru in kullanilan or bolme(kay2["gen"]) != bolme(kay["gen"]) or kay2["gen"].upper() == kay["gen"].upper():
                continue
            adlar = varyant_adlari(kay2)
            # Soru yabancı varyantı ADIYLA anmalı: "bu varyant ..." gibi adsız bir soru başka bağlamda cevaplanabilir hâle gelir
            # (o zaman "bilgi yok" yanlış olur). Adların hiçbiri bu girdinin kaynaklarında geçmemeli.
            if not any(gecer_mi(a, soru) for a in adlar) or any(gecer_mi(a, metin) for a in adlar):
                continue
            adaylar.append(soru)
        if adaylar:
            soru = rng.choice(adaylar)
            kullanilan.add(soru)
            cikti.append({"varyant": g, "bolme": bolme(kay["gen"]), "surum": "v4", "bicim": kay["bicim"], "alan": kay["alan"], "tur": "ret_yabanci",
                          "messages": [{"role": "system", "content": kay["sistem"]}, {"role": "user", "content": soru},
                                       {"role": "assistant", "content": RET_CEVAP}]})
    return cikti


def main():
    sayac = collections.Counter()
    v3 = v3_yukle()
    kararlar = {int(k["index"]): k for k in json.load(open(DENETIM, encoding="utf-8"))["ornekler"]}
    eski = v3_isle(v3, kararlar, sayac)
    kaynaklar = {json.loads(l)["girdi"]: json.loads(l) for l in open(KAYNAK_V4, encoding="utf-8") if l.strip()}
    yeni = {json.loads(l)["girdi"]: json.loads(l) for l in open(YENI, encoding="utf-8") if l.strip()}
    eksik = sorted(set(kaynaklar) - set(yeni))
    yeni_satirlar = v4_yeni(kaynaklar, yeni, sayac)
    hepsi = eski + yeni_satirlar
    uzun = [(s["varyant"], s["tur"], token_tahmini(s["messages"])) for s in hepsi if token_tahmini(s["messages"]) > MAX_TOKEN_TAHMIN]
    if uzun:
        print(f"UYARI: tahmini {MAX_TOKEN_TAHMIN} token üstü {len(uzun)} örnek ÇIKARILDI: {uzun[:5]}")
        hepsi = [s for s in hepsi if token_tahmini(s["messages"]) <= MAX_TOKEN_TAHMIN]
    with open(CIKTI, "w", encoding="utf-8") as f:
        for s in hepsi:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    tur = collections.Counter(s["tur"] for s in hepsi)
    print(f"v3: aynen {sayac['v3_aynen']}, ret doğru {sayac['v3_ret_dogru']}, düzeltilen {sayac['v3_duzeltilen']}, ret->cevap {sayac['v3_ret_cevaba_donen']}, silinen {sayac['v3_silinen']} "
          f"-> {len(eski)} örnek")
    print(f"v4 yeni: {len(yeni_satirlar)} örnek ({len(yeni)} girdi; cevabı olmayan girdi: {eksik or 'yok'})")
    print(f"TOPLAM {len(hepsi)} örnek -> {os.path.basename(CIKTI)}")
    print("tür:", dict(tur))
    print("bölme:", dict(collections.Counter(s["bolme"] for s in hepsi)), "| sürüm:", dict(collections.Counter(s["surum"] for s in hepsi)))
    print("biçim:", dict(collections.Counter(s["bicim"] for s in hepsi)))
    print("alan:", dict(collections.Counter(s["alan"] for s in hepsi)))
    print("en uzun örnek (tahmini token):", max(token_tahmini(s["messages"]) for s in hepsi))


if __name__ == "__main__":
    main()
