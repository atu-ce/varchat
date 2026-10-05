"""
BENCHMARK 6 — TOPLU ÜRETİM (adım 9): dondurulmuş arama kaydı üzerinde, aynı ayarlarla, bir modelin özetlerini üretir.

Girdi : degerlendirme/sonuclar/arama_<tarih>.jsonl  (b05: her girdi için seçilen makaleler + kademe; PubMed'e gidilmez)
Çıktı : degerlendirme/sonuclar/uretim_<model>_<tarih>.jsonl  (girdi, katman, kademe, soru, system, cevap, denetimler, süre)
Kaldığı yerden devam eder: aynı model + aynı snapshot için yazılmış en yeni üretim dosyası bulunur ve içindeki girdiler atlanır
(gece yarısını geçen ya da ertesi gün yeniden başlatılan koşu yeni dosyaya sıfırdan BAŞLAMAZ). CPU'da saatler sürer, gece çalıştırılır.

Kullanım: python degerlendirme/b06_toplu_uret.py [model_adi] [--yeni]
  model_adi: varsayılan c04.MODEL; örn. 'varchat' (fine-tune'lu model)
  --yeni   : var olan dosyaya devam etme, yeni tarihli dosya aç (aynı modeli ikinci kez ölçmek için)
Ölçüm (sadakat, atıf, dil) b07'de yapılır; bu betik yalnızca üretir ve c04'ün üretim-sonrası denetim sonuçlarını kaydeder.
"""

import glob
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import c04_varchat_ollama as app
from c06_clinvar import clinvar_bilgisi
from c07_sorgu_kur import varyant_kaydi

BURASI = os.path.dirname(os.path.abspath(__file__))


def uyanik_tut():
    """Windows: bu süreç çalıştığı sürece bilgisayar UYKUYA GEÇMESİN (ekran kapanabilir). Süreç bitince işaret kendiliğinden kalkar.
    Neden: gece koşusu bilgisayar uyuyunca saatlerce durdu (4-5 Ekim). Not: kapak kapatma eylemi 'uyku' ise yine uyuyabilir."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        except Exception:
            pass


def son_snapshot():
    """En son YAZILAN arama kaydı (ad sıralaması değil: aynı gün açılan arama_<tarih>_2.jsonl de doğru seçilsin)."""
    dosyalar = glob.glob(os.path.join(BURASI, "sonuclar", "arama_*.jsonl"))
    if not dosyalar:
        raise SystemExit("Önce b05_arama_dondur.py çalıştırılmalı (arama_<tarih>.jsonl yok).")
    return max(dosyalar, key=os.path.getmtime)


def model_dosya_adi(model):
    return model.replace(":", "-").replace("/", "-")


def cikti_sec(model_ad, snapshot_ad, yeni=False):
    """Devam edilecek üretim dosyası: aynı model + aynı snapshot'la yazılmış en yeni dosya. Yoksa (ya da yeni=True) yeni ad."""
    if not yeni:
        adaylar = sorted(glob.glob(os.path.join(BURASI, "sonuclar", f"uretim_{model_ad}_*.jsonl")), key=os.path.getmtime, reverse=True)
        for yol in adaylar:
            with open(yol, encoding="utf-8") as f:
                ilk = next((l for l in f if l.strip()), None)
            if ilk and json.loads(ilk).get("snapshot") == snapshot_ad:
                return yol
    yol = os.path.join(BURASI, "sonuclar", f"uretim_{model_ad}_{date.today().isoformat()}.jsonl")
    n = 2
    while os.path.exists(yol):
        yol = os.path.join(BURASI, "sonuclar", f"uretim_{model_ad}_{date.today().isoformat()}_{n}.jsonl")
        n += 1
    return yol


def main():
    argv = [a for a in sys.argv[1:] if a != "--yeni"]
    uyanik_tut()
    if argv:
        app.MODEL = argv[0]
    snapshot = son_snapshot()
    satirlar = [json.loads(l) for l in open(snapshot, encoding="utf-8")]
    model_ad = model_dosya_adi(app.MODEL)
    cikti = cikti_sec(model_ad, os.path.basename(snapshot), yeni="--yeni" in sys.argv)
    yapilan = set()
    if os.path.exists(cikti):
        yapilan = {json.loads(l)["girdi"] for l in open(cikti, encoding="utf-8") if l.strip()}
    print(f"model={app.MODEL} | snapshot={os.path.basename(snapshot)} | çıktı={os.path.basename(cikti)} | {len(satirlar)} girdi, "
          f"{len(yapilan)} tamamlanmış | ayarlar={app.AYARLAR}")
    with open(cikti, "a", encoding="utf-8") as f:
        for i, r in enumerate(satirlar, 1):
            girdi = r["girdi"]
            if girdi in yapilan:
                continue
            kayit = {"girdi": girdi, "katman": r["katman"], "kademe": r["kademe"], "model": app.MODEL,
                     "ayarlar": dict(app.AYARLAR), "snapshot": os.path.basename(snapshot), "tarih": date.today().isoformat()}
            if r["kademe"] in ("yok", "hata") or not r["makaleler"]:
                kayit.update(soru=None, cevap=None, not_="kaynak yok")
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); f.flush()
                print(f"[{i}/{len(satirlar)}] {girdi}: kaynak yok, atlandı")
                continue
            gen = (r.get("kayit") or {}).get("gen")
            # ClinVar (çelişki denetimi için) — kayıt paylaşımı için varyant_kaydi (koordinatta VEP'e 1 istek)
            try:
                cv = clinvar_bilgisi(girdi, kayit=varyant_kaydi(girdi))
            except Exception as e:
                cv = None
                print(f"  (ClinVar: {type(e).__name__})")
            app.SON_BAGLAM.clear()
            app.SON_BAGLAM.update(kademe=r["kademe"], gen=gen, varyant=girdi, n_kaynak=len(r["makaleler"]), clinvar=cv)
            sistem = app.sistem_metni(girdi, r["makaleler"], r["kademe"], gen)
            soru = app.ilk_soru(girdi)
            t = time.time()
            try:
                cevap = app.grounded_sor([{"role": "system", "content": sistem}], soru)
            except Exception as e:
                print(f"[{i}/{len(satirlar)}] {girdi}: ÜRETİM HATASI {type(e).__name__}: {e}")
                continue
            sure = round(time.time() - t, 1)
            kayit.update(soru=soru, sistem=sistem, cevap=cevap, denetim=dict(app.SON_YANIT), sure_s=sure,
                         clinvar_onem=((cv or {}).get("germline") or {}).get("onem"),
                         pmidler=[m["pmid"] for m in r["makaleler"]], alaka=[m.get("alaka") for m in r["makaleler"]])
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); f.flush()
            d = app.SON_YANIT
            print(f"[{i}/{len(satirlar)}] {girdi:34} {sure:6.0f}s | {r['kademe']:7} | cümle {d.get('cumle')} atıfsız {d.get('atifsiz_cumle')} "
                  f"geçersiz {d.get('gecersiz_atif')} cjk {d.get('cjk_orani')} çelişki {'VAR' if d.get('celiski') else '-'}")
    print(f"Bitti -> {cikti}")


if __name__ == "__main__":
    main()
