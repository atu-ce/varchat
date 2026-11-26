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
[Bulucu]        PubMed'de kademeli arama: varyanta özgü sorgu → VEP'in varyanta bağladığı yayınlar
 │              → gen düzeyi; her kaynak "varyant" / "gen düzeyi" diye etiketlenir
 ▼
[Üretim]        özetler + kurallar tek bir system mesajına yazılır:
 │              "yalnızca bu kaynakları kullan, her cümleye [n] yaz, Türkçe konuş, yoksa 'bilgi yok' de"
 │              model: varchat-v2 (Qwen2.5-7B-Instruct + LoRA, Ollama); isteğe bağlı varchat-14b (--model)
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
| `m01_main.py` | **Uygulama.** Sohbet döngüsü, yönlendirici, üretim, üretim sonrası denetimler. Diğer modülleri çağırır. `--model <ad>` ile başka bir Ollama modeli seçilir (varsayılan `varchat-v2`). |
| `m02_hgnc.py` | Gen sembolü doğrulama (HGNC, 45.018 sembol; `genler.txt` ilk çalıştırmada indirilir) ve yazım önerisi. |
| `m03_vep.py` | Girdiyi Ensembl VEP ile anotasyon kartına çevirir (GRCh38, gerekirse GRCh37). |
| `m04_retrieval.py` | Sorgu kurucu + alaka kapısı: PubMed'i kademeli arar, kaynakları `varyant` / `gen` diye etiketler. |
| `m05_pubmed.py` | NCBI E-utilities (PubMed) istemcisi. |
| `m06_clinvar.py` | ClinVar kaydını bulur, kanonik kaydı seçer, sınıflandırmaları yıldızıyla gösterir. |
| `models/` | Yerel model dosyaları. Repoda yalnız Ollama ayarları: `Modelfile.varchat-v2`, `Modelfile.varchat-14b`. Repo dışı: `varchat-v2-Q4_K_M.gguf` (4,7 GB), `varchat-14b-Q4_K_M.gguf` (9,0 GB) ve eğitilmiş adaptörler `varchat-lora-v2/` (155 MB), `varchat-lora-14b/` (275 MB; model dosyasını yeniden üretmek için). Adaptör ve model dosyalarının parmak izleri (sha256) `fine_tune/results/` ve `evaluation/results/gguf_ortam_*` kayıtlarında. |

### Değerlendirme (`evaluation/`)

