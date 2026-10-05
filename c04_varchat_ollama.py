"""
VarChat benzeri chatbot — TAMAMEN YEREL + YÖNLENDİRİCİ (ana uygulama).

Gemini yok; kendi bilgisayarında qwen2.5:7b (Ollama) çalışır.
Yönlendirici (router) sayesinde kullanıcı serbestçe yazabilir:
  - SELAMLAMA / KENDINI_TANIT / KONU_DISI  -> doğrudan, KOD tarafından cevaplanır
  - VARYANT                                 -> RAG hattına (anlamlandırma + kademeli PubMed araması + özet) gider

Güvenlik notu: Konu dışı yanıt LLM'e bırakılmaz, kod sabit metin döndürür; ayrıca üretim
yalnızca çekilen makalelere dayanır (grounded). Böylece "kuralları yok say" gibi
denemelerin zararı sınırlıdır.

İnternet yalnızca PubMed / VEP / ClinVar sorguları için gerekir.
"""

import json
import re
import sys

import ollama

from c01_makale_getir import kunye
from c05_gen_validasyon import gen_cikar, gen_gecerli_mi, GEN_LISTESI
from c06_clinvar import clinvar_bilgisi, clinvar_satirlari
from c07_sorgu_kur import kaynaklari_getir, baglam_metni   # kademeli arama + alaka kapısı (adım 4)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

MODEL = "qwen2.5:7b"                # grounded üretim (LoRA gelince: "varchat")
SINIFLANDIRICI_MODEL = MODEL        # niyet_belirle; LoRA'ya geçince bilinçli karar ver (eğitim verisinde sınıflandırma örneği yok)

# --- Üretim ayarları: TEK yerden. Her ollama.chat çağrısı bunları alır. ---
# num_ctx        : bağlam penceresi (modelin "masası"). Ollama varsayılanı 4096; 5 makale özeti tek başına
#                  ~2.000 token olduğu için masa hemen doluyordu ve kaynaklar sessizce düşüyordu. Model 32k destekler;
#                  8192 CPU belleğine rahat sığar (KV önbelleği ~450 MB).
# num_predict    : cevaba ayrılan pay. Bütçede bu pay düşülür; üretimde de sınırdır ki pencere ÜRETİM sırasında dolmasın.
# temperature=0  : zar yok; aynı soruya aynı cevap (ölçüm ve hata ayıklama için şart).
# seed           : rastgele tohum sabit; temperature 0 ile birlikte tekrar üretilebilirlik.
# repeat_penalty : Qwen'in kendi önerisi (1.05); tekrar döngülerini frenler.
# NOT: iki çağrı da aynı num_ctx'i kullanmalı; farklı num_ctx Ollama'yı modeli yeniden yüklemeye zorlar.
#      İstekle gönderilen options, Modelfile'daki PARAMETER satırlarını ezer; iki yer aynı tutulmalı.
CIKTI_PAYI = 1024
AYARLAR = {"num_ctx": 8192, "num_predict": CIKTI_PAYI, "temperature": 0, "seed": 42, "repeat_penalty": 1.05}
SON_TUR_SAYISI = 8       # geçmişte tutulacak en fazla tamamlanmış soru-cevap çifti (asıl fren token bütçesidir)

# Kaba token tahmini. Gerçek Qwen tokenizer ölçümü: İngilizce makale özetleri ~4,3 karakter/token,
# Türkçe cevaplar medyan 2,8 (en kötü 2,3). Oranlar ÜSTTEN tahmin edecek şekilde seçildi (system 3,5; Türkçe 2,5).
KARAKTER_PER_TOKEN = {"system": 3.5, "user": 2.5, "assistant": 2.5}
SABLON_PAYI = 6          # Qwen chat şablonu: <|im_start|>rol ... <|im_end|> (~5-6 token / mesaj)

# Gözlenen kötü çeviriler: kod tarafında deterministik düzeltme (kalıcı çözüm fine-tune verisinde doğru terimler)
YASAK_CEVIRI = [(re.compile(r"siki[şs]\s*hücre", re.IGNORECASE), "orak hücre")]

# varyant_baglami_kur'un son çağrısının bilgisi: {'kademe', 'gen', 'varyant', 'n_kaynak', 'clinvar'} (imza değişmesin diye; b02 kullanır)
SON_BAGLAM = {}
# grounded_sor'un son cevabı için denetim sonuçları: {'gecersiz_atif', 'atifsiz_cumle', 'cumle', 'cjk_orani', 'yeniden_uretildi', 'bozuk',
#   'kesik_cumle_atildi', 'celiski', 'girdi_token', 'cikti_token', 'bitis', 'sure_ms'}
SON_YANIT = {}

