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
 │               önce kurallar, emin değilse ham qwen2.5:7b
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
| `m02_hgnc.py` | Gen sembolü doğrulama (HGNC, 45.019 sembol; `genler.txt` ilk çalıştırmada indirilir) ve yazım önerisi. |
| `m03_vep.py` | Girdiyi Ensembl VEP ile anotasyon kartına çevirir (GRCh38, gerekirse GRCh37). |
| `m04_retrieval.py` | Sorgu kurucu + alaka kapısı: PubMed'i kademeli arar, kaynakları `varyant` / `gen` diye etiketler. |
| `m05_pubmed.py` | NCBI E-utilities (PubMed) istemcisi. |
| `m06_clinvar.py` | ClinVar kaydını bulur, kanonik kaydı seçer, sınıflandırmaları yıldızıyla gösterir. |
| `models/` | Yerel model dosyaları (repoda yalnız `Modelfile.varchat-v2`; GGUF ve adaptör repo dışı). |

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
| `sonuclar/` | Ölçüm girdileri: donmuş arama kaydı, doğru cevap listesi, hakem kararları (`hakem.jsonl`), özetler. |
| `sonuclar_colab/` | Colab üretim/sadakat sonuçları (5 model, 7B ve 32B yargıç); `v1_` önekliler ilk eğitimin ölçüm koşusuna ait. |

### Eğitim (`fine_tune/`)

| Dosya | Ne yapar |
|---|---|
Eğitim yalnız Qwen2.5-7B-Instruct'a yapıldı (14B eğitilmedi; ham hâli yalnız karşılaştırma için ölçüldü).

| Dosya | Ne yapar |
|---|---|
| `f01_collect_sources.py` | Yeni eğitim girdilerinin kaynaklarını uygulamanın kendi hattıyla toplar → `ara_veri/kaynaklar_v4.jsonl`. |
| `f02_build_dataset.py` | `ara_veri/` içindeki dört dosyadan **`egitim_verisi.jsonl`**'ı (501 örnek) üretir: v3'ün 204 örneğine denetim düzeltmelerini uygular, 297 yeni örneği ekler. |
| `f03_colab_train.ipynb` | QLoRA eğitimi (Qwen2.5-7B-Instruct, 4-bit, yalnız cevap tokenlarında kayıp, gen bazlı doğrulama). |
| `f04_colab_gguf.ipynb` | Yalnız model dosyası üretir: adaptör + taban → birleştir → GGUF → Q4_K_M. |
| `egitim_verisi.jsonl` | **Eğitim verisi** (438 eğitim / 63 doğrulama); `f03` bunu okur. |
| `ara_veri/` | `f02`'nin girdileri: `egitim_verisi_v3.jsonl` (v3'ün 204 örneği, değiştirilmemiş), `denetim_v3.json` (bu örneklerin denetim kararları), `kaynaklar_v4.jsonl`, `yeni_ornekler_v4.jsonl`. Silinirse eğitim verisi yeniden üretilemez. |
| `v4_kayit/` | Verinin nasıl üretildiğinin ham kayıtları (denetim ve yazım/doğrulama ajanlarının çıktıları, yönergeler); bkz. `v4_kayit/README.md`. |
| `egitim_ciktilari_v1/`, `egitim_ciktilari_v2/` | Eğitim kayıtları (kayıp geçmişi, sürümler, doğrulama varyantları). |

### Arşiv (`arsiv/`)

Kullanılmayan eski sürümler ve denemeler; içerik ve nedenleri `arsiv/README.md`'de.

---

## 3. Kurulum ve çalıştırma

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