| Dosya | Ne yapar |
|---|---|
| `e01_test_set.py` | 45 girdi + 11 türetilmiş koordinat = 56; 4 katman (kanser hotspot, eski adlı kalıtsal, rsID/koordinat, literatürsüz); 37 test geninin hiçbiri 105 eğitim geninde yok. 56 girdi 40 farklı varyanttır: 8 varyant birkaç yazımla (ad, rsID, koordinat) ayrı ayrı sorulur (`AYNI_VARYANT`). |
| `e02_ground_truth.py` | Her girdi için "bu varyantı anan makaleler" listesi (LitVar2 + PubTator3). |
| `e03_retrieval_eval.py` | Aramayı dondurur ve P@5'i ölçer; hakem kararlarını çevrimdışı uygular (`--hakem`). Eski hatla (v1) karşılaştırma donmuş kayıtta; eski hattın kodu git geçmişinde. |
| `e04_generate.py` | Donmuş kaynaklarla bir modelden 56 özet üretir (kaldığı yerden devam eder). |
| `e05_faithfulness.py` | Yargıç model her atıflı cümleyi kaynağına karşı yargılar (destekleniyor / desteklenmiyor / çelişiyor). |
| `e06_compare.py` | Modelleri girdi girdi eşleştirir: sadakat, çelişki ve atıfsız cümle farkı + bootstrap güven aralığı (girdi bazlı ve varyant bazlı), işaret testi, McNemar, yargıç uyumu (kappa). |
| `e07_colab_measure.ipynb` | Colab'da: LoRA'yı birleştirip model dosyası üretir, modelleri aynı ortamda `e04` + `e05` ile ölçer. |
| `e08_colab_judge.ipynb` | Colab'da: ham qwen2.5:14b ile üretim + bütün modelleri qwen2.5:32b yargıçla puanlama + `e06`. |
| `e09_router_eval.py` | Yönlendirici doğruluğu. 39 mesajlık geliştirme seti (kurallar buna bakılarak ayarlandı; regresyon testi) ve kodu görmemiş bir yazarın yazdığı 80'er mesajlık iki ayrı set (`e09_router_heldout.json`, `e09_router_heldout2.json`). |
| `e10_check_tests.py` | Model çağırmadan çalışan 123 kontrol: üretim sonrası denetimler, yönlendirici kuralları, takma adlar, VEP yayın listesi, atıf duyarlılığı hesabı. |
| `e11_judge_check.py` | Yargıç kontrolü: bütün iddiaları kör paketlere böler, daha güçlü üçüncü yargıcın (Claude) kararlarını toplar, 7B/32B yargıcın doğruluğunu ve üçüncü yargıçla model sadakatini hesaplar. |
| `e12_colab_14b.ipynb` | Colab'da 14B için: taban modelden `qwen14-taban`, eğitilmiş adaptörle birleştirip `varchat-14b` model dosyalarını üretir (llama.cpp ve Ollama sürümleri 7B ile aynı) ve ikisiyle `e04` çalıştırır. |
| `e13_judge_14b.py` | 2x2 ölçümü (7B / 14B x eğitimsiz / eğitimli): `e11` yöntemiyle kör yargıç paketleri, yargıç tutarlılık kontrolü (çapa), 2x2 tablosu, etkileşim ve atıf duyarlılığı (bölüm 4). |
| `results/` | Bütün ölçüm dosyaları. Girdiler: donmuş arama kaydı (`arama_*`), doğru cevap listesi, hakem kararları (`hakem.jsonl`). Çıktılar: modellerin cevapları (`uretim_*`), yargıç kararları (`sadakat_*`; `__yargic-qwen2.5-32b` ekli olanlar 32B yargıç), karşılaştırmalar (`karsilastirma_*`), üçüncü yargıç kararları (`yargic_kontrol*`; 2x2 ölçümü `yargic_kontrol_2x2.jsonl` ve `yargic_kontrol_ozet_2x2.json`), yönlendirici testleri (`router_<model>_*`), ortam kayıtları (`ortam_*`, `gguf_ortam_*`); `v1_` önekliler ilk eğitimin ölçüm koşusuna ait. |

### Eğitim (`fine_tune/`)

Aynı 501 örnek ve aynı tarifle iki model eğitildi: Qwen2.5-7B-Instruct (`f01`) ve Qwen2.5-14B-Instruct (`f03`; yalnız taban model farklı).

| Dosya | Ne yapar |
|---|---|
| `egitim_verisi.jsonl` | **Eğitim verisi: 501 örnek** (438 eğitim / 63 doğrulama, gen bazlı ayrım); `f01` ve `f03` bunu okur. |
| `f01_colab_train.ipynb` | Colab'da QLoRA eğitimi (Qwen2.5-7B-Instruct, 4-bit, yalnız cevap tokenlarında kayıp); adaptörü Drive'a yazar. |
| `f02_colab_gguf.ipynb` | 7B: adaptör + taban → birleştir → GGUF → Q4_K_M: Ollama'nın çalıştırdığı model dosyası (14B için `evaluation/e12_colab_14b.ipynb`). |
| `f03_colab_train_14b.ipynb` | Aynı eğitim, Qwen2.5-14B-Instruct ile; tur sayısı ve tohum ayar olarak yazılı (3, 42), veri parmak izi denetlenir. |
| `results/v1/`, `results/v2/`, `results/v2-14b/` | Eğitim kayıtları (kayıp geçmişi, kütüphane sürümleri, doğrulama varyantları, adaptör ayarları ve en iyi epoch; v2-14b'de ayrıca GPU ve adaptör dosyalarının parmak izleri). |

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
yönlendirici doğruluğu için bkz. bölüm 4). `f02_colab_gguf.ipynb`'nin ürettiği `varchat-v2-Q4_K_M.gguf` dosyasını `models/` klasörüne koy, sonra:

