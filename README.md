# VarChat Benzeri Genetik Varyant Chatbotu

Yüksek lisans tez projesi (Kayseri Üniversitesi, Bilgisayar Mühendisliği).

Bir genetik varyant girildiğinde (örn. `BRAF V600E`, `rs334` ya da `chr7:140753336:A>T`)
o varyantla ilgili bilimsel makaleleri bulan, **yalnızca bu makalelere dayanarak**
Türkçe ve **kaynak gösteren** bir özet üreten, sonra aynı kaynaklar üzerinde
takip sorularına cevap veren bir chatbot.

Referans araç: [VarChat](https://varchat.engenome.com) (enGenome, Bioinformatics 2024,
[makale](https://pmc.ncbi.nlm.nih.gov/articles/PMC11055464/)).
Bu projede: genom koordinatı girişi, Türkçe çıktı, açık ağırlıklı bir model (Qwen2.5) ve tekrar üretilebilir ölçüm.

---

## 1. Nasıl çalışıyor?

```
Mesaj
 │
 ▼
[Yönlendirici]  selamlama / kendini tanıt / konu dışı / varyant / takip / belirsiz
 │               önce kurallar, emin değilse model (varchat-v2)
 ▼ (varyant)
[Gen doğrulama] gen sembolü HGNC listesinde var mı? "BRFA" → "BRAF mı demek istediniz?"
 ▼
[Anlamlandırma] koordinat, HGVS ya da rsID → VEP "anotasyon kartı": gen, protein değişimi,
 │              rsID, gnomAD sıklığı, CADD (çok alelli rsID'de ClinVar'da önemi olan alel seçilir)
 ▼
[Bulucu]        PubMed'de kademeli arama: varyanta özgü sorgu → VEP'in kürasyonlu PMID'leri
 │              → gen düzeyi; her kaynak "varyant" / "gen düzeyi" diye etiketlenir
 ▼
[Üretim]        özetler + kurallar tek bir system mesajına yazılır:
 │              "yalnızca bu kaynakları kullan, her cümleye [n] yaz, Türkçe konuş, yoksa 'bilgi yok' de"
 │              model: varchat-v2 (Qwen2.5-7B-Instruct + LoRA, Ollama)
 ▼
[Denetim]       kod denetler: geçersiz atıf silinir, atıfsız cümle sayılır, yabancı alfabeye kayışta yeniden
 │              üretilir, özet ClinVar sınıfıyla ters yöndeyse uyarı basılır
 ▼
[Çıktı]         özet + kaynak listesi (PMID bağlantılı, kod basar) + ClinVar klinik önem satırı
 ▼
[Takip]         sonraki sorular aynı kaynak bloğu üzerinde, sohbet geçmişiyle sorulur
```

Bilgi VEP, PubMed ve ClinVar'dan gelir; model yalnızca verilen kaynakları özetler.
Kaynak listesini model değil kod bastığı için makale uydurulamaz (cümle düzeyindeki hatalar için bkz. bölüm 4).

---

## 2. Dosyalar

### Ana program (kök klasör)

| Dosya | Ne yapar |
|---|---|
| `m01_main.py` | **Uygulama.** Sohbet döngüsü, yönlendirici, üretim, üretim sonrası denetimler. Diğer modülleri çağırır. |
| `m02_hgnc.py` | Gen sembolü doğrulama (HGNC, 45.018 sembol; `genler.txt` ilk çalıştırmada indirilir) ve yazım önerisi. |
| `m03_vep.py` | Girdiyi Ensembl VEP ile anotasyon kartına çevirir (GRCh38, gerekirse GRCh37). |
| `m04_retrieval.py` | Sorgu kurucu + alaka kapısı: PubMed'i kademeli arar, kaynakları `varyant` / `gen` diye etiketler. |
| `m05_pubmed.py` | NCBI E-utilities (PubMed) istemcisi. |
| `m06_clinvar.py` | ClinVar kaydını bulur, kanonik kaydı seçer, sınıflandırmaları yıldızıyla gösterir. |
| `models/` | Yerel model dosyaları: `Modelfile.varchat-v2` (Ollama ayarı, repoda), `varchat-v2-Q4_K_M.gguf` (model, 4,7 GB) ve `varchat-lora-v2/` (eğitilmiş adaptör, 155 MB; model dosyasını yeniden üretmek için). Son ikisi repo dışı. |

### Değerlendirme (`evaluation/`)

| Dosya | Ne yapar |
|---|---|
| `e01_test_set.py` | 45 girdi + 11 türetilmiş koordinat = 56; 4 katman (kanser hotspot, eski adlı kalıtsal, rsID/koordinat, literatürsüz); eğitim genleriyle kesişimsiz. |
| `e02_ground_truth.py` | Her girdi için "bu varyantı anan makaleler" listesi (LitVar2 + PubTator3). |
| `e03_retrieval_eval.py` | Aramayı dondurur ve P@5'i ölçer; hakem kararlarını çevrimdışı uygular (`--hakem`). Eski hatla (v1) karşılaştırma donmuş kayıtta; eski hattın kodu git geçmişinde. |
| `e04_generate.py` | Donmuş kaynaklarla bir modelden 56 özet üretir (kaldığı yerden devam eder). |
| `e05_faithfulness.py` | Yargıç model her atıflı cümleyi kaynağına karşı yargılar (destekleniyor / desteklenmiyor / çelişiyor). |
| `e06_compare.py` | Modelleri girdi girdi eşleştirir: sadakat farkı + bootstrap güven aralığı, işaret testi, McNemar, yargıç uyumu (kappa). |
| `e07_colab_measure.ipynb` | Colab'da: LoRA'yı birleştirip model dosyası üretir, modelleri aynı ortamda `e04` + `e05` ile ölçer. |
| `e08_colab_judge.ipynb` | Colab'da: ham qwen2.5:14b ile üretim + bütün modelleri qwen2.5:32b yargıçla puanlama + `e06`. |
| `e09_router_eval.py` | Yönlendirici doğruluğu (39 mesaj). |
| `e10_check_tests.py` | Üretim sonrası denetimlerin model çağırmadan çalışan testleri. |
| `e11_judge_check.py` | Yargıç kontrolü: bütün iddiaları kör paketlere böler, daha güçlü üçüncü yargıcın (Claude) kararlarını toplar, 7B/32B yargıcın doğruluğunu ve üçüncü yargıçla model sadakatini hesaplar. |
| `results/` | Bütün ölçüm dosyaları. Girdiler: donmuş arama kaydı (`arama_*`), doğru cevap listesi, hakem kararları (`hakem.jsonl`). Çıktılar: modellerin cevapları (`uretim_*`), yargıç kararları (`sadakat_*`; `__yargic-qwen2.5-32b` ekli olanlar 32B yargıç), karşılaştırmalar (`karsilastirma_*`), üçüncü yargıç kontrolü (`yargic_kontrol*`), yönlendirici testleri (`router_<model>_*`), ortam kayıtları; `v1_` önekliler ilk eğitimin ölçüm koşusuna ait. |

### Eğitim (`fine_tune/`)

Eğitim yalnız Qwen2.5-7B-Instruct'a yapıldı (14B eğitilmedi; ham hâli yalnız karşılaştırma için ölçüldü).

| Dosya | Ne yapar |
|---|---|
| `egitim_verisi.jsonl` | **Eğitim verisi: 501 örnek** (438 eğitim / 63 doğrulama, gen bazlı ayrım); `f01` bunu okur. |
| `f01_colab_train.ipynb` | Colab'da QLoRA eğitimi (Qwen2.5-7B-Instruct, 4-bit, yalnız cevap tokenlarında kayıp); adaptörü Drive'a yazar. |
| `f02_colab_gguf.ipynb` | Adaptör + taban → birleştir → GGUF → Q4_K_M: Ollama'nın çalıştırdığı tek model dosyası. |
| `results/v1/`, `results/v2/` | Eğitim kayıtları (kayıp geçmişi, kütüphane sürümleri, doğrulama varyantları; v2'de adaptör ayarları ve en iyi epoch). |

Verinin nasıl üretildiği (204 eski örneğin denetimi, 297 yeni örnek, üretim betikleri ve girdileri) arşivde:
`archive/dataset_build_v4/` (betikler orada da çalışır ve aynı 501 örneği yeniden üretir).

### Arşiv (`archive/`)

Kullanılmayan eski sürümler ve denemeler; içerik ve nedenleri `archive/README.md`'de.

---

## 3. Kurulum ve çalıştırma

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

[Ollama](https://ollama.com) kurulu olmalı. Uygulama tek model kullanır: `varchat-v2` (cevap üretimi ve yönlendirici;
yönlendirici testinde 39/39). `f02_colab_gguf.ipynb`'nin ürettiği `varchat-v2-Q4_K_M.gguf` dosyasını `models/` klasörüne koy, sonra:

```bash
cd models
ollama create varchat-v2 -f Modelfile.varchat-v2
cd ..
python m01_main.py
```

`Modelfile.varchat-v2`, `ollama show qwen2.5:7b --modelfile` çıktısının yalnız `FROM` satırı değiştirilmiş hâlidir
(aynı sohbet şablonu). Linux satır sonuyla (LF) kalmalı; Windows satır sonu şablonu bozuyor.
Ham modelle çalıştırmak için `ollama pull qwen2.5:7b` ve `m01_main.py`'de `MODEL = "qwen2.5:7b"`.

İnternet PubMed, VEP ve ClinVar sorguları için gerekir. `.env` içinde NCBI anahtarı isteğe bağlıdır (bkz. `.env.example`).
GPU olmayan bilgisayarda bir özet birkaç dakika sürer.

---

## 4. Sonuçlar

### Arama (`evaluation/results/arama_ozet_2026-10-05.json`)

P@5 = sistemin seçtiği ilk 5 makaleden kaçının gerçekten o varyantı anlattığı. "Otomatik": LitVar2, PubTator3 ve ClinVar
kürasyon listesine göre; "hakemli": bu listenin kaçırdığı makaleler için 14 insan hakem kararı eklenmiş hâli
(`evaluation/results/hakem.jsonl`).

| Katman | Girdi | P@5 otomatik | P@5 hakemli |
|---|---|---|---|
| A: kanser hotspot | 15 | 0.84 | 0.91 |
| B: eski adlı kalıtsal | 15 | 0.89 | 0.91 |
| C: rsID | 10 | 0.96 | 1.00 |
| C: koordinat (GRCh38/GRCh37) | 11 | 0.98 | 1.00 |
| **A+B+C** | 51 | **0.91** | **0.94** |

D katmanı (literatürü olmayan 5 varyant): 5'inde de sistem "gen düzeyi" moduna geçti; varyanta özgü kaynak varmış gibi davranmadı.

### Cevap kalitesi (`evaluation/results/`)

**Nasıl ölçüldü:** 56 test girdisinin her biri için model, dondurulmuş aynı 5 makaleyle özet yazar (`e04`). Özetteki her atıflı
cümle, gösterdiği makalenin başlık ve özetine karşı yargılanır: destekleniyor / desteklenmiyor / çelişiyor. Yargıç Claude Opus 5.5;
değerlendirme kördür, cümlenin hangi modelden geldiği gizlidir (`e11_judge_check.py`). Otomatik Qwen yargıçlar (7B ve 32B) aynı
cümlelerde Claude ile ancak %62-65 oranında aynı kararı verdi (kappa 0.25-0.31) ve bozuk ya da yanlış cümleleri çoğu zaman
"destekleniyor" saydı; ana ölçü bu yüzden Claude. Claude etiketleri insan etiketi değildir; eğitim örneklerini de Claude yazdığı
için yanlılık riski vardır.

| Model | Sadakat | Çelişen iddia | Atıfsız cümle | Desteklenen iddia | "Bilgi yok" diye geçiştirme | Dil çöküşü |
|---|---|---|---|---|---|---|
| **varchat-v2** (kullanılan) | 0.605 | %14,0 | %0,9 | **268** | 0 | 0 |
| Eğitimsiz Qwen2.5-7B | 0.637 | %7,2 | %33 | 142 | 10 | 0 |
| Ham Qwen2.5-14B | 0.526 | %9,4 | %42 | 112 | 0 | 6 |

Sadakat = desteklenen / yargılanan atıflı iddia; değerler 56 girdinin toplamı. Dil çöküşü = cevabın %2'sinden fazlası yabancı
alfabe (Çince/Arapça).

**Çıkarımlar** (eşleştirilmiş karşılaştırma, `e06`, %95 bootstrap güven aralığı):

- **Eğitim cümle başına doğruluğu değiştirmedi:** varchat-v2 − eğitimsiz 7B = −0.03 (GA −0.12…+0.06). Kazandırdığı: cevap
  başına yaklaşık iki kat desteklenen bilgi (268'e 142), neredeyse her cümlede atıf (atıfsız cümle %0,9'a %33) ve hiçbir girdiyi
  "bilgi yok" diye geçiştirmeme (0'a 10). Atıfsız cümleler de desteksiz sayılırsa: varchat-v2 0.60, eğitimsiz 7B 0.42.
- **Ham 14B daha iyi değil:** 14B − varchat-v2 = −0.08 (GA −0.17…+0.02); cümlelerinin %42'si atıfsız, 6 cevabı yabancı alfabeye
  kayıyor. İki kat donanım isteyen 14B yerine eğitilmiş 7B kullanılıyor.
- **Bedeli:** varchat-v2 daha uzun ve ayrıntılı yazıyor; çelişen iddia oranı en yüksek onda (%14).

**Bilinen sorunlar (varchat-v2):** çelişen iddialar rakam ve özne karışması, ters yön, yanlış alel ya da hastalık şeklinde.
Gen düzeyi bir girdide (chr1:17001759:A>T) varyanta kaynakta olmayan bir hastalık ilişkisi yüklendi. Türkçe terimlerde bozulmalar
var. Kararların tamamı `evaluation/results/yargic_kontrol.jsonl` (her iddia için Claude kararı ve gerekçesi), özet
`yargic_kontrol_ozet.json`.

### Eğitim (`fine_tune/results/v2/`)

Qwen2.5-7B-Instruct, QLoRA (taban 4-bit, adaptör r=16, kayıp yalnız cevap tokenlarında). 501 örnek: 438 eğitim, 63 doğrulama;
doğrulamadaki 14 gen eğitimde yok. 3 tur, Colab A100'de 26 dakika. Doğrulama kaybı turlara göre 0.717 → **0.684** → 0.708;
en düşük kayıplı 2. tur saklandı (3. turda ezber başlıyor).

---

## 5. Bilinen eksikler ve sonraki adımlar

### Bilinen eksikler

- **Gen düzeyi modda varyant iddiası:** Varyanta özgü kaynak yoksa model yalnız gen hakkında yazmalı. Bir test girdisinde
  (chr1:17001759:A>T) yine de varyanta kaynakta olmayan bir hastalık ilişkisi yükledi; bunu yakalayan bir üretim sonrası kod
  denetimi yok.
- **Çelişen iddialar:** varchat-v2'nin atıflı iddialarının %14'ü kaynağıyla çelişiyor (yanlış rakam, ters yön, yanlış alel ya da
  hastalık). Üretim sonrası denetim yalnız ClinVar sınıfıyla yön çelişkisini yakalıyor; cümledeki rakam ve yön kaynak metniyle
  karşılaştırılmıyor.
- **Yıldız alel adları ve eski numaralama:** Sistem farmakogenetik yıldız alel adlarını (TPMT\*3A) ve bazı genlerin eski
  numaralamasını (EZH2 Y641N = Y646N) tanımıyor; bu girdilerde P@5 düşük.
- **Gen kısaltması çakışması:** Kısaltması başka bir terimle çakışan genlerde (APC = aktive protein C) arama konu dışı kaynak
  getirebiliyor; çakışma filtresi bu kısaltmayı içermiyor.

### Sonraki adımlar

- **Daha büyük modeller:** Yüksek bellekli GPU'da aynı 501 örnekle Qwen2.5-14B ve Qwen2.5-32B'yi eğitip aynı test seti ve
  yargıçla ölçmek. Şu an 14B yalnız eğitimsiz hâliyle ölçüldü, 32B ise yalnız yargıç olarak kullanıldı. 14B eğitimi A100 40 GB'a
  sığar; 32B eğitimi için 80 GB sınıfı GPU gerekeceği tahmin ediliyor.
- **Tez yazımı.** Araştırma sorusu danışmanla birlikte netleştirilecek.

---

## 6. Kaynaklar

- VarChat makalesi: De Paoli ve ark., Bioinformatics 40(4), 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11055464/
- Ensembl VEP REST — https://rest.ensembl.org (GRCh37 için grch37.rest.ensembl.org)
- NCBI E-utilities (PubMed, ClinVar) — https://www.ncbi.nlm.nih.gov/books/NBK25497/
- LitVar2 — https://www.ncbi.nlm.nih.gov/research/litvar2-api/ · PubTator3 — https://www.ncbi.nlm.nih.gov/research/pubtator3/
- ACMG/AMP 2015 sınıflandırma kılavuzu — https://pubmed.ncbi.nlm.nih.gov/25741868/
- LoRA (Hu ve ark. 2022) — https://arxiv.org/abs/2106.09685 · QLoRA (Dettmers ve ark. 2023) — https://arxiv.org/abs/2305.14314