[Ollama](https://ollama.com) kurulu olmalı. Yönlendirici ham modeli kullanır:

```bash
ollama pull qwen2.5:7b
```

Eğitilmiş model (`varchat-v2`): `f04_colab_gguf.ipynb`'nin ürettiği `varchat-v2-Q4_K_M.gguf` dosyasını `models/` klasörüne koy, sonra:

```bash
cd models
ollama create varchat-v2 -f Modelfile.varchat-v2
cd ..
python m01_main.py
```

`Modelfile.varchat-v2`, `ollama show qwen2.5:7b --modelfile` çıktısının yalnız `FROM` satırı değiştirilmiş hâlidir
(aynı sohbet şablonu). Linux satır sonuyla (LF) kalmalı; Windows satır sonu şablonu bozuyor.
Ham modelle çalıştırmak için `m01_main.py`'de `MODEL = "qwen2.5:7b"`.

İnternet PubMed, VEP ve ClinVar sorguları için gerekir. `.env` içinde NCBI anahtarı isteğe bağlıdır (bkz. `.env.example`).
GPU olmayan bilgisayarda bir özet birkaç dakika sürer.

---

## 4. Sonuçlar

### Arama (5 Ekim 2026, `evaluation/sonuclar/arama_ozet_2026-10-05.json`)

P@5 = seçilen ilk 5 makaleden doğru olanların oranı. Eski hat = Temmuz'daki kod (git `b87d8a8`), birebir.
"Hakemli" sütunu otomatik listeye 14 insan hakem kararını ekler (`evaluation/sonuclar/hakem.jsonl`).

| Katman | Girdi | Yeni hat, otomatik | Eski hat, otomatik | Yeni hat, hakemli | Eski hat, hakemli |
|---|---|---|---|---|---|
| A: kanser hotspot | 15 | 0.84 | 0.79 | 0.91 | 0.88 |
| B: eski adlı kalıtsal | 15 | 0.89 | 0.85 | 0.91 | 0.87 |
| C: rsID | 10 | 0.96 | 0.90 | 1.00 | 0.90 |
| C: koordinat (GRCh38/GRCh37) | 11 | 0.98 | 0.20 | 1.00 | 0.20 |
| A+B+C | 51 | 0.91 | 0.70 | 0.94 | 0.73 |

Literatürsüz 5 girdinin 5'inde sistem "gen düzeyi" moduna geçti.

### Üretim (Colab L4/A100, aynı 56 girdi, `evaluation/sonuclar_colab/`)

Sadakat = yargıcın "kaynakta destekleniyor" dediği iddiaların oranı (yalnız atıflı cümleler yargılanır). Üç yargıç:
qwen2.5:7b ve qwen2.5:32b (`e05`) ve bütün 1.434 iddiayı kör (model adı ve öbür kararlar gizli) yeniden değerlendiren
Claude Opus 5.5 (`e11_judge_check.py`; aynı tanımlar + iki netleştirme: kısmen destek ya da anlamı çözülemeyen Türkçe =
desteklenmiyor). Claude etiketleri insan etiketi değildir; varchat'in eğitim örneklerini de Claude yazdığı için yanlılık riski not edilir.

| Model | Sadakat 7B | Sadakat 32B | **Sadakat Claude** | Çelişki (Claude) | Atıfsız cümle | Desteklenen iddia (Claude) | Çıplak "bilgi yok" |
|---|---|---|---|---|---|---|---|
| ham qwen2.5:7b | 0.763 | 0.769 | 0.572 | %10,9 | %34 | 131 | 9 |
| qwen-taban (aynı ağırlıklar, bizim dönüştürme hattımız) | 0.806 | 0.848 | **0.637** | %7,2 | %33 | 142 | 10 |
| varchat v1 (204 örnek) | 0.649 | 0.711 | 0.356 | %12,6 | %7 | 116 | 0 |
| **varchat-v2 (501 denetlenmiş örnek)** | **0.828** | 0.810 | 0.605 | %14,0 | **%0,9** | **268** | 0 |
| ham qwen2.5:14b | – | 0.831 | 0.526 | %9,4 | %42 | 112 | 0 |

**Yargıçların doğruluğu (Claude kararına göre, aynı iddialar):** 7B %61,5 aynı karar (kappa 0.25), 32B %64,8 (kappa 0.31).
İki küçük yargıç da hoşgörülü: Claude'un desteksiz bulduğu bozuk ya da yanlış cümlelerin önemli kısmına "destekleniyor" demişler;
mutlak sadakat değerleri bu yüzden 7B/32B sütunlarında şişkin. Sıralama ve aşağıdaki sonuçlar üç yargıçta da aynı yönde.

Eşleştirilmiş karşılaştırma (`e06`, %95 bootstrap güven aralığı):

- varchat v1 → v2: +0.18 (7B, GA +0.12…+0.23), +0.10 (32B, GA +0.03…+0.17), **+0.25 (Claude, GA +0.18…+0.32)**: veri denetimi
  ve büyütme ilk eğitimdeki düşüşü giderdi (üç yargıçta da anlamlı).
- qwen-taban → v2: +0.02 / −0.04 / −0.03 (Claude, GA −0.12…+0.06): iddia başına sadakatte fark yok; v2 yaklaşık iki kat
  desteklenen iddia üretiyor (268 / 142), neredeyse her cümleye atıf veriyor ve girdiyi "bilgi yok" diye geçiştirmiyor.
  Atıfsız cümleler de desteksiz sayılırsa (Claude): v2 0.60, qwen-taban 0.42, ham 14B 0.31.
- v2 → ham 14B: +0.02 (32B), −0.08 (Claude, GA −0.17…+0.02): fark yok; 14B'nin 56 cevabından 7'si Çince/Arapçaya kayıyor.
- 7B ile 32B yargıcın birbirine uyumu orta (kappa 0.42–0.56).

**Bilinen sorunlar (varchat-v2):** iddiaların %14'ü kaynakla çelişiyor (Claude; modeller arasında en yüksek oran): rakam ve
özne karışması, ters yön, yanlış alel ya da hastalık. Daha uzun ve ayrıntılı yazdıkça hata fırsatı artıyor. Gen düzeyi bir girdide
(chr1:17001759:A>T) varyanta kaynakta olmayan bir hastalık ilişkisi yüklendi. Türkçe terimlerde bozulmalar var.
Kararların tamamı: `sonuclar_colab/yargic_kontrol.jsonl` (her iddia için 7B, 32B ve Claude kararı + Claude gerekçesi);
özet: `yargic_kontrol_ozet.json`.

### Eğitim

QLoRA, Qwen2.5-7B-Instruct, 3 epoch, en düşük doğrulama kaybındaki epoch saklanır.
v2: 501 örnek (438 eğitim / 63 doğrulama, 14 doğrulama geni), A100'de 26 dk; doğrulama kaybı 0.717 → **0.684** → 0.708 (epoch 2 saklandı).
Eğitim verisinin denetimi ve üretimi: `fine_tune/v4_kayit/README.md`.

---

## 5. Sıradaki işler

1. Gen düzeyi kaynaklarda varyant adını anıp "bilgi yok" demeyen cümleleri silen kod denetimi.
2. Çelişen iddiaları azaltmak (rakam/yön hataları): eğitim verisinde ya da üretim sonrası denetimde.
3. Sistem yıldız alel adlarını (TPMT\*3A) ve eski numaralamayı (EZH2 Y641N = Y646N) bilmiyor; bu girdilerde P@5 düşük.
4. Arama: gen kısaltması çakışması (APC = aktive protein C) bir girdide konu dışı kaynak getirdi.
5. İsteğe bağlı: aynı veriyle 14B eğitimi.
6. Tez yazımı.

Araştırma sorusu danışmanla birlikte netleştirilecek.

---

## 6. Kaynaklar

- VarChat makalesi: De Paoli ve ark., Bioinformatics 40(4), 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11055464/
- Ensembl VEP REST — https://rest.ensembl.org (GRCh37 için grch37.rest.ensembl.org)
- NCBI E-utilities (PubMed, ClinVar) — https://www.ncbi.nlm.nih.gov/books/NBK25497/
- LitVar2 — https://www.ncbi.nlm.nih.gov/research/litvar2-api/ · PubTator3 — https://www.ncbi.nlm.nih.gov/research/pubtator3/
- ACMG/AMP 2015 sınıflandırma kılavuzu — https://pubmed.ncbi.nlm.nih.gov/25741868/
- LoRA (Hu ve ark. 2022) — https://arxiv.org/abs/2106.09685 · QLoRA (Dettmers ve ark. 2023) — https://arxiv.org/abs/2305.14314