```bash
cd models
ollama create varchat-v2 -f Modelfile.varchat-v2
cd ..
python m01_main.py
```

`Modelfile.varchat-v2`, `ollama show qwen2.5:7b --modelfile` çıktısının yalnız `FROM` satırı değiştirilmiş hâlidir
(aynı sohbet şablonu). Linux satır sonuyla (LF) kalmalı; Windows satır sonu şablonu bozuyor.

14B ile çalıştırmak için `e12_colab_14b.ipynb`'nin ürettiği `varchat-14b-Q4_K_M.gguf` dosyasını `models/` klasörüne koy,
`ollama create varchat-14b -f Modelfile.varchat-14b` ve `python m01_main.py --model varchat-14b`. Ham modelle: `ollama pull qwen2.5:7b`
ve `python m01_main.py --model qwen2.5:7b`. Yönlendiricinin doğruluğu yalnız `varchat-v2` ile ölçüldü.

İnternet PubMed, VEP ve ClinVar sorguları için gerekir. `.env` içinde NCBI anahtarı ve NCBI'ye gönderilen iletişim e-postası isteğe bağlıdır (bkz. `.env.example`).
GPU olmayan bilgisayarda bir özet birkaç dakika sürer.

---

## 4. Sonuçlar

### Arama (`evaluation/results/arama_ozet_2026-10-05.json`)

