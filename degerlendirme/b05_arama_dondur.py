"""
BENCHMARK 5 — ARAMAYI DONDUR + RETRIEVAL ÖLÇÜMÜ (adım 8, v3 — 4 Ekim düzeltmeleri).

Her test girdisi için c07.kaynaklari_getir'in sonucunu (sorgu, çeviri, sayılar, kademe, seçilen makalelerin PMID/başlık/özet/etiket)
VE eski hattın (v1) sonucunu tarih damgasıyla kaydeder; ölçümler bir daha canlı PubMed'e gitmez (kayma %17/47 gün ölçüldü).
v1 = git b87d8a8 sürümündeki kod BİREBİR (degerlendirme/eski_hat/): koordinat -> VEP region ucu -> ALFABETİK ilk gen adı;
'GRCh37:' öneki eski kodda çöker -> ham metin aranır; diğer girdiler ham metin; 'özet yok' makaleler elenmez.
Ağ kesintisi (429/5xx/zaman aşımı) eski kodun davranışı değildir: iki hatta da 3 deneme yapılır, kalıcı hata satıra yazılır.
PubTator3 anotasyonları, v1 makalelerinin başlık+özeti ve her makalenin hangi kaynakla doğru sayıldığı kayda yazılır.

Ölçüm (b04'ün doğru cevap listesine karşı; A/B/C katmanları) — iki hat için AYNI tanımlar:
  - P@5             : ilk 5'in kaçı doğru / 5 (payda SABİT; eksik sonuç = yanlış, kullanıcıya 5 kaynak vaadi)
  - kesinlik(dönen) : doğru / dönen (yalnızca dönen makaleler; az döndürmek cezalandırılmaz)
  - doğru (oto)     : LitVar2 listesinde ∪ PubTator3 o makalede varyantı etiketlemiş (rsID / protein / cDNA / eski ad) ∪ kürasyon PMID'i
  - doğru (hakem)   : oto ∪ insan hakem kararı (degerlendirme/hakem.jsonl; yoksa hakemli sütun = oto)
  - recall5_sinirli : yalnız LitVar ∪ kürasyon listesindeki isabetler / min(|liste|, 5)  (PubTator-only isabet recall'a girmez)
  - gen_etiketli_dogru: sistemin 'gen düzeyi' dediği ama listede doğru sayılan makaleler (liste tam metinden, sistem özetten okur)
  Otomatik doğru cevap listesi bir ALT SINIRDIR (tmVar 'GNASR201C', 'c-MetD1228N' gibi bitişik yazımları kaçırır);
  iki hattın da 'varyant' etiketli ama listede olmayan makaleleri hakem_adaylari_<etiket>.jsonl'a yazılır (insan kararı için;
  v1 makaleleri c07.alaka_etiketi ile aynı kuralla etiketlenir).
D katmanı (doğru cevap listesi yok): ölçü P@5 değil BEKLENEN KADEME (test_seti.BEKLENEN_KADEME): varyanta özgü iddia yapılmaması
  (kademe gen/yok = doğru); 'yanlış varyant iddiası' (kademe varyant) sayılır.

Kullanım:
  python degerlendirme/b05_arama_dondur.py                         canlı: aramayı dondur + ölç
  python degerlendirme/b05_arama_dondur.py --hakem arama_<etiket>.jsonl   çevrimdışı: hakem.jsonl kararlarını donmuş kayda uygula,
                                                                    özeti yeniden hesapla (PubMed'e gidilmez)
Çıktılar (var olan dosya EZİLMEZ, _2/_3 eki alır):
  sonuclar/arama_<tarih>.jsonl  (kayıt)   sonuclar/arama_ozet_<etiket>.json (tablo)   sonuclar/hakem_adaylari_<etiket>.jsonl
"""

import importlib.util
import json
import os
import re
import statistics
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import requests

