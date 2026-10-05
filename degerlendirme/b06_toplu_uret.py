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
from c07_sorgu_kur import model_etiketi, varyant_kaydi

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


def model_kaynakli_hata(hata):
    """Kayıtlı bir üretim hatası MODELİN başarısızlığı mı (ölçüme sayılır), yoksa kurulum/bağlantı hatası mı (sayılmaz)?
    Model tarafı: Ollama'nın tekrar döngüsünü kesmesi ('token repeat limit reached', 'prediction aborted')."""
    h = (hata or "").lower()
    return "repeat" in h or "prediction aborted" in h


def istem(r):
    """Bir arama kaydı satırı için modele gidecek (system, ilk soru). Canlı uygulamayla aynı fonksiyonlar; varyant adı model_etiketi."""
    gen = (r.get("kayit") or {}).get("gen")
    etiket = model_etiketi(dict(r.get("kayit") or {}, girdi=r["girdi"]), r["girdi"])
    app.SON_BAGLAM.clear()
    app.SON_BAGLAM.update(kademe=r["kademe"], gen=gen, varyant=r["girdi"], etiket=etiket, n_kaynak=len(r["makaleler"]))
    return app.sistem_metni(etiket, r["makaleler"], r["kademe"], gen), app.ilk_soru(etiket)


def main():
    argv = [a for a in sys.argv[1:] if a != "--yeni"]
    uyanik_tut()
    if argv:
        app.MODEL = argv[0]
    snapshot = son_snapshot()
    satirlar = [json.loads(l) for l in open(snapshot, encoding="utf-8")]
    model_ad = model_dosya_adi(app.MODEL)
    try:                                                   # model kurulu değilse hiçbir satır yazmadan dur
        app.ollama.show(app.MODEL)
    except app.ollama.ResponseError as e:
        raise SystemExit(f"DURDU: '{app.MODEL}' Ollama'da bulunamadı ({e}). Önce modeli oluştur ('ollama list' ile kontrol et).")
    cikti = cikti_sec(model_ad, os.path.basename(snapshot), yeni="--yeni" in sys.argv)
    yapilan = set()
    if os.path.exists(cikti):
        # İstemi (system + soru) bugünkü kodla DEĞİŞMİŞ satırlar yeniden üretilir: iki model aynı istemlerle ölçülmeli
        # (5 Ekim: koordinat/rsID girdilerinde modele verilen varyant adı değişti)
        bekleyen = {r["girdi"]: istem(r) for r in satirlar}
        onceki = [json.loads(l) for l in open(cikti, encoding="utf-8") if l.strip()]
        gecerli = [k for k in onceki if (k.get("soru") is None or (k.get("sistem"), k.get("soru")) == bekleyen.get(k["girdi"]))
                   and (not k.get("hata") or model_kaynakli_hata(k["hata"]))]      # 'model bulunamadı' gibi kurulum hataları silinir
        if len(gecerli) != len(onceki):
            print(f"  ({len(onceki) - len(gecerli)} satırın istemi değişmiş ya da kurulum hatasıyla kaydedilmiş; bu satırlar yeniden üretilecek)")
            with open(cikti, "w", encoding="utf-8") as f:
                for k in gecerli:
                    f.write(json.dumps(k, ensure_ascii=False) + "\n")
        yapilan = {k["girdi"] for k in gecerli}
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
            sistem, soru = istem(r)
            app.SON_BAGLAM["clinvar"] = cv
            t = time.time()
            try:
                cevap = app.grounded_sor([{"role": "system", "content": sistem}], soru)
            except app.ollama.ResponseError as e:
                if not model_kaynakli_hata(str(e)):
                    # Ör. 'model not found' (404): model Ollama'da yok, kurulum hatası. Kaydetmeden DUR (5 Ekim: 56 satır boşa yazılmıştı)
                    raise SystemExit(f"DURDU: {app.MODEL} için Ollama hatası: {e}. Model Ollama'da kurulu mu? ('ollama list' ile bak)")
                # Model tarafı hata (ör. iki denemede de tekrar döngüsü): modelin başarısızlığıdır, KAYDEDİLİR ve ölçüme sayılır
                print(f"[{i}/{len(satirlar)}] {girdi}: ÜRETİM HATASI (model) {e}")
                kayit.update(soru=soru, sistem=sistem, cevap=None, hata=str(e)[:200], denetim=dict(app.SON_YANIT),
                             sure_s=round(time.time() - t, 1), pmidler=[m["pmid"] for m in r["makaleler"]])
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); f.flush()
                continue
            except Exception as e:
                # Bağlantı / sunucu kesintisi: kaydedilmez, betik yeniden çalıştırılınca bu girdi tekrar denenir
                print(f"[{i}/{len(satirlar)}] {girdi}: ÜRETİM HATASI {type(e).__name__}: {e} (yeniden çalıştırınca tekrar denenecek)")
                continue
            sure = round(time.time() - t, 1)
            kayit.update(etiket=app.SON_BAGLAM.get("etiket"), soru=soru, sistem=sistem, cevap=cevap, denetim=dict(app.SON_YANIT), sure_s=sure,
                         clinvar_onem=((cv or {}).get("germline") or {}).get("onem"),
                         pmidler=[m["pmid"] for m in r["makaleler"]], alaka=[m.get("alaka") for m in r["makaleler"]])
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); f.flush()
            d = app.SON_YANIT
            print(f"[{i}/{len(satirlar)}] {girdi:34} {sure:6.0f}s | {r['kademe']:7} | cümle {d.get('cumle')} atıfsız {d.get('atifsiz_cumle')} "
                  f"geçersiz {d.get('gecersiz_atif')} cjk {d.get('cjk_orani')} çelişki {'VAR' if d.get('celiski') else '-'}")
    print(f"Bitti -> {cikti}")


if __name__ == "__main__":
    main()