P@5 = sistemin seçtiği ilk 5 makaleden kaçının o varyantı andığı. "Otomatik": LitVar2, PubTator3 ve VEP'in varyanta bağladığı
yayın listesine göre (isabetlerin 206'sı LitVar2, 26'sı PubTator3, 0'ı VEP listesinden); "hakemli": bu listenin kaçırdığı 14 makale için araştırmacının kararı eklenmiş hâli
(`evaluation/results/hakem.jsonl`; adayları sistem işaretledi, bağımsız ikinci hakem yok). Ölçülen şey makalenin varyantı **anması**dır;
makalenin soruya ne kadar yararlı olduğu ölçülmez.

| Katman | Girdi | P@5 otomatik | P@5 hakemli |
|---|---|---|---|
| A: kanser hotspot | 15 | 0.84 | 0.91 |
| B: eski adlı kalıtsal | 15 | 0.89 | 0.91 |
| C: rsID | 10 | 0.96 | 1.00 |
| C: koordinat (GRCh38/GRCh37) | 11 | 0.98 | 1.00 |
| **A+B+C** | 51 | **0.91** | **0.95** |

D katmanı (varyanta özgü yayını olmayan 5 girdi = 3 farklı varyant): 5'inde de sistem "gen düzeyi" moduna geçti; varyanta özgü kaynak varmış gibi davranmadı.

### Cevap kalitesi: 2x2 ölçüm (`evaluation/results/yargic_kontrol_ozet_2x2.json`)

**Tasarım:** iki boyut (7B, 14B) x ince ayar (eğitimsiz, eğitilmiş). Dört model de aynı hattan geçer: aynı sistem mesajı, aynı
ayarlar, aynı dondurulmuş 5 makale (`e04`); eğitimsiz modeller de bizim dönüştürme hattımızla üretildi (`qwen-taban`, `qwen14-taban`).
Ollama'nın hazır `qwen2.5:7b` / `qwen2.5:14b` dosyaları yalnız yan kontrol.

**Nasıl ölçüldü:** Her cevaptaki her atıflı cümle, gösterdiği makalelerin başlık ve özetine karşı yargılanır: destekleniyor /
desteklenmiyor / çelişiyor. Yargıç Claude Opus 5.5; değerlendirme kördür, cümlenin hangi modelden geldiği gizlidir (`e13`, `e11`
yöntemi). Yargıç tutarlılığı: daha önce etiketlenmiş 199 iddia paketlere kör karıştırıldı; aynı karar %88,4, kappa 0.787. Önceden
belirlenen 0.80 eşiğinin altında kaldığı için bütün modellerin iddiaları aynı turda, aynı yargıçla etiketlendi. Yargıcın güvenlik
filtresi 12 girdide etiketlemeyi durdurdu; bu girdiler bütün modellerden çıkarıldı: ölçüm **44 girdi = 32 farklı varyant** üzerinde.
Otomatik Qwen yargıçlar (7B ve 32B) aynı cümlelerde Claude ile ancak %61,5-64,8 oranında aynı kararı verdiği için (kappa
0.245-0.309) ana yargıç Claude. Claude etiketleri insan etiketi değildir; eğitim örneklerini de Claude yazdığı için yanlılık riski vardır.

**Ölçüler:**
- **Atıf duyarlılığı** (ALCE'deki *citation recall*; Gao ve ark. 2023, Liu ve ark. 2023): her cevapta gösterdiği kaynaklarca
  desteklenen cümle / bütün cümleler (atıfsız cümle desteklenmemiş sayılır), sonra cevapların ortalaması. Yalnız "bilgi yok" diyen
  ya da üretilemeyen cevap ortalamaya girmez, ayrıca sayılır.
- **Kaynak göstermeyen cümle:** atıfsız cümle / bütün cümleler. **Çelişen cümle:** kaynağıyla çelişen / yargılanan atıflı cümle.
- **Desteklenen / atıflı cümle:** yalnız kaynak gösteren cümleler içinde desteklenenlerin payı (atıf duyarlılığının ikinci çarpanı).

| Model | Atıf duyarlılığı (%95 GA) | Kaynak göstermeyen cümle | Çelişen cümle | Desteklenen / atıflı cümle | "Bilgi yok" cevabı | Üretim hatası | Dil çöküşü |
|---|---|---|---|---|---|---|---|
| Eğitimsiz 7B (`qwen-taban`) | 0.420 (0.32–0.52) | %33,5 | %6,9 | 0.608 | 5 | 0 | 0 |
| **Eğitilmiş 7B (`varchat-v2`, uygulama)** | 0.579 (0.52–0.64) | %1,1 | %13,5 | 0.586 | 0 | 0 | 0 |
| Eğitimsiz 14B (`qwen14-taban`) | 0.366 (0.30–0.43) | %36,8 | %4,9 | 0.577 | 0 | 1 | 4 |
| **Eğitilmiş 14B (`varchat-14b`)** | 0.705 (0.64–0.76) | %0,0 | %7,8 | 0.723 | 0 | 0 | 0 |
| Yan kontrol: Ollama'nın hazır `qwen2.5:7b` dosyası | 0.353 (0.30–0.41) | %33,0 | %9,6 | 0.508 | 4 | 0 | 0 |
| Yan kontrol: Ollama'nın hazır `qwen2.5:14b` dosyası | 0.326 (0.26–0.39) | %42,0 | %9,6 | 0.565 | 0 | 0 | 4 |

Üretim hatası = model tekrar döngüsüne girdi, cevap yok (MAP2K1 K57N). Dil çöküşü = cevaptaki harflerin %2'sinden fazlası Çince,
Japonca ya da Korece.

**Çıkarımlar** (eşleştirilmiş karşılaştırma, %95 bootstrap güven aralığı; aynı varyantın farklı yazımları bağımsız olmadığı için
varyant kümeleri yeniden örneklenir):

- **İnce ayar atıf duyarlılığını iki boyutta da artırdı:** 7B +0.159 (GA +0.045…+0.271), 14B +0.339 (GA +0.258…+0.425). Etki 14B'de
  daha büyük: etkileşim +0.180 (GA +0.047…+0.314). Eğitimsiz modellerde boyutun etkisi anlamlı değil (−0.054, GA −0.166…+0.054).
- **7B'de artış yalnız daha çok kaynak göstermekten geliyor:** kaynak göstermeyen cümle −0.323 (GA −0.403…−0.241), ama kaynak
  gösteren cümlelerin desteklenme payı değişmedi (−0.023, GA −0.117…+0.085) ve çelişen cümle arttı (+0.066, GA +0.017…+0.125).
- **14B'de ince ayar doğruluğu da artırdı:** desteklenen / atıflı cümle +0.146 (GA +0.063…+0.227); çelişen cümledeki değişim
  anlamlı değil (+0.029, GA −0.019…+0.070).
- **Hazır dosya ile kendi dosyamız arasında** atıf duyarlılığında anlamlı fark yok (7B +0.067, 14B +0.040; ikisinin aralığı da
  sıfırı içeriyor).
- Duyarlılık analizi (her modelde cevabı olan 43 girdi) aynı sonucu veriyor (etkileşim +0.181, GA +0.047…+0.323).

**Sınırlılıklar:** çıkarılan 12 girdi rastgele değil (güvenlik filtresi); 32 varyant kümesi ve her boyut için tek eğitim koşusu var;
14B ile 7B farklı GPU'larda eğitildi.

**Bilinen sorunlar (eğitilmiş 7B):** çelişen iddialar rakam ve özne karışması, ters yön, yanlış alel ya da hastalık şeklinde.
Gen düzeyi bir girdide (chr1:17001759:A>T) varyanta kaynakta olmayan bir hastalık ilişkisi yüklendi. Türkçe terimlerde bozulmalar
var. Her iddianın kararı ve gerekçesi `yargic_kontrol_2x2.jsonl`'de; aynı cevapların 56 girdilik önceki yargı turu
`yargic_kontrol.jsonl` / `yargic_kontrol_ozet.json`'da.

### Yönlendirici (`evaluation/results/router_*`)

Kurallar 39 mesajlık bir geliştirme setine bakılarak ayarlandı; o setteki 39/39 bir ölçüm değil, kod değişince eski davranışın
bozulmadığını gösteren regresyon testidir. Ölçüm, yönlendiricinin kodunu görmemiş bir yazarın (Claude alt ajanı; yalnız kategori
tanımları verildi) yazdığı ve kuralların ayarlanmasında kullanılmayan 80 mesajla yapıldı: **74/80 = %92,5**
(`router_ayri2_varchat-v2_2026-11-12.json`). Bundan önceki ilk bağımsız sette doğruluk 68/80 = %85,0 çıkmış, hatalar incelenip iki
mantık düzeltmesi yapılmıştı; o set bu yüzden artık geliştirme setidir. İki bağımsız seti aynı tür yazar aynı tanımlardan ürettiği
için birbirlerine benzerler; gerçek kullanıcı mesajlarıyla ölçüm yapılmadı. Kalan hata türleri: gen sembolüyle aynı yazılan
kelimeler ("ATM"), Türkçe yazılmış klinik adlar ("exon 7 delesyonu"), botun kendisi hakkındaki sorular.

### Eğitim (`fine_tune/results/v2/`, `fine_tune/results/v2-14b/`)

QLoRA (taban 4-bit, adaptör r=16, kayıp yalnız cevap tokenlarında), iki modelde aynı ayarlar. 501 örnek: 438 eğitim, 63 doğrulama;
doğrulamadaki 14 gen eğitimde yok (iki bölmenin kaynaklarında ortak tek bir makale var; 5 doğrulama örneğinde geçiyor). 3 tur;
her modelde en düşük doğrulama kayıplı 2. tur saklandı (3. turda ezber başlıyor).

| Model | GPU | Süre | Doğrulama kaybı (1 → 2 → 3. tur) |
|---|---|---|---|
| Qwen2.5-7B-Instruct | Colab A100 sınıfı | 26 dk | 0.717 → **0.684** → 0.708 |
| Qwen2.5-14B-Instruct | Colab RTX PRO 6000 Blackwell | 33 dk | 0.585 → **0.553** → 0.593 |

---

## 5. Bilinen eksikler ve sonraki adımlar

### Bilinen eksikler

- **Gen düzeyi modda varyant iddiası:** Varyanta özgü kaynak yoksa model yalnız gen hakkında yazmalı. Bir test girdisinde
  (chr1:17001759:A>T) yine de varyanta kaynakta olmayan bir hastalık ilişkisi yükledi; bunu yakalayan bir üretim sonrası kod
  denetimi yok.
- **Çelişen iddialar:** eğitilmiş 7B'nin atıflı cümlelerinin %13,5'i kaynağıyla çelişiyor (yanlış rakam, ters yön, yanlış alel ya
  da hastalık). Üretim sonrası denetim yalnız ClinVar sınıfıyla yön çelişkisini yakalıyor; cümledeki rakam ve yön kaynak metniyle
  karşılaştırılmıyor.
- **İnsan etiketi yok:** cevap kalitesini yalnız bir dil modeli (Claude Opus 5.5) yargıladı; eğitim örneklerini de aynı model ailesi
  yazdı.
- **Yıldız alel adları ve eski numaralama:** Sistem farmakogenetik yıldız alel adlarını (TPMT\*3A) ve bazı genlerin eski
  numaralamasını (EZH2 Y641N = Y646N) tanımıyor; bu girdilerde P@5 düşük.
- **Gen kısaltması çakışması:** Kısaltması başka bir terimle çakışan genlerde (APC = aktive protein C) arama konu dışı kaynak
  getirebiliyor; çakışma filtresi bu kısaltmayı içermiyor.

### Sonraki adımlar

- **Kendi arama ve yeniden sıralama sistemi:** Bugün ilk 5 makaleyi PubMed'in "Best Match" sıralaması seçiyor. Plan: varyantla ilgili
  makaleleri toplayıp en ilgili 5-10'unu kendi modelimizle sıralamak (monoBERT tarzı yeniden sıralayıcı; Nogueira ve ark. 2019).
  Bunun için "hangi sorgu için hangi makale ilgili" etiketli bir eğitim ve test seti kurulacak; sıralayıcılar MAP, nDCG ve P@k ile
  karşılaştırılacak (PubMed sırası, BM25, MedCPT ve kendi modelimiz), en iyisi uygulamaya takılıp cevap ölçümü tekrarlanacak.
- **İnsan etiketi:** cevap kalitesi ve arama değerlendirmesi için insan kontrollü bir test örneği.
- **Hazır veri setleriyle karşılaştırma:** 501 sentetik örnek yerine ya da yanında hazır kaynaklarla (ör. CIViC) eğitim.
- **Tez yazımı.**

---

## 6. Kaynaklar

- VarChat makalesi: De Paoli ve ark., Bioinformatics 40(4), 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11055464/
- Ensembl VEP REST — https://rest.ensembl.org (GRCh37 için grch37.rest.ensembl.org)
- NCBI E-utilities (PubMed, ClinVar) — https://www.ncbi.nlm.nih.gov/books/NBK25497/
- LitVar2 — https://www.ncbi.nlm.nih.gov/research/litvar2-api/ · PubTator3 — https://www.ncbi.nlm.nih.gov/research/pubtator3/
- ACMG/AMP 2015 sınıflandırma kılavuzu — https://pubmed.ncbi.nlm.nih.gov/25741868/
- LoRA (Hu ve ark. 2022) — https://arxiv.org/abs/2106.09685 · QLoRA (Dettmers ve ark. 2023) — https://arxiv.org/abs/2305.14314
- Atıf duyarlılığı: ALCE (Gao ve ark., EMNLP 2023) — https://arxiv.org/abs/2305.14627 · Liu ve ark. (Findings of EMNLP 2023) — https://arxiv.org/abs/2304.09848
- monoBERT (Nogueira ve ark. 2019) — https://arxiv.org/abs/1910.14424 · MedCPT (Jin ve ark., Bioinformatics 2023) — https://arxiv.org/abs/2307.00589
