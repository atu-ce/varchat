"""
BENCHMARK 7 — İDDİA DÜZEYİNDE SADAKAT (faithfulness) + çıktı metrikleri (adım 9).

Girdi : degerlendirme/sonuclar/uretim_<model>_<tarih>.jsonl (b06) + arama_<tarih>.jsonl (kaynak metinleri)
Yöntem (RAGAS'ın sadakat fikri, yerel yargıçla):
  1) Cevap cümlelere bölünür. Ret cümlesi ("...bilgi yok.") atlanır.
  2) Atıfsız cümle -> ATIFSIZ (yargılanmaz, ayrı sayılır).
  3) Atıflı cümle -> atıf yaptığı kaynak(lar)ın başlık+özeti ile birlikte YARGIÇ modele sorulur:
     DESTEKLENIYOR / DESTEKLENMIYOR / CELISIYOR  (JSON, sıcaklık 0)
  4) Sadakat = DESTEKLENIYOR / yargılanan iddia; çelişki oranı ayrı (tıpta en ağır hata).
Ek metrikler (b06'nın denetimlerinden): atıfsız cümle oranı, geçersiz atıf sayısı, yabancı alfabe oranı, kesilme, süre.
Yargıç varsayılan olarak c04.MODEL (aynı model kendini yargılar — bilinen zayıflık; --yargic ile başka model verilebilir).
İnsan kontrolü için 30 rastgele iddia sonuclar/insan_kontrol_<tarih>.csv'ye boş etiket sütunuyla yazılır (kappa için).

Kaynak metinleri, üretim satırının kendi 'snapshot' alanındaki arama kaydından okunur (en yeni arama dosyasından DEĞİL);
satırın PMID listesi o kayıtla uyuşmazsa satır yargılanmaz (atıf numarası başka makaleye eşlenmesin).

Kullanım: python degerlendirme/b07_sadakat.py [uretim_dosyasi] [--model MODEL] [--yargic MODEL]
  uretim_dosyasi yoksa: --model verilmişse o modelin, verilmemişse herhangi bir modelin EN SON YAZILAN üretim dosyası.
"""

import csv
import glob
import json
import os
import random
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import ollama

import c04_varchat_ollama as app

BURASI = os.path.dirname(os.path.abspath(__file__))
KARARLAR = ("DESTEKLENIYOR", "DESTEKLENMIYOR", "CELISIYOR")

YARGIC_SISTEM = (
    "Sen titiz bir bilimsel yargıçsın. Sana bir ya da birkaç makale özeti (KAYNAK) ve tek bir İDDİA verilecek. "
    "Görevin: iddianın YALNIZCA verilen kaynak metnine dayanıp dayanmadığını söylemek. Kendi bilgini kullanma.\n"
    "- DESTEKLENIYOR: iddiadaki bilgi kaynakta açıkça var (çeviri/ifade farkı sorun değil).\n"
    "- DESTEKLENMIYOR: iddia kaynakta yok ya da kaynaktan çıkarılamıyor.\n"
    "- CELISIYOR: kaynak iddianın tersini söylüyor (örn. 'riski artırır' vs 'azaltır', 'neden olur' vs 'korur').\n"
    'Yalnızca şu JSON ile cevap ver: {"karar": "DESTEKLENIYOR|DESTEKLENMIYOR|CELISIYOR", "gerekce": "<bir cümle>"}'
)
# Yargıç sürümü: 2 (5 Ekim) = model hatasında ('token repeat limit reached') ya da geçersiz JSON'da bir kez sıcaklık 0.3 / tohum+1
# ile yeniden dener, yine olmazsa BELIRSIZ ('yargıç hatası') yazar ve devam eder. Başka sürümle yargılanmış satırlar yeniden yargılanır.
YARGIC_SURUMU = 2
YARGIC_AYARLARI = dict(app.AYARLAR, num_predict=256)     # karar + tek cümle gerekçe yeter; döngüye girerse erken kesilsin


