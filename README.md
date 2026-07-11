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

## 2. Temel Kavramlar (ne nedir?)

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

## 3. Sistem Mimarisi (akış)

```
Varyant gir → [BULUCU] ilgili makaleleri bul → [BEYİN] makaleleri okuyup kaynaklı özet üret
```

RAG'ın iki yarısı da bu projede **bize ait** olacak:
- **Bulucu:** Kendi makale havuzumuz üzerinde embedding + hybrid arama.
- **Beyin:** Dışa bağımlı API değil, kendi (fine-tune edilmiş) açık kaynak modelimiz.

## 4. Şimdiye Kadar Yapılanlar (prototip)

Çalışan bir ilk prototip kuruldu (öğrenme amaçlı, ileride parçaları değişecek):

- `makale_getir.py` — Varyantı **PubMed**'de aratıp ilgili makalelerin başlık ve
  özetlerini çeker (NCBI E-utilities API). *Bulucu adımı.*
- `gemini_test.py` — Gemini'nin tek başına çalıştığını doğrulayan küçük test.
- `varchat.py` — İkisini birleştirir: makaleleri çeker, Gemini'ye bağlam olarak verir,
  "sadece kaynaklara dayan, her bilginin yanına kaynağını yaz" kurallarıyla kaynaklı
  bir Türkçe özet ürettirir. *Çalışan ilk RAG döngüsü.*

Mevcut sınırlar: makale seçimini PubMed yapıyor (kendi aramamız yok), sadece özet var
(tam metin değil), dış API (Gemini) kullanılıyor, girdi denetimi yok.

## 5. Kararlar (danışmanla netleşen yön)

- **Girdi:** Gen adı değil, **genomik koordinat** formatında varyant
  (örn. `chr1:17001759:A>T`). Bunlar PubMed'de doğrudan aranamaz; önce
  **anlamlandırma (annotation)** ile gen/rsID'ye çevrilmeli.
- **Bulucu:** Danışmanın elindeki **~45 milyon makalelik tam metin PubMed** korpusu
  üzerinde **kendi embedding + hybrid arama** sistemimizi kuracağız.
- **Model:** Dış API yok. **Açık kaynak bir modeli (Llama/Mistral) fine-tune** edeceğiz
  (sıfırdan eğitim yok). GPU danışman tarafından sağlanmaya çalışılacak.
- **Değerlendirme:** **Benchmark/validasyon yapılacak** (tezin temel katkılarından biri).
- **Web arayüzü:** Ürünleşme aşamasına ait; şimdilik ertelendi. Önce model + validasyon.

## 6. Yapılacaklar (yol haritası)

1. **Fine-tune örneği:** Küçük bir açık modeli Google Colab (ücretsiz GPU) üzerinde
   LoRA ile fine-tune eden bir örnek + dokümantasyon. *(Sıradaki adım.)*
2. **Varyant anlamlandırma:** Genomik koordinatı gen/rsID'ye çeviren adım (VEP/dbSNP vb.).
3. **Kendi bulucumuz:** 45M korpusu indeksleyip embedding + hybrid arama kurmak.
4. **Kendi modelimizi entegre etmek:** Fine-tune edilmiş açık modeli RAG'a bağlamak.
5. **Benchmark/validasyon:** Sistemi ölçmek (örn. ClinVar referans alınarak).
6. *(Sonra)* Web arayüzü.

## 7. Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Gemini testi için `.env` dosyasına `GEMINI_API_KEY=...` eklenmelidir.

## 8. VarChat Nasıl Çalışıyor? (İnceleme Notları)

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
- **Dil:** İngilizce üretip 30+ dile çeviriyor (biz Gemini ile doğrudan Türkçe ürettik — tasarım farkı).
