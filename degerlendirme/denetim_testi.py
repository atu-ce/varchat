"""
DENETİM TESTİ — c04'ün üretim sonrası denetimleri için çevrimdışı testler (Ollama çağrılmaz, birkaç saniye sürer).

Neden: atıf, cümle bölme, kesik cümle, çeviri düzeltmesi ve çelişki denetimi ölçüm tablosuna doğrudan sayı yazar
(atıfsız cümle oranı, geçersiz atıf, çelişki). Düzenli ifadeler (regex) küçük bir değişiklikle sessizce bozulabilir;
bu dosya bilinen her durumu bir kez yazar ve kod değişince yeniden koşulur.

Kullanım: python degerlendirme/denetim_testi.py      (hepsi geçerse çıkış kodu 0)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import c04_varchat_ollama as app

RET = app.RET_CEVAP
basarisiz = []


def kontrol(ad, gercek, beklenen):
    if gercek == beklenen:
        print(f"  geçti   {ad}")
    else:
        basarisiz.append(ad)
        print(f"  KALDI   {ad}\n          beklenen: {beklenen!r}\n          gelen   : {gercek!r}")


# ---------------------------------------------------------------- atıf denetimi (5 kaynak)
print("ATIF DENETİMİ")
for girdi in [f"{RET[:-1]}. [1]", f"{RET[:-1]}.[1]", f"{RET[:-1]} [1].", f"{RET[:-1]} [1]", f"{RET[:-1]} [1], [2].", f"{RET[:-1]} [2] [3]."]:
    temiz, r = app.atif_denetimi(girdi, 5)
    kontrol(f"ret + yapışık atıf -> yalnız ret: {girdi!r}", (temiz, r["cumle"]), (RET, 0))

temiz, r = app.atif_denetimi(f"{RET[:-1]} [1] Ancak ikinci kaynak şunu bildirir [2].", 5)
kontrol("ret + atıf + devam (noktasız): boşluk korunur, devam kalır", (temiz, r["cumle"], r["atifsiz_cumle"]),
        (f"{RET} Ancak ikinci kaynak şunu bildirir [2].", 1, 0))
temiz, r = app.atif_denetimi(f"{RET[:-1]}. [1] Ancak ikinci kaynak şunu bildirir [2].", 5)
kontrol("ret. [1] + devam: ret atıfı silinir, devam kalır", temiz, f"{RET} Ancak ikinci kaynak şunu bildirir [2].")
temiz, r = app.atif_denetimi(f"BRAF V600E melanomda sık görülür [1]. {RET[:-1]} [2].", 5)
kontrol("cevabın ortasındaki ret cümlesinin atıfı da silinir", (temiz, r["cumle"]), (f"BRAF V600E melanomda sık görülür [1]. {RET}", 1))
temiz, r = app.atif_denetimi("Birinci cümle burada yazıyor [1, 2, 9]. İkinci cümle de burada [1-10].", 5)
kontrol("karışık liste/aralıkta geçerli kısım kalır", (temiz, r["gecersiz_atif"]),
        ("Birinci cümle burada yazıyor [1, 2]. İkinci cümle de burada [1, 2, 3, 4, 5].", [6, 7, 8, 9, 10]))
temiz, r = app.atif_denetimi("Bir iki üç dört beş [1-2-3].", 5)
kontrol("çözülemeyen atıf '[1-2-3]' silinir ve geçersiz diye RAPORLANIR", (temiz, r["gecersiz_atif"], r["atifsiz_cumle"]),
        ("Bir iki üç dört beş.", ["1-2-3"], 1))
temiz, r = app.atif_denetimi("Bu bileşik [1,2,4]triazolo halkası taşır ve etkilidir [2].", 5)
kontrol("kimyasal ad '[1,2,4]triazolo' atıf sayılmaz", (temiz, r["gecersiz_atif"], r["atifsiz_cumle"]),
        ("Bu bileşik [1,2,4]triazolo halkası taşır ve etkilidir [2].", [], 0))
kontrol("ters aralık [5-2] açılmaz, iki numara sayılır", app.atif_numaralari("x [5-2] y [ 3 ] z [1; 4]"), [5, 2, 3, 1, 4])

# ---------------------------------------------------------------- cümle bölme
print("CÜMLE BÖLME")
kontrol("madde ve numaralı liste işaretleri atılır, '. [3]' önceki cümleye yapışır",
        app.cumlelere_bol("Özet:\n- Madde bir burada yazıyor [1]\n- Madde iki burada yazıyor [2]\n3. Numaralı madde burada yazıyor. [3]\n"
                          "Son cümle burada kalır. Bir başka cümle [4]."),
        ["Özet:", "Madde bir burada yazıyor [1]", "Madde iki burada yazıyor [2]", "Numaralı madde burada yazıyor. [3]",
         "Son cümle burada kalır.", "Bir başka cümle [4]."])
kontrol("'cümle. [1] Sonraki' stili: atıf önceki (atıfsız) cümleye taşınır",
        app.cumlelere_bol("Birinci cümle burada yazıyor. [1] İkinci cümle de burada. [2]"),
        ["Birinci cümle burada yazıyor. [1]", "İkinci cümle de burada. [2]"])
kontrol("önceki cümle zaten atıflıysa baştaki atıf yerinde kalır ('[2] numaralı çalışmada')",
        app.cumlelere_bol("Birinci cümle burada yazıyor [1]. [2] numaralı çalışmada başka bulgu var."),
        ["Birinci cümle burada yazıyor [1].", "[2] numaralı çalışmada başka bulgu var."])
kontrol("özne olarak atıf ('[1] ve [3] kaynaklarında ...') önceki cümleye taşınmaz (gerçek SMO W535L cevabı)",
        app.cumlelere_bol("SMO varyantı bazı türlerde görülmektedir. [1] ve [3] kaynaklarında belirtildiğine göre katkıda bulunur. "
                          "[3] kaynağında oran yüzde kırk üç bulunmuştur."),
        ["SMO varyantı bazı türlerde görülmektedir.", "[1] ve [3] kaynaklarında belirtildiğine göre katkıda bulunur.",
         "[3] kaynağında oran yüzde kırk üç bulunmuştur."])
kontrol("sondaki atıf listesi '. [1] ve [3].' önceki cümleye yapışır",
        app.cumlelere_bol("Bu konuda daha fazla bilgiye ihtiyaç vardır. [1] ve [3]."),
        ["Bu konuda daha fazla bilgiye ihtiyaç vardır. [1] ve [3]."])
kontrol("ondalık sayı ve p.Val600Glu bölünmez", app.cumlelere_bol("Sıklık %70.49 bulundu ve p.Val600Glu önemlidir [1]."),
        ["Sıklık %70.49 bulundu ve p.Val600Glu önemlidir [1]."])

# ---------------------------------------------------------------- kesik son cümle
print("KESİK CÜMLE")
kontrol("madde listesinde kesik son madde işaretiyle birlikte atılır",
        app.kesik_cumleyi_at("- Tam madde bir iki üç [1].\n- Kesik madde iki üç dört ve"), ("- Tam madde bir iki üç [1].", True))
kontrol("numaralı listede de", app.kesik_cumleyi_at("1. Tam madde bir iki üç [1].\n2. Kesik madde"), ("1. Tam madde bir iki üç [1].", True))
kontrol("düz metinde yarım son cümle atılır", app.kesik_cumleyi_at("Birinci tam cümle burada [1]. İkinci cümle yarım kal"),
        ("Birinci tam cümle burada [1].", True))
kontrol("atıfla biten cümle tam sayılır", app.kesik_cumleyi_at("Birinci cümle [1]. İkinci cümle burada [2]"),
        ("Birinci cümle [1]. İkinci cümle burada [2]", False))
kontrol("tek (yarım) cümle silinmez", app.kesik_cumleyi_at("Tek cümle yarım kal"), ("Tek cümle yarım kal", False))

# ---------------------------------------------------------------- çeviri düzeltmesi
print("ÇEVİRİ DÜZELTMESİ")
metin, n = app.ceviri_duzelt("Bu varyant HBB geninde bulunur [1]. Sikiş hücre anemisine yol açar [2]. Hastalarda sikiş hücre krizi görülür [3].")
kontrol("cümle başında büyük harf korunur, ortada küçük", (metin, n),
        ("Bu varyant HBB geninde bulunur [1]. Orak hücre anemisine yol açar [2]. Hastalarda orak hücre krizi görülür [3].", 2))
kontrol("düzeltme sonrası cümle sayısı doğru (3)", len(app.cumlelere_bol(metin)), 3)

# ---------------------------------------------------------------- çelişki denetimi
print("ÇELİŞKİ DENETİMİ")


def celiski(onem, metin, kademe="varyant"):
    app.SON_BAGLAM.clear()
    app.SON_BAGLAM.update(kademe=kademe, clinvar={"germline": {"onem": onem}})
    return bool(app.celiski_denetimi(metin))


PATOJENIK_UYARI = [   # ClinVar 'Pathogenic' iken bu ifadeler UYARI vermeli (zararsız yön)
    "Bu varyant patojenik değildir [1].",
    "Bu varyantın hastalıkla ilişkisi yoktur [1].",
    "Bu varyant hastalıkla ilişkili bulunmamıştır [1].",
    "Hastalıkla ilişki saptanmamıştır [1].",
    "Bu varyantın hastalığa neden olmadığı gösterilmiştir [1].",
    "Varyant patojenik olarak sınıflandırılmamıştır [1].",
    "Zararlı olmadığı gösterilmiştir [1].",
    "Bu varyant hastalık riskini azaltır [1].",
    "Bu varyant koroner hastalık riskini belirgin şekilde düşürür [1].",
    "Bu varyant tromboz ile ilişkili değildir [1].",
    "Bu varyant iyi huyludur [1].",
    "İyi huylu bir varyanttır [1].",
    "Bu varyant benign olarak değerlendirilmiştir [1].",
]
PATOJENIK_SESSIZ = [   # ClinVar 'Pathogenic' iken uyarı VERMEMELİ
    "Bu varyant orak hücre anemisine yol açar [1]; taşıyıcılık sıtmaya karşı koruyucudur [2].",
    "Bu varyant hastalık riskini arttırır [1].",
    "Bu varyant tromboz riskini belirgin şekilde artırır [1].",
    "Varyant iyi huylu tümör oluşumuna yol açar [1].",
    "Varyant iyi huylu kemik lezyonlarına neden olur [1].",
    "Bu varyant patojeniktir [1].",
    "Fibröz displaziye neden olur [1].",
]
BENIGN_UYARI = [   # ClinVar 'Benign' iken UYARI vermeli (zararlı yön)
    "Bu varyant patojeniktir [1].",
    "Bu varyant kanser riskini arttırır [1].",
    "Bu varyant meme kanseri ile ilişkilidir [1].",
    "Bu varyant hastalığa neden olur [1].",
    "Varyant ciddi bir sendroma yol açar [1].",
]
BENIGN_SESSIZ = [   # ClinVar 'Benign' iken uyarı VERMEMELİ
    "Bu varyant patojenik değildir [1].",
    "Benign varyantlar sık görülür [1].",
    "Bu varyantın hastalığa neden olmadığı gösterilmiştir [1].",
    "Patojenik olarak sınıflandırılmamıştır [1].",
    "Hastalıkla ilişkisi yoktur [1].",
    "Bu varyant tromboz ile ilişkili değildir [1].",
    "Bu varyant ilaç yanıtını etkiler [1].",
]
for m in PATOJENIK_UYARI:
    kontrol(f"Pathogenic + '{m}' -> uyarı", celiski("Pathogenic", m), True)
for m in PATOJENIK_SESSIZ:
    kontrol(f"Pathogenic + '{m}' -> sessiz", celiski("Pathogenic", m), False)
for m in BENIGN_UYARI:
    kontrol(f"Benign + '{m}' -> uyarı", celiski("Benign", m), True)
for m in BENIGN_SESSIZ:
    kontrol(f"Benign + '{m}' -> sessiz", celiski("Benign", m), False)
kontrol("gen kademesinde denetim yok", celiski("Benign", "TTN geni patojenik varyantlar taşır [1].", kademe="gen"), False)
kontrol("çelişkili (Conflicting) sınıfta denetim yok", celiski("Conflicting classifications of pathogenicity", "Bu varyant patojeniktir [1]."), False)
app.SON_BAGLAM.clear()

# ---------------------------------------------------------------- tekrar döngüsü (Ollama 'token repeat limit reached')
print("TEKRAR DÖNGÜSÜ")
import ollama as _ollama
import b07_sadakat as b07


class _Cevap(dict):
    def __init__(self, metin):
        super().__init__(message={"content": metin})
        self.done_reason, self.prompt_eval_count, self.eval_count, self.total_duration = "stop", 100, 20, 1_000_000


def _sahte(sira):
    """Sırayla: Exception örneği -> fırlatılır, metin -> cevap döner."""
    kalan = list(sira)

    def chat(**kw):
        x = kalan.pop(0)
        if isinstance(x, Exception):
            raise x
        return _Cevap(x)
    return chat


DONGU = _ollama.ResponseError("prediction aborted, token repeat limit reached", 500)
_gercek_chat = _ollama.chat
try:
    app.SON_BAGLAM.clear(); app.SON_BAGLAM.update(kademe="varyant", n_kaynak=2)
    _ollama.chat = _sahte([DONGU, "Bu varyant melanomda sık görülür [1]."])
    g = [{"role": "system", "content": "[1] Başlık: a"}]
    sonuc = app.grounded_sor(g, "özetle")
    kontrol("üretim: döngüde bir kez yeniden üretilir ve işaretlenir", (sonuc, app.SON_YANIT.get("tekrar_dongusu"), len(g)),
            ("Bu varyant melanomda sık görülür [1].", True, 3))
    _ollama.chat = _sahte([_ollama.ResponseError("model not found", 404)])
    try:
        app.grounded_sor([{"role": "system", "content": "x"}], "özetle")
        kontrol("üretim: döngü dışı model hatası yeniden denenmeden iletilir", "hata yok", "ResponseError")
    except _ollama.ResponseError:
        kontrol("üretim: döngü dışı model hatası yeniden denenmeden iletilir", "ResponseError", "ResponseError")
    kontrol("kullanıcı mesajı: model hatası ile bağlantı hatası ayrılır",
            (app.model_hata_mesaji(DONGU).startswith("Model bu soruya"), app.model_hata_mesaji(ConnectionError()).startswith("Yerel modele")),
            (True, True))
    kaynak = [(1, {"baslik": "B", "ozet": "O"})]
    _ollama.chat = _sahte([DONGU, '{"karar": "DESTEKLENIYOR", "gerekce": "kaynakta var"}'])
    kontrol("yargıç: döngüde ikinci denemede karar verir", b07.yargila("iddia", kaynak, "m")[::2], ("DESTEKLENIYOR", 1))
    _ollama.chat = _sahte(["{bozuk", '{"karar": "CELISIYOR", "gerekce": "ters"}'])
    kontrol("yargıç: geçersiz JSON'da ikinci denemede karar verir", b07.yargila("iddia", kaynak, "m")[::2], ("CELISIYOR", 1))
    _ollama.chat = _sahte([DONGU, DONGU])
    k, gerekce, d = b07.yargila("iddia", kaynak, "m")
    kontrol("yargıç: iki deneme de başarısızsa BELIRSIZ + 'yargıç hatası', betik durmaz", (k, gerekce.startswith("yargıç hatası"), d),
            ("BELIRSIZ", True, 2))
    _ollama.chat = _sahte(['{"karar": "DESTEKLENMIYOR", "gerekce": "yok"}'])
    kontrol("yargıç: normal durumda tek deneme", b07.yargila("iddia", kaynak, "m")[::2], ("DESTEKLENMIYOR", 0))
finally:
    _ollama.chat = _gercek_chat
    app.SON_BAGLAM.clear()

print()
if basarisiz:
    print(f"{len(basarisiz)} test KALDI.")
    sys.exit(1)
print("Tüm testler geçti.")