from c07_sorgu_kur import alaka_etiketi, kaynaklari_getir
from test_seti import BEKLENEN_KADEME

BURASI = os.path.dirname(os.path.abspath(__file__))
GT_DOSYA = os.path.join(BURASI, "sonuclar", "dogru_cevap.jsonl")
HAKEM = os.path.join(BURASI, "hakem.jsonl")
ESKI = os.path.join(BURASI, "eski_hat")
PUBTATOR = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/"
ADET = 5
ARALIK = 0.4
OTO = ("litvar", "pubtator", "kurasyon")
LISTE = ("litvar", "kurasyon")
NUK = re.compile(r"^([acgt])(\d+)([acgt])$")


def _yukle(ad, yol):
    spec = importlib.util.spec_from_file_location(ad, yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


c02_v1 = _yukle("c02_v1", os.path.join(ESKI, "c02_v1.py"))
c01_v1 = _yukle("c01_v1", os.path.join(ESKI, "c01_v1.py"))


def yeni_yol(taban, uzanti):
    """sonuclar/<taban>.<uzanti>; varsa <taban>_2, _3 ... (aynı gün ikinci koşu öncekini ezmesin)."""
    yol = os.path.join(BURASI, "sonuclar", f"{taban}.{uzanti}")
    n = 2
    while os.path.exists(yol):
        yol = os.path.join(BURASI, "sonuclar", f"{taban}_{n}.{uzanti}")
        n += 1
    return yol


def _gecici_mi(e):
    """Ağ kesintisi mi (429/5xx/zaman aşımı/bağlantı)? Eski kodun deterministik hatalarından (ValueError, 400) ayrılır."""
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(e, requests.HTTPError):
        return getattr(e.response, "status_code", None) in (429, 500, 502, 503, 504)
    return False


def _tekrar(fn, *args, **kwargs):
    for deneme in range(3):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if _gecici_mi(e) and deneme < 2:
                time.sleep(2 * (deneme + 1))
                continue
            raise


# ---------------- v1 (eski hat, b87d8a8) ----------------
def eski_sorgu(girdi):
    """b87d8a8 c03.arama_terimi_belirle BİREBİR (print'ler atıldı): ':g.' -> HGVS ucu; 'chr:pos:R>A' -> region ucu (yalnız SNV);
    'GRCh37:' öneki eski c02'de ValueError -> ham metin; gen bulununca ALFABETİK ilk gen (chr19 APOE bölgesinde 'APOC1').
    (terim, ag_hatasi|None): eski kodun kendi hatası (ValueError, 400) None döner — o eski davranıştır; ağ kesintisi 3 denemeden sonra adıyla."""
    g = girdi.strip()
    for deneme in range(3):
        try:
            if ":g." in g:
                bilgi = c02_v1.anlamlandir_hgvs(g)
            elif ">" in g and g.count(":") >= 2:
                time.sleep(ARALIK)
                bilgi = c02_v1.anlamlandir(g)
            else:
                return g, None
            genler = bilgi.get("genler")
            return (genler[0] if genler else g), None
        except Exception as e:
            if _gecici_mi(e):
                if deneme < 2:
                    time.sleep(3 * (deneme + 1))
                    continue
                return g, type(e).__name__
            return g, None


def eski_makaleler(terim):
    """v1 hattı: makale_idleri_bul (esearch relevance, retmax=5) + makale_detaylari_al (eski ayrıştırıcı; 'özet yok' ELENMEZ).
    [{pmid, baslik, ozet, ozet_var}]"""
    time.sleep(ARALIK)
    pmidler = [str(p) for p in _tekrar(c01_v1.makale_idleri_bul, terim, adet=ADET)]
    if not pmidler:
        return []
    time.sleep(ARALIK)
    detay = {str(m["pmid"]): m for m in _tekrar(c01_v1.makale_detaylari_al, pmidler)}
    sonuc = []
    for p in pmidler:
        d = detay.get(p, {})
        ozet = d.get("ozet", "(özet yok)")
        sonuc.append({"pmid": p, "baslik": d.get("baslik"), "ozet": ozet, "ozet_var": ozet != "(özet yok)"})
    return sonuc


# ---------------- PubTator3 per-makale anotasyon ----------------
def pubtator_anotasyon(pmidler):
    """Her PMID için PubTator3'ün gördüğü varyant anotasyonları: ({pmid: {'rs334', 'p.v600e', 'c.20a>t', ...}}, hata|None)"""
    if not pmidler:
        return {}, None
    hata, veri = None, None
    for deneme in range(3):
        try:
            time.sleep(ARALIK if deneme == 0 else 3 * deneme)
            r = requests.get(PUBTATOR + "publications/export/biocjson", params={"pmids": ",".join(pmidler)}, timeout=120)
            r.raise_for_status()
            veri = r.json()
            break
        except Exception as e:
            hata, veri = type(e).__name__, None
    if veri is None:
        return {}, hata
    docs = veri.get("PubTator3", veri) if isinstance(veri, dict) else veri
    sonuc = {}
    for d in docs if isinstance(docs, list) else [docs]:
        pmid = str(d.get("pmid") or d.get("id") or "")
        etiketler = set()
        for p in d.get("passages", []):
            for a in p.get("annotations", []):
                inf = a.get("infons", {})
                if inf.get("type") == "Variant":
                    for parca in str(inf.get("identifier", "")).split(";"):
                        if parca.startswith("RS#:"):
                            etiketler.add("rs" + parca[4:])
                        if parca.startswith("HGVS:"):
                            etiketler.add(parca[5:].lower())
        sonuc[pmid] = etiketler
    return sonuc, None


def pubtator_bicimleri(gt, kayit):
    """Doğru cevap satırının PubTator anotasyonuyla karşılaştırılacak yazımları (küçük harf): rsID'ler (LitVar kayıtlarındakiler dahil),
    p.protein (kısa + diğer numaralama), c.cDNA, LitVar kayıt adları (c.1691g>a), ek terimler (c.35delg, c.5382insc),
    nükleotid tarzı eski ad -> HGVS (C677T -> c.677c>t, G20210A -> g.20210g>a)."""
    b = {r.lower() for r in (gt.get("rsid") or [])} | {r.lower() for r in (kayit.get("rsid") or [])}
    b |= {k["rsid"].lower() for k in gt.get("litvar_kayitlar") or [] if k.get("rsid")}
    for p in [gt.get("protein_kisa"), *(gt.get("protein_diger") or []), kayit.get("protein_kisa"), *(kayit.get("protein_diger") or [])]:
        if p and not p.endswith("="):
            b.add(f"p.{p.lower()}")
            b.add(f"p.{p.lower().replace('x', '*')}")
        n = NUK.match((p or "").lower())
        if n:
            b |= {f"c.{n.group(2)}{n.group(1)}>{n.group(3)}", f"g.{n.group(2)}{n.group(1)}>{n.group(3)}"}
    for c in (gt.get("cdna"), kayit.get("cdna")):
        if c:
            b.add(c.lower())
    for t in (gt.get("ek_terimler") or []) + (kayit.get("ek_terimler") or []):
        t = t.lower()
        b |= {t, t if t.startswith(("c.", "g.", "p.")) else f"c.{t}"}
    for k in gt.get("litvar_kayitlar") or []:
        if k.get("ad") and k["ad"][:2] in ("c.", "g.", "p."):
            b.add(k["ad"].lower())
    return b


def hakem_yukle():
    """degerlendirme/hakem.jsonl: {"girdi","pmid","karar":"varyant|gen|ilgisiz","kanit","tarih","hakem"} satırları (insan kararı)."""
    h = {}
    if os.path.exists(HAKEM):
        for l in open(HAKEM, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                h[(r["girdi"], str(r["pmid"]))] = r.get("karar")
    return h


def dogru_kaynak(pmid, gt, anot, hakem):
    """'litvar' | 'pubtator' | 'kurasyon' | 'hakem' | None"""
    if pmid in gt["litvar_set"]:
        return "litvar"
    if (anot.get(pmid) or set()) & gt["pt_bicimler"]:
        return "pubtator"
    if pmid in gt["kurasyon_set"]:
        return "kurasyon"
    if hakem.get((gt["girdi"], pmid)) == "varyant":
        return "hakem"
    return None


def hakemi_uygula(satir, hakem):
    """Donmuş kayıt satırındaki makalelere hakem kararlarını uygular (yalnızca otomatik olarak doğru SAYILMAYANLARA)."""
    for m in satir["makaleler"] + satir["v1_makaleler"]:
        if m.get("dogru_kaynak") in OTO:
            continue
        m["dogru_kaynak"] = "hakem" if hakem.get((satir["girdi"], m["pmid"])) == "varyant" else None


def satir_olculeri(satir):
    """Bir kayıt satırından tablo satırı (her ölçü kayıttaki makale etiketlerinden yeniden hesaplanır)."""
    v2, v1 = satir["makaleler"][:ADET], satir["v1_makaleler"][:ADET]
    d_katman = satir.get("kademe_beklenen") is not None
    gt_liste = satir.get("gt_liste_toplam") or 0
    return {"girdi": satir["girdi"], "katman": satir["katman"], "kademe": satir["kademe"], "d_katman": d_katman,
            "gt_toplam": satir.get("gt_toplam") or 0,
            "p5_v2": sum(m["dogru_kaynak"] in OTO for m in v2), "p5_v1": sum(m["dogru_kaynak"] in OTO for m in v1),
            "p5_v2_hakem": sum(bool(m["dogru_kaynak"]) for m in v2), "p5_v1_hakem": sum(bool(m["dogru_kaynak"]) for m in v1),
            "n_v2": len(satir["makaleler"]), "n_v1": len(satir["v1_makaleler"]),
            "v1_ozet_yok_hit": sum(1 for m in v1 if m["dogru_kaynak"] and not m.get("ozet_var", True)),
            "gen_etiketli_dogru": sum(1 for m in v2 if m.get("alaka") == "gen" and m["dogru_kaynak"] in OTO),
            "p5_v2_varyant_etiketli": sum(1 for m in v2 if m.get("alaka") in ("varyant", "kurasyon") and m["dogru_kaynak"] in OTO),
            "recall5_sinirli": (round(sum(m["dogru_kaynak"] in LISTE for m in v2) / min(gt_liste, ADET), 3)
                                if gt_liste and not d_katman else None),
            "kapsama_ozet": satir.get("kapsama_ozet"), "kademe_dogru": satir.get("kademe_dogru"),
            "yanlis_varyant_iddiasi": bool(satir.get("yanlis_varyant_iddiasi")),
            "v1_hata": bool(satir.get("v1_hata") or satir.get("v1_sorgu_hata")),
            "dogru_kaynak_v2": [m["dogru_kaynak"] for m in v2]}


def katman_ozeti(tablo):
    ozet = {}
    for k in sorted({t["katman"] for t in tablo}) + ["A+B+C"]:
        alt = [t for t in tablo if (k == "A+B+C" and not t["d_katman"]) or t["katman"] == k]
        if not alt:
            continue
        if all(t["d_katman"] for t in alt):
            ozet[k] = {"girdi": len(alt), "olcu": "beklenen kademe (P@5 uygulanmaz)",
                       "kademe_dogru_orani": round(sum(bool(t["kademe_dogru"]) for t in alt) / len(alt), 3),
                       "yanlis_varyant_iddiasi": sum(t["yanlis_varyant_iddiasi"] for t in alt),
                       "kademe": {kd: sum(1 for t in alt if t["kademe"] == kd) for kd in ("varyant", "gen", "yok", "hata")}}
            continue
        sabit = ADET * len(alt)
        n2 = sum(min(t["n_v2"], ADET) for t in alt) or 1
        n1 = sum(min(t["n_v1"], ADET) for t in alt) or 1
        kaynaklar = [d for t in alt for d in t["dogru_kaynak_v2"] if d]
        kapsama = [t["kapsama_ozet"] for t in alt if t["kapsama_ozet"] is not None]
        recall = [t["recall5_sinirli"] for t in alt if t["recall5_sinirli"] is not None]
        ozet[k] = {"girdi": len(alt),
                   "p5_v2": round(sum(t["p5_v2"] for t in alt) / sabit, 3), "p5_v1": round(sum(t["p5_v1"] for t in alt) / sabit, 3),
                   "kesinlik_donen_v2": round(sum(t["p5_v2"] for t in alt) / n2, 3), "kesinlik_donen_v1": round(sum(t["p5_v1"] for t in alt) / n1, 3),
                   "donen_v2": n2, "donen_v1": n1, "v1_bos": sum(1 for t in alt if t["n_v1"] == 0),
                   "v1_ag_hatasi": sum(t["v1_hata"] for t in alt), "v1_ozet_yok_hit": sum(t["v1_ozet_yok_hit"] for t in alt),
                   "p5_v2_hakem": round(sum(t["p5_v2_hakem"] for t in alt) / sabit, 3), "p5_v1_hakem": round(sum(t["p5_v1_hakem"] for t in alt) / sabit, 3),
                   "p5_v2_varyant_etiketli": round(sum(t["p5_v2_varyant_etiketli"] for t in alt) / sabit, 3),
                   "gen_etiketli_dogru": sum(t["gen_etiketli_dogru"] for t in alt),
                   "recall5_sinirli_ort": round(statistics.mean(recall), 3) if recall else None,
                   "dogru_kaynak_v2": {kd: kaynaklar.count(kd) for kd in ("litvar", "pubtator", "kurasyon", "hakem")},
                   "kapsama_ozet_medyan": round(statistics.median(kapsama), 3) if kapsama else None,
                   "gt_bos": sum(1 for t in alt if not t["gt_toplam"]),
                   "kademe": {kd: sum(1 for t in alt if t["kademe"] == kd) for kd in ("varyant", "gen", "yok", "hata")}}
    return ozet


def ozet_yaz(satirlar, hakem, ozet_yolu, kayit_adi):
    tablo = [satir_olculeri(s) for s in satirlar]
    ozet = katman_ozeti(tablo)
    json.dump({"kayit": kayit_adi, "hesap_tarihi": date.today().isoformat(), "adet": ADET, "hakem_karari": len(hakem),
               "katmanlar": ozet, "satirlar": tablo}, open(ozet_yolu, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nKATMAN ÖZETİ — P@5: doğru/5 (eksik=yanlış), kesinlik(dönen): doğru/dönen; v2 = yeni hat, v1 = eski hat (b87d8a8 kodu birebir)")
    for k, v in ozet.items():
        if "kademe_dogru_orani" in v:
            print(f"  {k:18} n={v['girdi']:2}  beklenen kademe doğru={v['kademe_dogru_orani']:.2f}  yanlış varyant iddiası={v['yanlis_varyant_iddiasi']}  kademe={v['kademe']}")
        else:
            print(f"  {k:18} n={v['girdi']:2}  P@5 v2={v['p5_v2']:.2f} v1={v['p5_v1']:.2f} | kesinlik(dönen) v2={v['kesinlik_donen_v2']:.2f} ({v['donen_v2']}) "
                  f"v1={v['kesinlik_donen_v1']:.2f} ({v['donen_v1']}, boş={v['v1_bos']}, ağ hatası={v['v1_ag_hatasi']}, özetsiz hit={v['v1_ozet_yok_hit']}) | "
                  f"hakemli v2={v['p5_v2_hakem']:.2f} v1={v['p5_v1_hakem']:.2f} | gen etiketli ama doğru={v['gen_etiketli_dogru']} | "
                  f"recall5={v['recall5_sinirli_ort']} | kaynak={v['dogru_kaynak_v2']} | özet-kapsama medyan={v['kapsama_ozet_medyan']}")
    print(f"Özet -> {ozet_yolu}  (hakem kararı: {len(hakem)})")
    return ozet


def hakem_cevrimdisi(kayit_adi):
    """Donmuş kayda hakem.jsonl kararlarını uygular ve özeti yeniden yazar (ağa gidilmez)."""
    kayit_yolu = kayit_adi if os.path.isabs(kayit_adi) else os.path.join(BURASI, "sonuclar", os.path.basename(kayit_adi))
    hakem = hakem_yukle()
    satirlar = [json.loads(l) for l in open(kayit_yolu, encoding="utf-8") if l.strip()]
    for s in satirlar:
        hakemi_uygula(s, hakem)
    etiket = os.path.basename(kayit_yolu).replace("arama_", "").replace(".jsonl", "")
    ozet_yaz(satirlar, hakem, os.path.join(BURASI, "sonuclar", f"arama_ozet_{etiket}.json"), os.path.basename(kayit_yolu))


def main():
    if "--hakem" in sys.argv:
        hakem_cevrimdisi(sys.argv[sys.argv.index("--hakem") + 1])
        return
    gts = [json.loads(l) for l in open(GT_DOSYA, encoding="utf-8") if l.strip()]
    hakem = hakem_yukle()
    bugun = date.today().isoformat()
    kayit_yolu = yeni_yol(f"arama_{bugun}", "jsonl")
    etiket = os.path.basename(kayit_yolu).replace("arama_", "").replace(".jsonl", "")
    ozet_yolu = os.path.join(BURASI, "sonuclar", f"arama_ozet_{etiket}.json")
    hakem_yolu = os.path.join(BURASI, "sonuclar", f"hakem_adaylari_{etiket}.jsonl")
    satirlar, hakem_adaylari = [], []
    print(f"doğru cevap: {len(gts)} satır | hakem kararı: {len(hakem)} | kayıt -> {os.path.basename(kayit_yolu)}")
    with open(kayit_yolu, "w", encoding="utf-8") as f:
        for gt in gts:
            girdi = gt["girdi"]
            gt["litvar_set"] = set(gt.get("litvar_pmidler") or [])
            try:
                s = _tekrar(kaynaklari_getir, girdi, adet=ADET)
            except Exception as e:
                print(f"{girdi}: HATA {type(e).__name__}: {e}")
                continue
            kayit = s["kayit"]
            gt["kurasyon_set"] = set(kayit.get("pubmed_kurasyon") or [])
            gt["pt_bicimler"] = pubtator_bicimleri(gt, kayit)
            secilen = s["makaleler"]
            # v1 (eski hat, birebir eski kod)
            v1_terim, v1_sorgu_hata = eski_sorgu(girdi)
            v1_hata = None
            try:
                v1 = eski_makaleler(v1_terim)
            except Exception as e:
                v1, v1_hata = [], type(e).__name__
            pmidler = list(dict.fromkeys([m["pmid"] for m in secilen] + [m["pmid"] for m in v1]))
            anot, pt_hata = pubtator_anotasyon(pmidler)
            if pt_hata:
                print(f"  (PubTator3 export hatası: {pt_hata}; bu satırda PubTator kaynağı yok)")
            for m in secilen + v1:
                m["dogru_kaynak"] = dogru_kaynak(m["pmid"], gt, anot, hakem)
            for m in v1:                                         # v1 makaleleri aynı alaka kuralıyla etiketlenir (hakem adayı için)
                m["alaka"] = alaka_etiketi(m, kayit) if m["ozet_var"] else "ozet_yok"
            gorulen = set()
            for hat, liste in (("v2", secilen), ("v1", v1)):
                for m in liste[:ADET]:
                    if m.get("alaka") == "varyant" and not m["dogru_kaynak"] and m["pmid"] not in gorulen:
                        gorulen.add(m["pmid"])
                        hakem_adaylari.append({"girdi": girdi, "pmid": m["pmid"], "hat": hat, "baslik": m.get("baslik"),
                                               "ozet": m.get("ozet") or "", "karar": "", "kanit": "", "tarih": bugun, "hakem": ""})
            gt_liste = len(gt["litvar_set"] | gt["kurasyon_set"])
            d_katman = girdi in BEKLENEN_KADEME
            satir = {"girdi": girdi, "katman": gt["katman"], "tarih": bugun,
                     "kayit": {k: kayit.get(k) for k in ("tur", "gen", "rsid", "protein_kisa", "protein_3harf", "protein_diger", "cdna", "ek_terimler")},
                     "sorgular": s["sorgular"], "sayilar": s["sayilar"], "kademe": s["kademe"], "uyarilar": s["uyarilar"],
                     "makaleler": [{k: m.get(k) for k in ("pmid", "alaka", "dogru_kaynak", "baslik", "ozet", "yil", "dergi", "yazar", "tur")} for m in secilen],
                     "v1_sorgu": v1_terim, "v1_sorgu_hata": v1_sorgu_hata, "v1_hata": v1_hata, "v1_makaleler": v1,
                     "v1_pmidler": [m["pmid"] for m in v1],
                     "pubtator_anotasyon": {p: sorted(e) for p, e in anot.items()}, "pubtator_hata": pt_hata,
                     "gt_litvar_sayi": len(gt["litvar_set"]), "gt_kurasyon_sayi": len(gt["kurasyon_set"]),
                     "kurasyon_pmidler": sorted(gt["kurasyon_set"]),
                     "gt_toplam": gt_liste, "gt_liste_toplam": gt_liste,
                     "kapsama_ozet": round((s["sayilar"].get("varyant_toplam") or 0) / gt_liste, 3) if gt_liste else None,
                     "kademe_beklenen": list(BEKLENEN_KADEME[girdi]) if d_katman else None,
                     "kademe_dogru": (s["kademe"] in BEKLENEN_KADEME[girdi]) if d_katman else None,
                     "yanlis_varyant_iddiasi": d_katman and s["kademe"] == "varyant"}
            f.write(json.dumps(satir, ensure_ascii=False) + "\n")
            f.flush()
            satirlar.append(satir)
            t = satir_olculeri(satir)
            if d_katman:
                print(f"{gt['katman']:18} {girdi:34} kademe={s['kademe']:7} beklenen={'/'.join(BEKLENEN_KADEME[girdi])} -> "
                      f"{'DOĞRU' if satir['kademe_dogru'] else 'YANLIŞ'}")
            else:
                print(f"{gt['katman']:18} {girdi:34} gt={gt_liste:5} kademe={s['kademe']:7} P@5 v2={t['p5_v2']}/{len(secilen)} v1={t['p5_v1']}/{len(v1)}"
                      + (f" (v1 sorgu: {v1_terim})" if v1_terim != girdi else "") + (f" [v1 ağ hatası: {v1_sorgu_hata or v1_hata}]" if t["v1_hata"] else ""))
    with open(hakem_yolu, "w", encoding="utf-8") as f:
        for h in hakem_adaylari:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    print(f"Kayıt -> {kayit_yolu}\nHakem adayları ({len(hakem_adaylari)}; iki hattın 'varyant' dediği, otomatik liste dışı makaleler) -> {hakem_yolu}")
    ozet_yaz(satirlar, hakem, ozet_yolu, os.path.basename(kayit_yolu))


if __name__ == "__main__":
    main()