# --- Üretim sonrası denetimler (adım 7) ---
# Prompt "her cümleye [n] yaz" der ama model uymayabilir; kaynak listesini kod bastığı için makale uydurulamaz,
# ama numara karışabilir. Bu yüzden çıktı kod tarafında denetlenir: geçersiz [n] silinir, atıfsız cümle sayılır,
# Çince/Japonca karakter oranı ölçülür (dil çöküşü), ClinVar sınıfıyla yön çelişkisi (patojenik ↔ "riski azaltır") aranır.
ATIF = re.compile(r"\[\s*(\d+(?:\s*[-–,;]\s*\d+)*)\s*\](?![a-zçğıöşü])")   # [1] [1-3] [1, 2, 3] [1; 2] [ 1 ]; '[1,2,4]triazolo' değil
RET_CEVAP = "Bu konuda elimdeki kaynaklarda bilgi yok."
# Ret cümlesi + yapışık atıf, cevabın neresinde olursa olsun ('yok [1].', 'yok. [1]', 'yok [1], [2]', 'yok [1] Ancak ...')
RET_ATIFLI = re.compile(r"(?<![^\s.!?])" + re.escape(RET_CEVAP.rstrip(".")) + r"\s*[.!]?\s*(?:\[[^\]]*\][\s,;]*)+[.!]?")
CJK = re.compile(r"[一-鿿぀-ヿ가-힯]")
CUMLE_SINIRI = re.compile(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ\[(])|\n+")       # nokta + büyük harf, ya da satır sonu (madde işaretli listeler)
MADDE_ISARETI = re.compile(r"^[ \t]*(?:[-•*–]|\d{1,2}[.)])[ \t]+", re.M)  # '- ', '• ', '3. ', '2) ' (satır başında)
BASTAKI_ATIF = re.compile(r"^((?:\[[^\]]*\](?![a-zçğıöşü])\s*)+)(.*)$", re.S)
YALNIZ_ATIF_LISTESI = re.compile(r"^(?:\[[^\]]*\](?![a-zçğıöşü])|[\s,;&]+|ve(?![a-zçğıöşü])|ile(?![a-zçğıöşü])|and(?![a-z]))+[.!?]?$")   # '[1] ve [3].'
# Yön çelişkisi desenleri — Türkçe küçük harfe çevrilmiş metne uygulanır (_tr_kucuk: 'İ'->'i', 'I'->'ı').
# Negasyon ('patojenik değildir', 'hastalığa neden olmadığı', 'X ile ilişkili değildir') ÖNCE ayrılır ki zararlı desen tetiklenmesin;
# 'iyi huylu/benign tümör/lezyon' hastalık adıdır, zararsız ifade sayılmaz; 'neden olmadığı'/'yol açmaz' zararlı sayılmaz.
_HASTALIK = r"(?:hastalı|anemi|sendrom|kanser|tromboz|tümör|displazi|bozukluk|bozukluğ|emboli|fenotip)\w*"
NEGASYON_ZARARSIZ = re.compile(
    r"\b(?:patojen\w*\s+değil\w*"
    r"|(?:patojen\w*|zararlı)\s+olmadığ\w*"
    r"|(?:patojen\w*|zararlı|hastalık\s+yapıcı)\s+(?:olarak\s+)?(?:sınıflandırılma|kabul\s+edilme|değerlendirilme)(?:mış|dı|z|yan)\w*"
    r"|zararlı\s+değil\w*"
    r"|" + _HASTALIK + r"\s+(?:neden\s+ol|yol\s+aç)ma\w*"
    r"|\S+(?:\s+ile)?\s+ilişki(?:li|si)?\s+(?:değil|yok|bulunma|saptanma|gösterilme|kurulama)\w*"
    r"|hastalık\s+yapmaz)")
ZARARSIZ_IFADE = re.compile(
    r"\b(?:risk\w*\s+(?:\S+\s+){0,2}(?:azal|düş)\w*"
    r"|zararsız\w*"
    r"|(?:iyi\s+huylu\w*|benign\w*)(?!\s+(?:\S+\s+)?(?:tümör|tumor|lezyon|neoplazi|kitle|adenom|nodül|kist|polip))"
    r"|koruyucu\w*)")
ZARARLI_IFADE = re.compile(
    r"\b(?:patojenik\w*"
    r"|" + _HASTALIK + r"\s+(?:\S+\s+)?(?:neden\s+ol(?!ma)|yol\s+aç(?!ma))\w*"
    r"|hastalık\s+yapar"
    r"|zararlı\w*"
    r"|risk\w*\s+(?:\S+\s+){0,2}art(?!ma)\w*"
    r"|" + _HASTALIK + r"(?:\s+ile)?\s+ilişkili\w*)")
VERITABANI_PROMPTA = False   # True: ClinVar/anotasyon kartı system prompt'a eklenir (eğitim verisiyle farklılaşır; ablasyon için)
ARASTIRMA_UYARISI = "Not: Bu çıktı araştırma amaçlıdır; tanı ve tedavi kararı için klinik genetik uzmanına başvurun."


def cumlelere_bol(metin):
    """Cümlelere böler: nokta/ünlem/soru + büyük harf, ayrıca satır sonları (madde işaretli listeler ayrı cümle sayılır).
    Madde/numara işaretleri bölmeden ÖNCE atılır. Noktadan sonra gelen atıflar:
      - yalnızca atıf listesi ('... vardır. [1] ve [3].') -> önceki cümleye yapışır;
      - atıf + BÜYÜK harfle yeni cümle ('... yazıyor. [1] İkinci cümle') -> atıf önceki (atıfsız) cümleye taşınır;
      - atıf + küçük harfle devam ('[1] ve [3] kaynaklarında ...', '[2] numaralı çalışmada') -> atıf o cümlenin öznesidir, yerinde kalır."""
    parcalar = []
    for c in CUMLE_SINIRI.split(MADDE_ISARETI.sub("", metin.strip())):
        c = (c or "").strip()
        if not c:
            continue
        if parcalar and YALNIZ_ATIF_LISTESI.match(c):
            parcalar[-1] = f"{parcalar[-1]} {c}"
            continue
        m = BASTAKI_ATIF.match(c)
        geri = m.group(2).strip() if m else ""
        if (m and parcalar and geri[:1].isupper() and not ATIF.search(parcalar[-1]) and re.search(r"[.!?]$", parcalar[-1])):
            parcalar[-1] = f"{parcalar[-1]} {m.group(1).strip()}"
            c = geri
        parcalar.append(c)
    return parcalar


def kesik_cumleyi_at(icerik):
    """Token sınırında kesilen cevabın yarım son cümlesini (ve varsa sarkan madde işaretini) atar. (icerik, atıldı_mı)
    Atıfla ']' ya da noktalama ile biten son cümle tam sayılır; tek cümlelik cevap silinmez."""
    parcalar = cumlelere_bol(icerik)
    if len(parcalar) < 2 or re.search(r"[.!?\]]\s*$", parcalar[-1]):
        return icerik, False
    k = icerik.rfind(parcalar[-1])
    if k <= 0:
        return icerik, False
    return re.sub(r"(?:^|\n)[ \t]*(?:[-•*–]|\d{1,2}[.)])?[ \t]*$", "", icerik[:k]).rstrip(), True


def ceviri_duzelt(icerik):
    """YASAK_CEVIRI düzeltmeleri; cümle başındaki büyük harf korunur ('Sikiş hücre' -> 'Orak hücre'). (icerik, düzeltme_sayısı)"""
    toplam = 0
    for desen, dogru in YASAK_CEVIRI:
        icerik, n = desen.subn(lambda e, d=dogru: (d[0].upper() + d[1:]) if e.group(0)[:1].isupper() else d, icerik)
        toplam += n
    return icerik, toplam


def _atif_coz(ic):
    """'1, 2-4; 7' -> [1, 2, 3, 4, 7]; ters aralık '5-2' -> [5, 2] (aralık açılmaz); çözülemeyen parça ('1-2-3') -> None."""
    nums = []
    for parca in re.split(r"\s*[,;]\s*", ic.strip()):
        m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", parca)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            nums += list(range(a, b + 1)) if a <= b else [a, b]
        elif parca.isdigit():
            nums.append(int(parca))
        else:
            nums.append(None)
    return nums


def atif_numaralari(metin):
    """Metindeki tüm (çözülebilen) atıf numaraları (sırayla, tekrarlı)."""
    return [n for m in ATIF.finditer(metin) for n in _atif_coz(m.group(1)) if n is not None]


def _bosluk(metin):
    return re.sub(r"[ \t]+([.,;])", r"\1", re.sub(r"[ \t]{2,}", " ", metin))


def atif_denetimi(icerik, n_kaynak):
    """Geçersiz [n] atıflarını siler (karışık '[1-10]'da geçerli kısım kalır; çözülemeyen '[1-2-3]' silinir ve raporlanır),
    ret cümlesine yapışık atıfı siler (cevabın neresinde olursa olsun; devamı korunur), atıfsız cümleleri sayar.
    (temiz_icerik, rapor) döndürür. rapor['gecersiz_atif']: kaynak sayısını aşan numaralar + çözülemeyen ham atıflar."""
    gecersiz, cozulemeyen = set(), []

    def degistir(m):
        nums = _atif_coz(m.group(1))
        if None in nums:
            cozulemeyen.append(m.group(1).strip())
            return ""
        gecerli = [n for n in dict.fromkeys(nums) if 1 <= n <= n_kaynak]
        kotu = [n for n in nums if not (1 <= n <= n_kaynak)]
        gecersiz.update(kotu)
        if not gecerli:
            return ""
        return "[" + ", ".join(map(str, gecerli)) + "]" if kotu else m.group(0)
    temiz = _bosluk(ATIF.sub(degistir, icerik))
    temiz = _bosluk(RET_ATIFLI.sub(RET_CEVAP + " ", temiz)).strip()
    cumleler = [c for c in cumlelere_bol(temiz) if len(c.split()) >= 4 and c != RET_CEVAP]
    atifsiz = [c for c in cumleler if not ATIF.search(c)]
    return temiz, {"gecersiz_atif": sorted(gecersiz) + cozulemeyen, "atifsiz_cumle": len(atifsiz), "cumle": len(cumleler)}


def dil_denetimi(icerik):
    """Çince/Japonca/Korece karakter oranı (harflere göre). 0 = temiz."""
    cjk = len(CJK.findall(icerik))
    harf = sum(ch.isalpha() for ch in icerik) or 1
    return cjk / harf


def _tr_kucuk(metin):
    """Türkçe küçük harf: 'İyi huylu' -> 'iyi huylu', 'RİSK' -> 'risk' (Python'un lower()'ı 'İ'yi 'i̇' yapar, eşleşmeyi bozar)."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def celiski_denetimi(icerik):
    """ClinVar germline sınıfı ile özetin yönü çelişiyor mu? (patojenik ↔ 'riski azaltır'; benign ↔ 'patojenik')
    Gen kademesinde uygulanmaz (özet gen hakkındadır; varyantın sınıfıyla kıyas anlamsız).
    Negasyon ('patojenik değildir') açık çelişkidir ve zararlı deseni tetiklemesin diye metinden önce ayrılır."""
    if SON_BAGLAM.get("kademe") == "gen":
        return None
    cv = SON_BAGLAM.get("clinvar")
    g = (cv or {}).get("germline") or {}
    onem = (g.get("onem") or "").lower()
    if not onem or "conflicting" in onem:
        return None
    patojen = "pathogenic" in onem and "benign" not in onem
    benign = "benign" in onem and "pathogenic" not in onem
    metin = _tr_kucuk(icerik)
    negasyon = bool(NEGASYON_ZARARSIZ.search(metin))
    metin = NEGASYON_ZARARSIZ.sub(" ", metin)
    zararsiz = negasyon or bool(ZARARSIZ_IFADE.search(metin))
    zararli = bool(ZARARLI_IFADE.search(metin))
    if patojen and (negasyon or (zararsiz and not zararli)):
        return f"ClinVar bu varyantı '{g['onem']}' sınıflıyor; özet ise zararsız/koruyucu yönde ifade içeriyor. Çelişki olabilir."
    if benign and zararli and not zararsiz:
        return f"ClinVar bu varyantı '{g['onem']}' sınıflıyor; özet ise zararlı yönde ifade içeriyor. Çelişki olabilir."
    return None


def model_hata_mesaji(e):
    """Kullanıcıya gösterilecek hata cümlesi: model cevap üretemedi mi, yoksa Ollama'ya hiç ulaşılamadı mı?"""
    if isinstance(e, ollama.ResponseError):
        return f"Model bu soruya cevap üretemedi ({str(e)[:80]}). Soruyu biraz farklı biçimde sormayı deneyin."
    return f"Yerel modele ulaşılamadı ({type(e).__name__}). Ollama çalışıyor mu?"


def token_tahmini(metin, rol="assistant"):
    return int(len(metin or "") / KARAKTER_PER_TOKEN.get(rol, 2.5)) + SABLON_PAYI


def gecmis_token(mesajlar):
    return sum(token_tahmini(m.get("content"), m.get("role", "assistant")) for m in mesajlar)


def gecmisi_buda(gecmis):
    """Sohbet geçmişini pencereye sığdırır. system mesajı (kurallar + KAYNAKLAR) DAİMA korunur;
    en eski soru-cevap çiftleri atılır. (atılan_çift_sayısı, sığdı_mı) döndürür.

    Neden: model hiçbir şeyi hatırlamaz; her turda geçmişin tamamı yeniden gönderilir (garsonun defteri).
    Defter uzayınca Ollama eski turları sessizce atar, üretim sırasında dolarsa kaynakların kendisi de düşer.
    Bunu Ollama'ya bırakmak yerine kendimiz, görerek ve kullanıcıya söyleyerek yapıyoruz.

    Budama gerektiğinde bütçenin %80'ine kadar iner: böylece her turda değil, birkaç turda bir budanır ve
    aradaki turlarda prompt önbelleği (aynı önek) isabet eder."""
    if not gecmis:
        return 0, True
    if gecmis[0].get("role") == "system":
        sistem, turlar = [gecmis[0]], gecmis[1:]
    else:
        sistem, turlar = [], gecmis[:]            # system yoksa ilk mesajı system sanma
    atilan = 0
    # 1) Tur sayısı sınırı: son SON_TUR_SAYISI tamamlanmış çift + cevap bekleyen yeni soru
    while len(turlar) > 2 * SON_TUR_SAYISI + 1:
        del turlar[0:2]
        atilan += 1
    # 2) Token bütçesi: system + turlar + cevap payı pencereye sığmalı
    butce = AYARLAR["num_ctx"] - CIKTI_PAYI
    sistem_tok = gecmis_token(sistem)
    if len(turlar) > 1 and sistem_tok + gecmis_token(turlar) > butce:
        hedef = butce * 0.8
        while len(turlar) > 1 and sistem_tok + gecmis_token(turlar) > hedef:
            del turlar[0:2]
            atilan += 1
    gecmis[:] = sistem + turlar
    sigdi = sistem_tok + gecmis_token(turlar) <= butce
    return atilan, sigdi


# ----------------------------------------------------------------------------------------------
# YÖNLENDİRİCİ (resepsiyonist). İki katman:
#   1) kural_tabanli_niyet : deterministik, anında. Selamlama sözlüğü; rsID / koordinat / gen+değişim desenleri
#                            (gen adı HGNC listesinde varsa tanınır). Aktif varyantla aynıysa TAKIP.
#   2) niyet_belirle       : model; aktif varyantı BİLİR ve TAKIP sınıfını tanır ("peki bu varyant BRAF'ta mı?").
# Eski sürümde resepsiyonist içerideki toplantıyı görmüyordu: gen adı geçen her takip sorusu "yeni varyant" sayılıp
# sohbet sıfırlanıyor, "kaynak 2 ne diyor?" konu dışı diye reddediliyordu.
# ----------------------------------------------------------------------------------------------
SELAM = {"merhaba", "selam", "selamlar", "günaydın", "iyi günler", "iyi akşamlar", "iyi geceler", "nasılsın",
         "nasilsin", "hey", "hello", "hi", "sa", "selamün aleyküm", "kolay gelsin"}
KIMSIN = re.compile(r"\b(sen kimsin|kimsin|ne yapars[ıi]n|ne i[şs]e yarar|nesin sen|ad[ıi]n ne|neler yapabilirsin)\b", re.IGNORECASE)
# Güçlü takip ipuçları: aktif sohbete AÇIK gönderme. Genel soru kelimeleri (hangi, kaç, neden) burada YOK;
# onlar modele gider (aktif varyantı bilir). Aksi halde "İstanbul'un nüfusu kaç?" takip sanılıyordu.
TAKIP_IPUCU = re.compile(r"\b(kaynak|kaynaklar|kaynağ\w*|özet|özetle|bu varyant\w*|bu mutasyon\w*|bunun|bunlar\w*|bununla|"
                         r"devam|daha kısa|daha uzun|kısaca|ingilizce|türkçe|yukarıda\w*|az önce)\b", re.IGNORECASE)
# Açık konu-dışı ipuçları (aktif sohbet varken modelin KONU_DISI kararını korumak için)
KONU_DISI_IPUCU = re.compile(r"\b(hava|dolar|euro|tl\b|döviz|şiir|hikaye|kod yaz|python|nüfus|tarif|yemek|futbol|maç|"
                             r"film|şarkı|tatil|saat kaç|tarih\b)\w*", re.IGNORECASE)
GONDERME = re.compile(r"\b(bu varyant\w*|bu mutasyon\w*|bunun|bununla|bu gen\w*)\b", re.IGNORECASE)
_DEG_DESEN = r"(?:p\.)?(?:[A-Za-z][a-z]{2}\d+(?:[A-Za-z][a-z]{2}|del|dup|fs\*?\d*|Ter|\*|=)|[A-Za-z]\d+(?:[A-Za-z]|del|dup|fs\*?\d*|\*|=))"
KIMLIK_RSID = re.compile(r"\brs\s?\d{3,}\b", re.IGNORECASE)
KIMLIK_KOORD = re.compile(r"(?:GRCh3[78][:\s]+|hg(?:19|38)[:\s]+)?(?:chr)?(?:2[0-2]|1[0-9]|[1-9]|X|Y|MT|M)[:\s_-]+\d{2,}[:\s_-]*[ACGT]+[>/-][ACGT]+\b", re.IGNORECASE)
KIMLIK_HGVS = re.compile(r"\b(?:N[CMPRG]_\d+(?:\.\d+)?|ENS[TPG]\d+(?:\.\d+)?):[gcnmp]\.\S+", re.IGNORECASE)
KIMLIK_GEN_DEG = re.compile(r"\b([A-Za-z][A-Za-z0-9-]{1,14})[\s:_/-]*(" + _DEG_DESEN + r")(?![A-Za-z0-9])")


def _normalize_kimlik(k):
    return re.sub(r"[\s:_/\-]|^p\.|(?<=\s)p\.", "", (k or "").upper()).replace("P.", "")


KIMLIK_GEN_IFADE = re.compile(r"\b([A-Za-z][A-Za-z0-9-]{1,14})\s+(exon\s*\d+\s*(?:skipping|deletion|del|insertion|ins)?|"
                              r"promoter\s*[A-Za-z]?\d+[A-Za-z]?|Leiden|\d+ins[ACGT]+|\d+del[ACGT]*)(?![A-Za-z0-9])", re.IGNORECASE)


def ayni_varyant(kimlik, aktif):
    """Çıkarılan kimlik aktif varyantla aynı mı, yalnızca aktif varyantın GENİ mi ('BRAF' vs 'BRAF V600E'),
    yalnızca DEĞİŞİMİ mi ('V600E'), ya da aktif varyant rsID/koordinatken çözülmüş GENİ mi ('HBB' vs rs334)?"""
    if not kimlik or not aktif:
        return False
    a, b = _normalize_kimlik(kimlik), _normalize_kimlik(aktif)
    if a == b:
        return True
    parcalar = [p.upper() for p in re.split(r"[\s:/_-]+", aktif.strip()) if p]
    aktif_gen = parcalar[0] if parcalar else ""
    if SON_BAGLAM.get("varyant") == aktif and SON_BAGLAM.get("gen"):
        aktif_gen_cozulmus = SON_BAGLAM["gen"].upper()          # rs334 -> HBB, koordinat -> BRAF
    else:
        aktif_gen_cozulmus = ""
    if a in (aktif_gen, aktif_gen_cozulmus) and a:
        return True
    return len(parcalar) > 1 and a == _normalize_kimlik(parcalar[-1])   # 'V600E' == aktif 'BRAF V600E'nin değişimi


def varyant_kimligi_bul(mesaj):
    """Mesajın içinde rsID / koordinat / HGVS / gen+değişim / gen+ifade / büyük harfli gen adı arar. Yoksa None."""
    m = KIMLIK_KOORD.search(mesaj)
    if m:
        return m.group(0).strip()
    m = KIMLIK_HGVS.search(mesaj)
    if m:
        return m.group(0).rstrip("?.,;")
    m = KIMLIK_RSID.search(mesaj)
    if m:
        return m.group(0).replace(" ", "").lower()
    for m in KIMLIK_GEN_DEG.finditer(mesaj):
        gen = m.group(1).upper()
        if gen in GEN_LISTESI:
            return f"{gen} {m.group(2).replace('p.', '')}"
    for m in KIMLIK_GEN_IFADE.finditer(mesaj):                 # "MET exon 14 skipping", "F5 Leiden", "TERT promoter C228T"
        gen = m.group(1).upper()
        if gen in GEN_LISTESI:
            return f"{gen} {m.group(2)}"
    # Yalnızca gen adı: kullanıcı BÜYÜK harfle yazmışsa ve HGNC'de varsa (MET/SET/CAT gibi sözcüklerle karışmasın diye)
    for tok in re.findall(r"\b[A-Z][A-Z0-9-]{2,14}\b", mesaj):
        if tok in GEN_LISTESI and tok not in ("DNA", "RNA", "PCR", "MRI", "ACMG", "HGVS", "VEP"):
            return tok
    return None


def kural_tabanli_niyet(mesaj, aktif_varyant=None):
    """Deterministik ön sınıflandırma. Emin olamazsa None (model karar verir)."""
    m = mesaj.strip().lower().rstrip("!?. ")
    if m in SELAM or (len(m) <= 30 and any(m.startswith(s) for s in SELAM)):
        return {"kategori": "SELAMLAMA", "varyant": "", "kaynak": "kural"}
    if KIMSIN.search(mesaj):
        return {"kategori": "KENDINI_TANIT", "varyant": "", "kaynak": "kural"}
    kimlik = varyant_kimligi_bul(mesaj)
    if kimlik:
        if aktif_varyant and ayni_varyant(kimlik, aktif_varyant):
            return {"kategori": "TAKIP", "varyant": "", "kaynak": "kural"}
        # "bu mutasyonun EGFR ile ilişkisi ne?": açık gönderme + yalnızca gen adı (değişim yok) -> aktif sohbetin takibi
        if aktif_varyant and GONDERME.search(mesaj) and re.fullmatch(r"[A-Z0-9-]+", kimlik):
            return {"kategori": "TAKIP", "varyant": "", "kaynak": "kural"}
        return {"kategori": "VARYANT", "varyant": kimlik, "kaynak": "kural"}
    if aktif_varyant:
        # Aktif varyantın yalnızca DEĞİŞİM adı geçiyorsa ("V600E kolon kanserinde ne yapar?") -> takip
        parcalar = [p for p in re.split(r"[\s:/_-]+", aktif_varyant) if p]
        if len(parcalar) > 1 and re.search(rf"(?<![A-Za-z0-9]){re.escape(parcalar[-1])}(?![A-Za-z0-9])", mesaj, re.IGNORECASE):
            return {"kategori": "TAKIP", "varyant": "", "kaynak": "kural"}
    if aktif_varyant and TAKIP_IPUCU.search(mesaj) and len(mesaj.split()) <= 25:
        return {"kategori": "TAKIP", "varyant": "", "kaynak": "kural"}
    return None


def niyet_belirle(mesaj, aktif_varyant=None):
    """Mesajı SELAMLAMA / KENDINI_TANIT / KONU_DISI / VARYANT / TAKIP olarak sınıflandırır (model);
    VARYANT ise gen/varyant kimliğini de çıkarır. Aktif varyant varsa modele söylenir."""
    baglam = (f"ŞU AN AKTİF SOHBET: kullanıcıyla '{aktif_varyant}' varyantı konuşuluyor; kaynaklar ve özet ekranda.\n"
              if aktif_varyant else "Şu an aktif bir varyant sohbeti yok.\n")
    talimat = (
        "Sen bir genetik varyant asistanının niyet sınıflandırıcısısın.\n" + baglam +
        "Kullanıcının mesajını TAM OLARAK şu kategorilerden birine ata:\n"
        "- SELAMLAMA: selam, merhaba, nasılsın gibi sohbet başlatma\n"
        "- KENDINI_TANIT: 'sen kimsin', 'ne yaparsın', 'ne işe yararsın' gibi\n"
        "- KONU_DISI: genetik/varyant DIŞI her şey (hava durumu, döviz, genel kültür...)\n"
        "- TAKIP: aktif varyant sohbetiyle ilgili devam sorusu (kaynaklar, özet, tedavi, gen, 'bu varyant', "
        "'kaynak 2 ne diyor', 'daha kısa anlat'); gen adı geçse bile aktif varyantla aynı gense TAKIP\n"
        "- VARYANT: YENİ ve FARKLI bir gen/varyant sorusu\n\n"
        "Yanıtı SADECE şu JSON formatında ver:\n"
        '{"kategori": "<KATEGORI>", "varyant": "<gen/varyant kimliği ya da boş>"}\n'
        "Kategori VARYANT ise 'varyant' alanına sorudaki gen/varyant kimliğini yaz "
        "(örn. BRAF V600E, rs334, chr1:...); değilse boş string bırak.\n\n"
        f"Mesaj: {mesaj}"
    )
    cevap = ollama.chat(
        model=SINIFLANDIRICI_MODEL,
        messages=[{"role": "user", "content": talimat}],
        format="json",
        options=AYARLAR,          # sınıflandırıcıda zar olmaz: temperature 0
    )
    try:
        niyet = json.loads(cevap["message"]["content"])
        if not isinstance(niyet, dict):
            raise ValueError
    except (json.JSONDecodeError, KeyError, ValueError):
        return {"kategori": "BELIRSIZ", "varyant": "", "kaynak": "model"}
    kategori = str(niyet.get("kategori", "")).upper().strip()
    varyant = niyet.get("varyant")
    varyant = varyant.strip() if isinstance(varyant, str) else ""
    if kategori not in ("SELAMLAMA", "KENDINI_TANIT", "KONU_DISI", "VARYANT", "TAKIP"):
        kategori = "BELIRSIZ"
    if kategori == "VARYANT" and aktif_varyant and ayni_varyant(varyant, aktif_varyant):
        kategori, varyant = "TAKIP", ""                 # model 'BRAF' dedi ama aktif varyant BRAF V600E: takip
    if kategori == "KONU_DISI" and aktif_varyant and not KONU_DISI_IPUCU.search(mesaj) and len(mesaj.split()) <= 12:
        kategori = "TAKIP"      # aktif sohbette kısa, açıkça konu dışı olmayan soru ("orak hücre ile ilişkisi ne?") takiptir;
                                # yanlışsa grounded model zaten 'bilgi yok' der (zararsız), konu dışı reddi ise bilgiyi keser
    return {"kategori": kategori, "varyant": varyant, "kaynak": "model"}


def niyet(mesaj, aktif_varyant=None):
    """Önce kural, sonra model."""
    return kural_tabanli_niyet(mesaj, aktif_varyant) or niyet_belirle(mesaj, aktif_varyant)


def varyant_baglami_kur(varyant):
    """Bir varyant için kaynakları kademeli arar (c07), anlamlandırma kartını ve uyarıları basar,
    grounded sohbet system mesajını hazırlar. (makaleler, system_mesaji) döndürür; kaynak yoksa (None, None).
    Kaynaklar GEN düzeyindeyse (varyanta özgü makale yok) 3. kural yumuşatılır: varyant hakkında iddia yasak,
    gen hakkında özet serbest. Kademe/gen bilgisi SON_BAGLAM'a yazılır (ilk_soru bunu kullanır)."""
    SON_BAGLAM.clear()
    s = kaynaklari_getir(varyant, adet=5)
    kayit, kart = s["kayit"], s["kayit"].get("kart")
    if kart and "hata" not in kart:
        print(f"  Anlamlandırma: {kart.get('kanonik_gen')} {kart.get('protein_kisa') or kart.get('etki')} | "
              f"rsID: {', '.join(kart.get('rsid') or []) or '-'} | gnomAD: {kart.get('gnomad_af')} | CADD: {kart.get('cadd')} | "
              f"klinik önem (VEP): {', '.join(kart.get('klinik_onem') or []) or '-'}")
    for u in s["uyarilar"]:
        print(f"  UYARI: {u}")
    # ClinVar kaydı ÜRETİMDEN ÖNCE (ve makale bulunamasa bile) çekilir; kayıt paylaşılır ki VEP'e ikinci kez gidilmesin
    try:
        cv = clinvar_bilgisi(varyant, kayit=kayit)
    except Exception as e:
        cv = None
        print(f"  (ClinVar'a ulaşılamadı: {type(e).__name__})")
    SON_BAGLAM.update(varyant=varyant, gen=kayit.get("gen"), clinvar=cv, kart=kart, kademe=s["kademe"], n_kaynak=0)
    if s["kademe"] in ("yok", "hata") or not s["makaleler"]:
        return None, None
    say = s["sayilar"]
    print(f"  PubMed: varyanta özgü {say.get('varyant_toplam', 0)} makale"
          + (f", gen düzeyi {say['gen_toplam']}" if say.get("gen_toplam") is not None else "")
          + f"; {len(s['makaleler'])} kaynak seçildi ({s['kademe']} düzeyi).")
    makaleler = s["makaleler"]
    gen = kayit.get("gen") or "ilgili gen"
    SON_BAGLAM.update(kademe=s["kademe"], gen=gen, varyant=varyant, n_kaynak=len(makaleler))
    veritabani = ""
    if VERITABANI_PROMPTA and (cv or (kart and "hata" not in kart)):
        satirlar = []
        if cv and cv.get("germline"):
            satirlar.append(f"ClinVar germline: {cv['germline']['onem']} ({cv['germline']['yildiz']} yıldız)")
        if kart and "hata" not in kart and kart.get("gnomad_af") is not None:
            satirlar.append(f"gnomAD sıklığı: {kart['gnomad_af']}")
        veritabani = "VERİTABANI BİLGİSİ (kaynaklarla çelişirse çelişkiyi açıkça söyle): " + "; ".join(satirlar) + "\n\n"
    sistem = sistem_metni(varyant, makaleler, s["kademe"], gen, veritabani)
    return makaleler, sistem


def sistem_metni(varyant, makaleler, kademe="varyant", gen=None, veritabani=""):
    """Grounded system mesajı. Varyant modunda fine-tune eğitim verisiyle BİREBİR aynı (train/serve eşitliği);
    gen modunda 3. kural yumuşatılır (aksi halde 7B model 'varyantı özetle' sorusuna yalnızca ret cümlesiyle cevap veriyor).
    Toplu üretim/ölçüm betikleri (b06) de bu fonksiyonu kullanır: canlı sistemle aynı metin."""
    if kademe == "gen":
        kural3 = (f"- Kaynaklar '{varyant}' varyantının kendisini anmıyor (gen düzeyi). Varyantın etkisi, patojenitesi ya da "
                  f"hastalık ilişkisi hakkında iddia üretme; yalnızca {gen or 'ilgili gen'} geni hakkında kaynaklarda yazanı özetle. "
                  "Sorulan konu kaynaklarda yoksa: 'Bu konuda elimdeki kaynaklarda bilgi yok.'\n")
    else:
        kural3 = "- Cevap kaynaklarda yoksa yalnızca şunu de: 'Bu konuda elimdeki kaynaklarda bilgi yok.'\n"
    return (
        f"Sen bir genetik varyant asistanısın. '{varyant}' hakkında SADECE aşağıdaki KAYNAKLAR'a "
        "dayanarak yanıt verirsin. Yanıtın DAİMA ve TAMAMEN Türkçe olmalı; başka dil kullanma.\n\n"
        "Kurallar:\n"
        "- Yalnızca kaynaklarda yazan bilgiyi kullan; kendi bilginden ekleme, tahmin etme, uydurma.\n"
        "- Her cümlenin sonuna dayandığı kaynağı yaz: [1], [2]. Kaynağı olmayan cümle yazma.\n"
        f"{kural3}\n"
        f"{veritabani}"
        f"KAYNAKLAR:\n{baglam_metni(makaleler)}"
    )


def ilk_soru(varyant):
    """Özet sorusu: varyant düzeyinde 'X varyantını kaynaklı olarak özetle.' (eğitim verisiyle aynı);
    gen düzeyinde genin kendisi hakkında sorulur (model reddetme şablonuna kaçmasın)."""
    if SON_BAGLAM.get("kademe") == "gen":
        return f"{SON_BAGLAM.get('gen')} geni hakkında kaynaklı bir özet yaz."
    return f"{varyant} varyantını kaynaklı olarak özetle."


def grounded_sor(gecmis, kullanici_mesaji):
    """Grounded sohbete bir mesaj sorar, cevabı döndürür.
    Geçmişe (soru, cevap) çifti yalnızca BAŞARILI çağrıda yazılır; hata olursa geçmiş bozulmaz."""
    aday = gecmis + [{"role": "user", "content": kullanici_mesaji}]
    atilan, sigdi = gecmisi_buda(aday)
    if atilan:
        print(f"  (pencere dolmasın diye en eski {atilan} konuşma turu çıkarıldı; kaynaklar korunuyor)")
    if not sigdi:
        print("  (UYARI: kaynaklar + soru pencereye sığmıyor; cevap eksik bağlamla üretilebilir)")
    # Yeni Ollama sürümleri model aynı kelimeyi durmadan tekrar edince üretimi keser ('token repeat limit reached').
    # O zaman bir kez, hafif sıcaklık ve başka tohumla yeniden üretilir; yine olursa hata yukarı iletilir.
    dongu = False
    try:
        cevap = ollama.chat(model=MODEL, messages=aday, options=AYARLAR)
    except ollama.ResponseError as e:
        if "repeat" not in str(e).lower():
            raise
        print("  (UYARI: model tekrar döngüsüne girdi; farklı tohumla yeniden üretiliyor)")
        cevap = ollama.chat(model=MODEL, messages=aday, options=dict(AYARLAR, temperature=0.3, seed=AYARLAR["seed"] + 1))
        dongu = True
    icerik = cevap["message"]["content"]
    SON_YANIT.clear()
    if dongu:
        SON_YANIT["tekrar_dongusu"] = True
    # Dil çöküşü (Türkçe -> Çince): bir kez, hafif sıcaklıkla yeniden üret; yine olmazsa 'bozuk' işaretle, geçmişe YAZMA
    oran = dil_denetimi(icerik)
    if oran > 0.02:
        print(f"  (UYARI: cevapta yabancı alfabe oranı %{100 * oran:.0f}; yeniden üretiliyor)")
        cevap = ollama.chat(model=MODEL, messages=aday, options=dict(AYARLAR, temperature=0.3, seed=AYARLAR["seed"] + 1))
        icerik = cevap["message"]["content"]
        SON_YANIT["yeniden_uretildi"] = True
        oran = dil_denetimi(icerik)
        if oran > 0.02:
            print("  (UYARI: cevap yine bozuk; güvenilmez sayılır, sohbet geçmişine yazılmaz)")
            SON_YANIT["bozuk"] = True
    SON_YANIT["cjk_orani"] = round(oran, 3)
    icerik, n = ceviri_duzelt(icerik)                # deterministik çeviri düzeltmesi (büyük harf korunur)
    if n:
        print(f"  (çeviri düzeltildi: {n} yer)")
    # Gözlemlenebilirlik: Ollama gerçek token sayılarını döndürür; pencereye ne kadar yaklaştığımızı görelim
    girdi_token = getattr(cevap, "prompt_eval_count", None)
    cikti_token = getattr(cevap, "eval_count", None)
    bitis = getattr(cevap, "done_reason", None)
    if girdi_token:
        print(f"  (bağlam {girdi_token} / {AYARLAR['num_ctx']} token; cevap {cikti_token} token)")
    if bitis == "length":
        print(f"  (UYARI: cevap {AYARLAR.get('num_predict', CIKTI_PAYI)} token sınırında kesildi)")
        icerik, atildi = kesik_cumleyi_at(icerik)       # yarım son cümle atılır (atıfsız sayılmasın, geçmişe girmesin)
        if atildi:
            SON_YANIT["kesik_cumle_atildi"] = True
    # Atıf denetimi: geçersiz numaralar silinir, atıfsız cümleler sayılır. Kaynak sayısı SON_BAGLAM'dan; yoksa system mesajından sayılır
    n_kaynak = SON_BAGLAM.get("n_kaynak") or len(re.findall(r"^\[(\d+)\] Başlık:", aday[0].get("content", ""), re.M)) or 5
    icerik, rapor = atif_denetimi(icerik, n_kaynak)
    SON_YANIT.update(rapor)
    if rapor["gecersiz_atif"]:
        print(f"  (UYARI: var olmayan kaynak numarası silindi: {rapor['gecersiz_atif']})")
    if rapor["atifsiz_cumle"]:
        print(f"  (UYARI: {rapor['atifsiz_cumle']}/{rapor['cumle']} cümle kaynak göstermiyor)")
    celiski = celiski_denetimi(icerik)
    SON_YANIT["celiski"] = celiski
    if celiski:
        print(f"  (UYARI: {celiski})")
    SON_YANIT.update(girdi_token=girdi_token, cikti_token=cikti_token, bitis=bitis,
                     sure_ms=int((getattr(cevap, "total_duration", 0) or 0) / 1e6) or None)
    if not SON_YANIT.get("bozuk"):                    # bozuk cevap bağlama girmez (model kendi Çince çıktısını görüp çöküşü sürdürmesin)
        gecmis[:] = aday + [{"role": "assistant", "content": icerik}]
    return icerik


def main():
    print("Genetik varyant asistanı (yerel). Bir varyant sorabilir ya da sohbet edebilirsiniz.")
    print("Çıkmak için 'çık' yaz.\n")

    grounded = None        # aktif varyantın sohbet geçmişi (ollama messages) ya da None
    aktif_varyant = None

    try:
        while True:
            mesaj = input("Sen: ").strip().lstrip("﻿")
            if mesaj.lower() in ("çık", "cik", "exit", "quit", ""):
                print("Görüşürüz!")
                break

            try:
                karar = niyet(mesaj, aktif_varyant)     # önce kural katmanı, sonra aktif varyantı bilen model
            except Exception as e:                      # Ollama kapalı / bağlantı hatası: çökme, söyle
                print(f"\nBot: {model_hata_mesaji(e)}\n")
                continue
            kategori = karar.get("kategori", "BELIRSIZ")

            # --- Konu dışı / sohbet: KOD sabit cevap verir (LLM'e bırakılmaz) ---
            if kategori == "SELAMLAMA":
                print("\nBot: Merhaba! Bir genetik varyant (örn. BRAF V600E) sorabilirsiniz.\n")
                continue
            if kategori == "KENDINI_TANIT":
                print("\nBot: Ben bir genetik varyant asistanıyım. Bir varyant girerseniz, ilgili "
                      "bilimsel makaleleri bulup kaynaklı bir özet çıkarırım.\n")
                continue
            if kategori == "KONU_DISI":
                print("\nBot: Ben yalnızca genetik varyantlar için varım; bu tür sorulara "
                      "cevap veremem.\n")
                continue
            if kategori == "BELIRSIZ":
                print("\nBot: Anlayamadım. Bir varyant (örn. BRAF V600E, rs334, chr7:140753336:A>T) ya da "
                      "aktif varyantla ilgili bir soru yazabilirsiniz.\n")
                continue
            if kategori == "TAKIP":
                if grounded is None:
                    print("\nBot: Henüz aktif bir varyant yok. Önce bir varyant sorun (örn. BRAF V600E).\n")
                    continue
                print("  (yanıt üretiliyor...)")
                try:
                    print(f"\nBot: {grounded_sor(grounded, mesaj)}\n")
                    if SON_YANIT.get("bozuk"):
                        print("DİKKAT: Bu cevap dil bozukluğu içeriyor (yabancı alfabe); güvenilmez sayın, soruyu yeniden sorun.\n")
                except Exception as e:
                    print(f"\nBot: {model_hata_mesaji(e)}\n")
                continue

            # --- Varyant sorusu: RAG hattı ---
            varyant = (karar.get("varyant") or "").strip()
            if varyant and not ayni_varyant(varyant, aktif_varyant):
                # VALİDASYON: gen sembolü geçerli mi? (rsID/koordinat/HGVS için atlanır; onları VEP doğrular)
                gen = gen_cikar(varyant)
                if gen is not None:
                    gecerli, oneriler = gen_gecerli_mi(gen)
                    if not gecerli:
                        if oneriler:
                            print(f"\nBot: '{gen}' geçerli bir gen değil. Şunu mu demek istediniz: "
                                  f"{', '.join(oneriler)}?\n")
                        else:
                            print(f"\nBot: '{gen}' geçerli bir gen sembolü değil; kontrol eder misiniz?\n")
                        continue
                # Yeni varyant: kaynakları çek, grounded sohbeti kur, özet üret.
                # Başarısız olursa (kesinti ya da makale yok) aktif sohbet ESKİ varyantta kalır; bağlamı da geri yüklenir
                # (yoksa takip sorusunda n_kaynak=0 ile tüm atıflar 'geçersiz' silinir, çelişki denetimi yanlış ClinVar'la çalışır)
                onceki_baglam = dict(SON_BAGLAM)
                try:
                    makaleler, sistem = varyant_baglami_kur(varyant)
                except Exception as e:                  # PubMed / VEP kesintisi: çökme, söyle
                    SON_BAGLAM.clear(); SON_BAGLAM.update(onceki_baglam)
                    print(f"\nBot: Kaynaklar çekilemedi ({type(e).__name__}: {str(e)[:120]}). Biraz sonra tekrar deneyin.\n")
                    continue
                if not makaleler:
                    print(f"\nBot: '{varyant}' ile ilgili makale bulunamadı.")
                    if SON_BAGLAM.get("clinvar"):           # literatür yoksa bile veri tabanı kaydı gösterilir
                        print()
                        for satir in clinvar_satirlari(SON_BAGLAM["clinvar"]):
                            print(satir)
                    print()
                    SON_BAGLAM.clear(); SON_BAGLAM.update(onceki_baglam)
                    continue
                aktif_varyant = varyant
                grounded = [{"role": "system", "content": sistem}]
                if SON_BAGLAM.get("kademe") == "gen":
                    # Uyarı KOD tarafından, deterministik: modele bırakılmaz
                    print(f"\nBot: Not: '{varyant}' için varyanta özgü yayın bulunamadı; aşağıdaki özet "
                          f"{SON_BAGLAM['gen']} geni hakkındadır, varyantın etkisi hakkında bir şey söylemez.")
                print("  (özet üretiliyor, biraz sürebilir...)")
                try:
                    ozet = grounded_sor(grounded, ilk_soru(varyant))
                except Exception as e:
                    print(f"\nBot: {model_hata_mesaji(e)}\n")
                    continue
                print(f"\nBot:\n{ozet}\n")
                if SON_YANIT.get("bozuk"):
                    print("DİKKAT: Bu cevap dil bozukluğu içeriyor (yabancı alfabe); güvenilmez sayın, soruyu yeniden sorun.\n")
                print("Kaynaklar:")
                for i, m in enumerate(makaleler, start=1):
                    etiket = " (gen düzeyi)" if m.get("alaka") == "gen" else ""
                    print(f"[{i}] {m['baslik']}{etiket} — {kunye(m)} — https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
                # ClinVar klinik önem katmanı (üretimden önce çekildi; yalnızca güvenle doğrulanırsa gösterilir)
                cv = SON_BAGLAM.get("clinvar")
                if cv:
                    print()
                    for satir in clinvar_satirlari(cv):
                        print(satir)
                if SON_YANIT.get("celiski"):
                    print(f"\nDİKKAT: {SON_YANIT['celiski']}")
                print(f"\n{ARASTIRMA_UYARISI}\n")
            elif grounded is not None:
                # Takip sorusu: mevcut varyantın grounded sohbetine sor
                print("  (yanıt üretiliyor...)")
                try:
                    print(f"\nBot: {grounded_sor(grounded, mesaj)}\n")
                    if SON_YANIT.get("bozuk"):
                        print("DİKKAT: Bu cevap dil bozukluğu içeriyor (yabancı alfabe); güvenilmez sayın, soruyu yeniden sorun.\n")
                except Exception as e:
                    print(f"\nBot: {model_hata_mesaji(e)}\n")
            else:
                print("\nBot: Hangi varyantı sormak istiyorsunuz? (örn. BRAF V600E)\n")
    except (KeyboardInterrupt, EOFError):
        print("\nGörüşürüz!")


if __name__ == "__main__":
    main()