def uyanik_tut():
    """Windows: bu süreç çalıştığı sürece bilgisayar UYKUYA GEÇMESİN (ekran kapanabilir). Süreç bitince işaret kendiliğinden kalkar.
    Neden: gece koşusu bilgisayar uyuyunca saatlerce durdu (4-5 Ekim). Not: kapak kapatma eylemi 'uyku' ise yine uyuyabilir."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        except Exception:
            pass


def son_dosya(desen):
    """En son yazılan dosya (ad sıralaması model adını tarihten önce karşılaştırdığı için yanlış dosyayı seçebilirdi)."""
    d = glob.glob(os.path.join(BURASI, "sonuclar", desen))
    return max(d, key=os.path.getmtime) if d else None


def kaynak_haritasi(snapshot_yolu):
    """girdi -> [makale sözlükleri] (snapshot'tan)."""
    h = {}
    for l in open(snapshot_yolu, encoding="utf-8"):
        r = json.loads(l)
        h[r["girdi"]] = r["makaleler"]
    return h


def yargila(iddia, kaynaklar, model):
    """(karar, gerekçe, deneme). deneme 0 = ilk deneme, 1 = yeniden denemede karar verdi, 2 = iki deneme de başarısız.
    Model hatası (Ollama 'token repeat limit reached') ya da geçersiz JSON betiği DURDURMAZ: bir kez farklı tohumla yeniden denenir,
    yine olmazsa iddia BELIRSIZ sayılır (sadakat paydasına girmez, 'yargıç hatası' olarak ayrıca raporlanır)."""
    metin = "\n\n".join(f"KAYNAK [{n}]: {m['baslik']}\n{m['ozet']}" for n, m in kaynaklar)
    mesajlar = [{"role": "system", "content": YARGIC_SISTEM},
                {"role": "user", "content": f"{metin}\n\nİDDİA: {iddia}\n\nKarar?"}]
    denemeler = (YARGIC_AYARLARI, dict(YARGIC_AYARLARI, temperature=0.3, seed=YARGIC_AYARLARI["seed"] + 1))
    sorun = None
    for deneme, ayar in enumerate(denemeler):
        try:
            cevap = ollama.chat(model=model, format="json", options=ayar, messages=mesajlar)
            j = json.loads(cevap["message"]["content"])
        except ollama.ResponseError as e:
            sorun = f"model hatası: {str(e)[:100]}"
            continue
        except (json.JSONDecodeError, KeyError, TypeError):
            sorun = "geçersiz JSON"
            continue
        if not isinstance(j, dict):
            sorun = "geçersiz JSON"
            continue
        karar = str(j.get("karar", "")).upper().replace("İ", "I").replace("Ş", "S").replace("Ç", "C")
        karar = next((k for k in KARARLAR if k in karar), "BELIRSIZ")
        return karar, str(j.get("gerekce", ""))[:300], deneme
    return "BELIRSIZ", f"yargıç hatası ({sorun})", len(denemeler)


def main():
    argv = sys.argv[1:]
    uyanik_tut()
    yargic = app.MODEL
    if "--yargic" in argv:
        i = argv.index("--yargic"); yargic = argv[i + 1]; del argv[i:i + 2]
    model = None
    if "--model" in argv:
        i = argv.index("--model"); model = argv[i + 1]; del argv[i:i + 2]
    desen = f"uretim_{model.replace(':', '-').replace('/', '-')}_*.jsonl" if model else "uretim_*.jsonl"
    uretim = argv[0] if argv else son_dosya(desen)
    if not uretim:
        raise SystemExit(f"{desen} (b06 çıktısı) bulunamadı.")
    satirlar = [json.loads(l) for l in open(uretim, encoding="utf-8") if l.strip()]
    haritalar = {}

    def kaynaklar_icin(r):
        """Satırın üretildiği snapshot'taki makaleler; snapshot yoksa ya da PMID listesi uyuşmazsa None."""
        ad = r.get("snapshot")
        yol = os.path.join(BURASI, "sonuclar", ad) if ad else None
        if not yol or not os.path.exists(yol):
            print(f"  UYARI: {r['girdi']}: snapshot dosyası yok ({ad}); atlandı")
            return None
        if yol not in haritalar:
            haritalar[yol] = kaynak_haritasi(yol)
        mk = haritalar[yol].get(r["girdi"], [])
        if r.get("pmidler") and r["pmidler"] != [m["pmid"] for m in mk]:
            print(f"  UYARI: {r['girdi']}: üretimdeki PMID'ler snapshot'la uyuşmuyor; atlandı")
            return None
        return mk
    etiket = os.path.basename(uretim).replace("uretim_", "").replace(".jsonl", "")
    cikti = os.path.join(BURASI, "sonuclar", f"sadakat_{etiket}.jsonl")
    yapilan = set()
    if os.path.exists(cikti):
        onceki = [json.loads(l) for l in open(cikti, encoding="utf-8") if l.strip()]
        gecerli = [h for h in onceki if h.get("yargic_surumu") == YARGIC_SURUMU]
        if len(gecerli) != len(onceki):                       # tüm girdiler AYNI yargıç sürümüyle puanlanmalı
            print(f"  ({len(onceki) - len(gecerli)} satır eski yargıç sürümüyle yargılanmıştı; yeniden yargılanacak)")
            with open(cikti, "w", encoding="utf-8") as f:
                for h in gecerli:
                    f.write(json.dumps(h, ensure_ascii=False) + "\n")
        yapilan = {h["girdi"] for h in gecerli}
    print(f"üretim={os.path.basename(uretim)} | yargıç={yargic} (sürüm {YARGIC_SURUMU}) | {len(satirlar)} satır, {len(yapilan)} yargılanmış")
    with open(cikti, "a", encoding="utf-8") as f:
        for r in satirlar:
            if r["girdi"] in yapilan or not r.get("cevap"):
                continue
            mk = kaynaklar_icin(r)
            if mk is None:
                continue
            iddialar = []
            for c in app.cumlelere_bol(r["cevap"]):
                if c == app.RET_CEVAP or len(c.split()) < 4:
                    continue
                nums = sorted({n for n in app.atif_numaralari(c) if 1 <= n <= len(mk)})
                if not nums:
                    iddialar.append({"iddia": c, "atif": [], "karar": "ATIFSIZ", "gerekce": ""})
                    continue
                karar, gerekce, deneme = yargila(app.ATIF.sub("", c).strip(), [(n, mk[n - 1]) for n in nums], yargic)
                iddialar.append({"iddia": c, "atif": nums, "karar": karar, "gerekce": gerekce, "deneme": deneme})
            yarg = [i for i in iddialar if i["karar"] in KARARLAR]
            ozet = {
                "n_cumle": len(iddialar), "atifsiz": sum(i["karar"] == "ATIFSIZ" for i in iddialar),
                "desteklenen": sum(i["karar"] == "DESTEKLENIYOR" for i in iddialar),
                "desteklenmeyen": sum(i["karar"] == "DESTEKLENMIYOR" for i in iddialar),
                "celisen": sum(i["karar"] == "CELISIYOR" for i in iddialar),
                "belirsiz": sum(i["karar"] == "BELIRSIZ" for i in iddialar),
                "yargic_hatasi": sum(1 for i in iddialar if i["gerekce"].startswith("yargıç hatası")),
                "yeniden_denenen": sum(1 for i in iddialar if i.get("deneme") == 1),
                "sadakat": round(sum(i["karar"] == "DESTEKLENIYOR" for i in yarg) / len(yarg), 3) if yarg else None,
            }
            kayit = {"girdi": r["girdi"], "katman": r["katman"], "kademe": r["kademe"], "model": r["model"], "yargic": yargic,
                     "yargic_surumu": YARGIC_SURUMU,
                     "yargic_ayarlari": {k: YARGIC_AYARLARI.get(k) for k in ("temperature", "seed", "num_predict", "num_ctx")},
                     "snapshot": r.get("snapshot"), "uretim": os.path.basename(uretim),
                     "iddialar": iddialar, "ozet": ozet, "denetim": r.get("denetim"), "sure_s": r.get("sure_s"), "tarih": date.today().isoformat()}
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); f.flush()
            print(f"{r['girdi']:34} {r['kademe']:7} cümle {ozet['n_cumle']} | destek {ozet['desteklenen']} yok {ozet['desteklenmeyen']} "
                  f"çelişki {ozet['celisen']} atıfsız {ozet['atifsiz']} belirsiz {ozet['belirsiz']} | sadakat {ozet['sadakat']}")
    # ---- özet tablo ----
    hepsi = [json.loads(l) for l in open(cikti, encoding="utf-8") if l.strip()]
    tablo = {}
    for k in sorted({h["katman"] for h in hepsi}) + ["TÜMÜ"]:
        alt = [h for h in hepsi if k == "TÜMÜ" or h["katman"] == k]
        y = sum(h["ozet"]["desteklenen"] + h["ozet"]["desteklenmeyen"] + h["ozet"]["celisen"] for h in alt)
        c = sum(h["ozet"]["n_cumle"] for h in alt)
        tablo[k] = {"girdi": len(alt), "iddia": y,
                    "sadakat": round(sum(h["ozet"]["desteklenen"] for h in alt) / y, 3) if y else None,
                    "celiski_orani": round(sum(h["ozet"]["celisen"] for h in alt) / y, 3) if y else None,
                    "atifsiz_orani": round(sum(h["ozet"]["atifsiz"] for h in alt) / c, 3) if c else None,
                    "gecersiz_atif": sum(len((h.get("denetim") or {}).get("gecersiz_atif") or []) for h in alt),
                    "cjk_bozuk": sum(1 for h in alt if ((h.get("denetim") or {}).get("cjk_orani") or 0) > 0.02),
                    "kesilen": sum(1 for h in alt if (h.get("denetim") or {}).get("bitis") == "length"),
                    "bozuk": sum(1 for h in alt if (h.get("denetim") or {}).get("bozuk")),
                    "belirsiz": sum(h["ozet"]["belirsiz"] for h in alt),
                    "yargic_hatasi": sum(h["ozet"].get("yargic_hatasi", 0) for h in alt),
                    "uretim_hatasi": sum(1 for r in satirlar if r.get("hata") and (k == "TÜMÜ" or r["katman"] == k)),
                    "ort_sure_s": round(sum(h.get("sure_s") or 0 for h in alt) / len(alt), 1) if alt else None}
    ozet_yolu = os.path.join(BURASI, "sonuclar", f"sadakat_ozet_{etiket}.json")
    json.dump({"uretim": os.path.basename(uretim), "yargic": yargic, "tablo": tablo}, open(ozet_yolu, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nKATMAN ÖZETİ")
    for k, v in tablo.items():
        print(f"  {k:18} n={v['girdi']:2} iddia={v['iddia']:3} sadakat={v['sadakat']} çelişki={v['celiski_orani']} atıfsız={v['atifsiz_orani']} "
              f"geçersiz={v['gecersiz_atif']} cjk={v['cjk_bozuk']} kesilen={v['kesilen']} belirsiz={v['belirsiz']} "
              f"yargıç hatası={v['yargic_hatasi']} üretim hatası={v['uretim_hatasi']} süre={v['ort_sure_s']}s")
    # ---- insan kontrolü örneklemi ----
    havuz = [(h["girdi"], i) for h in hepsi for i in h["iddialar"] if i["karar"] in KARARLAR]
    random.Random(42).shuffle(havuz)
    insan_yolu = os.path.join(BURASI, "sonuclar", f"insan_kontrol_{etiket}.csv")
    with open(insan_yolu, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["girdi", "iddia", "atif", "yargic_karari", "yargic_gerekcesi", "INSAN_KARARI (DESTEKLENIYOR/DESTEKLENMIYOR/CELISIYOR)", "not"])
        for g, i in havuz[:30]:
            w.writerow([g, i["iddia"], ",".join(map(str, i["atif"])), i["karar"], i["gerekce"], "", ""])
    print(f"Özet -> {ozet_yolu}\nİnsan kontrolü (30 iddia) -> {insan_yolu}")


if __name__ == "__main__":
    main()
