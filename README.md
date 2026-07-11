# VarChat Benzeri Genetik Varyant RAG Chatbotu

Yüksek lisans tez projesi. Amaç: Bir genetik varyant girildiğinde, ilgili bilimsel
literatürü bulup özetleyen ve **kaynak gösteren** bir chatbot geliştirmek.
Referans alınan araç: [VarChat](https://varchat.engenome.com) (enGenome, 2024).

---


## 1. Amaç

Bir hastanın DNA'sı dizilendiğinde binlerce genetik varyant çıkar. Bir araştırmacının
"bu varyant zararlı mı?" sorusuna cevap vermek için yüzlerce makaleyi taraması gerekir.
Bu proje, o varyantla ilgili literatürü otomatik bulup, **uydurma yapmadan, kaynaklı**
bir özet üreten bir sistem kurmayı hedefler.


## 2. Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

- **Gemini sürümü için** (`c03_varchat_gemini.py`): `.env` dosyasına
  `GEMINI_API_KEY=...` eklenmelidir.
- **Yerel sürüm için** (`c04_varchat_ollama.py`): [Ollama](https://ollama.com) kurulu olmalı ve
  model indirilmelidir: `ollama pull qwen2.5:7b`.


## 3. Temel Kavramlar (ne nedir?)

- **LLM (Büyük Dil Modeli):** Metnin devamını tahmin ederek cevap üreten yapay zeka
  (ChatGPT gibi). Tek başına bilgiyi ezberinden verir ve uydurabilir (halüsinasyon).
- **RAG (Retrieval-Augmented Generation):** "Açık kitap sınavı" mantığı. Model cevap
  vermeden önce ona ilgili belgeleri bulup veririz; o da sadece bunlara dayanır.
- **Retrieval (Bulucu):** İlgili makaleleri bulan arama parçası.
- **Embedding:** Metni, anlamını yakalayan sayılara (vektör) çevirme. Anlamca benzer
  metinler birbirine yakın olur; "anlam araması" bununla yapılır.
- **Fine-tuning (İnce ayar):** Hazır bir modeli, kendi görevimize uyacak şekilde küçük
  bir veriyle yeniden eğitmek (sıfırdan eğitmek değil). Modele *nasıl cevap vereceğini*
  öğretir; bilgiyi yine RAG/bulucu sağlar.
  *Analoji:* Türkçeyi ve genel kültürü zaten bilen bir çalışana sıfırdan dil öğretmek
  yerine, "bizde raporlar şu formatta yazılır" diye kısa bir **oryantasyon** vermek gibi.
- **LoRA (Low-Rank Adaptation):** Fine-tuning'i ucuza yapma yöntemi. Modelin
  milyarlarca parametresine dokunmadan (dondurarak), üstüne küçük bir "ayar katmanı"
  ekleyip yalnızca onu eğitiriz. Eğitilen parametre milyarlardan birkaç milyona iner;
  böylece küçük/ücretsiz bir GPU'da bile çalışabilir.
  *Analoji:* Koca bir ders kitabını baştan yazmak yerine üstüne ince, şeffaf bir
  **asetat** koymak gibi — orijinal kitap aynı kalır, senin eklediğin küçük notlar onu yönlendirir.

### Bir LLM nasıl eğitilir? (3 aşama)

Modern bir dil modeli üç aşamadan geçer. Bilginin büyük kısmı 1. aşamadan gelir;
soru–cevap (bizim fine-tune'da yaptığımız) yalnızca 2. aşamadır.

| Aşama | Ne yapılır | Analoji |
|---|---|---|
| 1. Ön eğitim (pre-training) | Trilyonlarca **ham metinle** "sıradaki kelimeyi tahmin et" | Bütün kütüphaneyi okuyup dünyayı öğrenmek (ama nasıl yardımcı olunacağını bilmeden) |
| 2. Talimat ayarı (SFT) | **Soru→cevap** örnekleriyle davranış öğretme | Kısa bir **oryantasyon**: "soruya böyle cevap ver" |
| 3. İnsan geri bildirimi (RLHF) | İnsan tercihleriyle cevapları cilalama | Mentörün "bu cevabın şundan iyiydi" demesi |

Bu projede 1. ve 3. aşama yok; hazır eğitilmiş bir modeli alıp yalnızca 2. aşamayı
(SFT) küçük ölçekte uyguluyoruz.


## 4. VarChat Nasıl Çalışıyor? (İnceleme Notları)

Referans aracı VarChat'i gerçek girdilerle test ederek nasıl çalıştığını çözdük. Akışı özetle:

```
Girdi → [1] Doğrula (geçerli gen/varyant mı?)  → geçersizse reddet
      → [2] Anlamlandır (gen / HGVS / rsID / koordinat kabul eder)
      → [3a] Literatürü tara + kaynaklı özet (RAG)     [NCBI, PubMed Central, Google Scholar]
      → [3b] Veri tabanlarını sorgula (anotasyon + sınıflandırma)  [gnomAD, CADD, REVEL, ACMG, ClinVar]
      → [4] İkisini birleştirip, "yanlış olabilir" uyarısıyla sun
```

**Gözlemler:**
- **İki katmanlı çıktı:** (A) makalelerden gelen *kaynaklı literatür özeti* + (B) veri tabanlarından gelen
  *anotasyon & ACMG sınıflandırması*. Bilginin kaynağını ayrı tutuyor.
- **Girdi doğrulama var:** geçersiz girdiyi (örn. "merhaba") reddediyor — sohbet botu değil, varyant/gen aracı.
- **Literatür yoksa dürüst:** "supporting literature bulunamadı" deyip gen düzeyi bilgiye düşüyor
  (nadir varyantlarda kaçınılmaz; bizim sistemimiz de aynısını yapıyor).
- **Kalite literatüre bağlı:** çok çalışılmış varyantta (BRAF V600E) çok zengin; nadir varyantta zayıf.
- **Tek atışlık + deterministik değil:** takip sorusu soramıyorsun (enGenome "yakında" diyor);
  ayrıca her çalıştırmada biraz farklı cevap üretir.

**Artıları:** çok kaynaklı, kaynaklı/doğrulanabilir özet, ACMG sınıflandırması, girdi doğrulama, dürüst uyarı.
**Sınırları:** sohbet edemez, nadir varyantta zayıf, İngilizce ağırlıklı, doğruluğu garanti etmez, modeli kapalı.

### VarChat'in kullandığı veri tabanları/araçlar (kısa sözlük)

- **ClinVar** — varyant ↔ hastalık ilişkisi ve klinik önem (patojenik/benign) kayıtları (NIH).
- **gnomAD** — varyantın toplumdaki görülme **sıklığı** (çok yaygın ≈ zararsız ipucu).
- **CADD** — varyantın **zararlılık tahmin skoru** (yüksek = daha muhtemel zararlı).
- **REVEL** — missense varyantlar için **0–1** arası zararlılık skoru (1'e yakın = daha muhtemel zararlı).
- **ACMG/AMP** — patojenik/benign **sınıflandırma için standart kurallar kılavuzu** (kanıt kodları: PM1, PP3...).

### Çıktıyı yakından inceleyince (ek gözlemler)

- **"Çok getir → azını kullan" hunisi:** 27.836 kaynak bulunur, 15'i listelenir, özette yalnızca ~5'i atıf alır.
- **Güncellik ağırlığı:** listelenen makalelerin hepsi son 1-2 yıl (yeni yayınlara daha yüksek puan).
- **Uyarlanabilir çıktı:** veri kıt varyantta (nadir rsID) kaynak/ClinVar bölümlerini **hiç göstermiyor**, uydurmuyor.
- **Otomatik sınıflandırıcı yanılabilir:** rs334 (orak hücre, kesin patojenik) VarChat'in otomatik ACMG'sinde
  "belirsiz/benign" çıktı — sıklık-tabanlı kurallar hastalık mekanizmasını kaçırabiliyor (değerlendirme neden önemli).


## 5. Genişletilmiş Proje Planı ve Mimari

Projenin güncel, ayrıntılı yol haritası.

### 5.1 Nihai sistem mimarisi

```
Kullanıcı mesajı
   │
   ▼
[0] YÖNLENDİRİCİ (niyet)
   ├─ selamlama ("merhaba")         → doğrudan, samimi cevap
   ├─ kendini tanıt ("sen kimsin")  → "Genetik varyant asistanıyım..."
   ├─ konu dışı ("hava durumu?")    → kibar ret (web arama YOK, uydurma YOK)
   └─ varyant/gen sorusu ↓
        │
        ▼
[1] VALİDASYON: varyant/gen geçerli mi?  ── değilse → "bunu mu demek istediniz: BRAF?"
        │ geçerli
        ▼
[2] ANLAMLANDIRMA (VEP): koordinat → gen / rsID / etki           [✅ kuruldu]
        │
        ▼
[3] RETRIEVAL (PubMed): ilgili makaleleri bul                     [✅ kuruldu]
        │   "X makale bulundu, en alakalı/güncel N tanesi özetlendi"
        ▼
[4] GENERATION: model makaleleri okur → kaynaklı Türkçe özet      [beyin: fine-tune'lu yerel model]
        │
        ▼
[5] SOHBET: takip soruları (hafıza)                              [✅ kuruldu]
```

**Temel ilke:** Model uydurmaz; gerçek bilgi VEP + PubMed'den gelir. Model yalnızca *yönlendirir* ve *verilen kaynakları özetler.*

### 5.2 Bileşen kararları

- **Model (beyin):** Model-bağımsız tasarım — istediğimiz zaman değiştiririz. Geliştirmede küçük/hızlı (qwen2.5:3b, CPU); final kalitede GPU'da büyük model. Dış API yok, Ollama ile yerel.
- **Yönlendirici (router):** Mesajın niyetini ayırır. Pratikte: basit kurallar (bariz selamlamalar) + model (gerisi).
- **Validasyon:** Sohbet dilindeki yazım hatalarını model bağlamdan anlar; ama **varyant/gen kimliğini** referansa (gen listesi / VEP) karşı doğrularız — yanlış gen yanlış sonuç getirir.
- **Güvenlik (prompt injection):** Kullanıcı "kuralları yok say / admin ol" gibi denemeler (jailbreak) yapabilir; hiçbir LLM %100 bağışık değildir. Zarar tasarımla sınırlanır: konu-dışı yanıtı **kod** (LLM değil) sabit döndürür, üretim **grounded**'dır (yalnızca makalelere dayanır), sistemin **tehlikeli bir yetkisi yoktur**. İleride adversarial testlerle ölçülecek.

### 5.3 Retrieval stratejisi (özet → tam metin)

| | Şimdi (geliştirme) | İleride (kendi retriever) |
|---|---|---|
| Kaynak | PubMed **özetleri** (API) | **Tam metin** (PMC / ~45M korpus) |
| Yöntem | Özeti direkt modele ver | **Chunking + embedding** → ilgili parçalar |
| Sıralama | PubMed'in alaka + güncellik sıralaması | Kendi **hybrid** (BM25 + embedding) sıralamamız |

- **Kaç makale:** 5 ile başla (yerel model için bağlam/hız dengesi), ayarlanabilir; GPU'da 15'e çıkılabilir.
- **Gösterim:** "X makale bulundu, en alakalı N tanesi özetlendi" (PubMed toplam sayıyı zaten döndürür).

### 5.4 Doğrulama (nasıl kontrol edeceğiz)

- **VEP:** Bilinen varyantlarla test (`BRAF V600E`→BRAF, `rs334`→HBB) + dbSNP/ClinVar ile karşılaştırma.
- **PubMed alaka:** Gen/varyant adı makalede geçiyor mu (basit kontrol) + **PubTator3 / LitVar2** referansına karşı precision ölçümü.

### 5.5 Fine-tune ve veri

- **Yöntem:** LoRA/QLoRA (model-bağımsız), Colab GPU → GGUF → Ollama. Fine-tune **zorunlu değil, kaliteyi cilalayan** adım.
- **Veri (iki katman):**
  - *Hazır setler (genel/alan):* PubMedQA, BioASQ (biyomedikal QA), talimat setleri, Türkçe setler, ClinVar.
  - *Kendi ürettiğimiz (göreve özel):* Gemini "öğretmen" ile **distillation** — (varyant → makale → iyi özet) çiftleri.

### 5.6 Veri kaynakları: API mı, yerel mi?

PubMed ve VEP ücretsiz API'lerle kullanılıyor; ama **ikisi de indirilip yerelde (offline) çalıştırılabilir**
(PubMed baseline dökümü; VEP standalone + cache). Geliştirmede API, final offline sistemde yerel.

### 5.7 Faz planı

| Faz | İş | Durum |
|---|---|---|
| 1 | RAG hattı (anlamlandırma + retrieval + üretim + sohbet) | ✅ büyük ölçüde bitti |
| 2 | Yönlendirici + validasyon (sohbet katmanı) | ✅ bitti |
| 3 | Eğitim verisi (distillation + hazır setler) | sıradaki |
| 4 | Fine-tune (LoRA) → GGUF → Ollama | sonra |
| 5 | Fine-tune'lu modeli hatta tak | sonra |
| 6 | Benchmark / değerlendirme | sonra |
| 7 | Kendi retriever (tam metin + chunking + hybrid) | sonra |
| 8 | Web arayüzü | en son |


## 6. Proje Dosyaları ve Şimdiye Kadar Yapılanlar

> Not: Dosyalar pipeline sırasına göre `c01_`, `c02_`... diye numaralandı.
> (Python modül adı rakamla başlayamaz; bu yüzden harfli `c` öneki kullanıldı ki
> dosyalar birbirini sorunsuz `import` edebilsin.)

### Ana klasör — çalışan pipeline

| # | Dosya | Rol |
|---|---|---|
| 1 | `c01_makale_getir.py` | **Retrieval (bulucu):** varyantı PubMed'de aratıp makale başlık+özetlerini çeker (NCBI E-utilities). |
| 2 | `c02_varyant_anlamlandir.py` | **Anlamlandırma:** koordinatı (`chr1:...` / `GRCh38:...`) VEP ile gen / rsID / etkiye çevirir. |
| 3 | `c03_varchat_gemini.py` | **Sohbet eden RAG (Gemini):** özet + takip soruları + koordinat yönlendirme. Ortak yardımcılar burada. |
| 4 | `c04_varchat_ollama.py` | **ANA UYGULAMA:** yönlendirici + validasyon + sohbet + RAG, **tamamen yerel** (Ollama/qwen2.5) — dış API yok. |
| 5 | `c05_gen_validasyon.py` | **Validasyon:** gen kimliği geçerli mi? Yanlış yazımı (BRFA→BRAF) HGNC listesi + Jaro-Winkler ile yakalar; `genler.txt`'yi bir kez indirir. |

### `arsiv/` — öğrenme / test dosyaları

| # | Dosya | Rol |
|---|---|---|
| 1 | `a01_gemini_test.py` | Gemini bağlantısını doğrulayan küçük test. |
| 2 | `a02_varchat_sohbetsiz_test.py` | Sohbetsiz (tek-atışlık) VarChat denemesi — Gemini (eski `varchat.py`). |
| 3 | `a03_sohbet_test.py` | Sohbet hafızasının çalıştığını gösteren test. |
| 4 | `a04_ollama_test.py` | Yerel modelin (Ollama) çalıştığını gösteren test. |
| 5 | `a05_yonlendirici_test.py` | Niyet sınıflandırıcı (router) izole testi. |

### Şimdiye kadar tamamlananlar

- ✅ PubMed'den makale çekme (retrieval)
- ✅ VEP ile varyant anlamlandırma (koordinat girişi desteği)
- ✅ Gemini ile RAG: tek-atışlık + sohbet eden (takip soruları)
- ✅ Tamamen **yerel** sohbet (Ollama / qwen2.5:7b) — internetsiz, gizli
- ✅ Yönlendirici (router): niyet sınıflandırma + sohbet katmanı (selamlama / konu-dışı / varyant)
- ✅ Validasyon: yanlış gen yazımını yakalama + öneri (HGNC + Jaro-Winkler)
- ✅ Fine-tune mekaniği (Colab, LoRA — küçük demo)
