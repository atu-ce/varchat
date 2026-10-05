# VarChat Benzeri Genetik Varyant Chatbotu

Yüksek lisans tez projesi (Kayseri Üniversitesi, Bilgisayar Mühendisliği).

Bir genetik varyant girildiğinde (örn. `BRAF V600E`, `rs334` ya da `chr7:140753336:A>T`)
o varyantla ilgili bilimsel makaleleri bulan, **yalnızca bu makalelere dayanarak**
Türkçe ve **kaynak gösteren** bir özet üreten, sonra aynı kaynaklar üzerinde
takip sorularına cevap veren bir chatbot.

Referans araç: [VarChat](https://varchat.engenome.com) (enGenome, Bioinformatics 2024,
[makale](https://pmc.ncbi.nlm.nih.gov/articles/PMC11055464/)).
Bizim farkımız: genom koordinatı girişi, tamamen yerel ve açık model, Türkçe çıktı ve
tekrar üretilebilir ölçüm.

---

## 1. Nasıl çalışıyor?

Kullanıcı `"BRAF V600E hangi kanserlerde görülür?"` yazsın.

```
Mesaj
 │
 ▼
[Yönlendirici]  selamlama / kendini tanıt / konu dışı / varyant / takip / belirsiz
 │               önce kurallar, emin değilse model; ilk üç sınıfın cevabı kodda sabittir
 ▼ (varyant)
[Gen doğrulama] gen sembolü HGNC listesinde var mı? "BRFA" → "BRAF mı demek istediniz?"
 │
 ▼
[Anlamlandırma] koordinat, HGVS ya da rsID → VEP "anotasyon kartı": gen, protein değişimi,
 │              rsID, gnomAD sıklığı, CADD (çok alelli rsID'de ClinVar'da önemi olan alel seçilir)
 ▼
[Bulucu]        PubMed'de kademeli arama: varyanta özgü sorgu → VEP'in kürasyonlu PMID'leri
 │              → gen düzeyi; her kaynak "varyant" / "gen düzeyi" diye etiketlenir
 ▼
[Üretim]        özetler + kurallar tek bir system prompt'a yazılır:
 │              "yalnızca bu kaynakları kullan, her cümleye [n] yaz, Türkçe konuş, yoksa 'bilgi yok' de"
 │              yerel model (qwen2.5:7b, Ollama) özeti üretir
 ▼
[Denetim]       kod denetler: geçersiz atıf silinir, atıfsız cümle sayılır, Çince çöküşte yeniden
 │              üretilir, özet ClinVar sınıfıyla ters yöndeyse uyarı basılır
 ▼
[Çıktı]         özet + kaynak listesi (PMID bağlantılı, kod basar) + ClinVar klinik önem satırı
 │
 ▼
[Takip]         sonraki sorular aynı kaynak bloğu üzerinde, sohbet geçmişiyle sorulur
```

Temel ilke: **model uydurmaz.** Bilgi VEP, PubMed ve ClinVar'dan gelir; model yalnızca
verilen kaynakları özetler. Kaynak listesini model değil kod bastığı için makale uydurulamaz.

---

## 2. Dosyalar

| Dosya | Rol | Ne yapar |
|---|---|---|
| `c01_makale_getir.py` | Kütüphaneci | Girilen metni PubMed'de aratır (esearch), ilk 5 makalenin başlık ve özetini çeker (efetch). |
| `c02_varyant_anlamlandir.py` | Adres çözücü | `chr7:140753336:A>T` gibi koordinatı Ensembl VEP'e sorup gen, rsID ve etki türünü alır. |
| `c03_varchat_gemini.py` | İlk sürüm (Gemini) | Bulut modeliyle çalışan eski sürüm. Ortak yardımcılar burada: özetleri numaralı metne çevirme, koordinatı arama terimine çevirme. |
| `c04_varchat_ollama.py` | **Ana uygulama** | Yerel model. Yönlendirici, doğrulama, VEP, PubMed, kaynaklı özet, takip soruları, ClinVar satırı. |
| `c05_gen_validasyon.py` | Kapıdaki isim listesi | 45.019 resmi gen sembolü (HGNC). Yanlış yazımda Jaro-Winkler benzerliğiyle öneri verir. |
| `c06_clinvar.py` | Hastane arşivi | Varyantı ClinVar'da rsID (dbSNP çapraz referansıyla doğrulanmış) ya da gen + 3 harfli protein değişimiyle bulur; kanonik kaydı yıldız ve gönderim sayısına göre seçer; germline, onkojenite ve klinik etki sınıflarını yıldızıyla gösterir; emin değilse susar. |
| `c07_sorgu_kur.py` | Sorgu kurucu + alaka kapısı | Girdiyi yapısal kayda çevirir (gen, rsID, V600E/Val600Glu, cDNA), PubMed'i kademeli arar (varyanta özgü sorgu → VEP'in kürasyonlu PMID'leri → gen düzeyi) ve her kaynağı `varyant` / `gen` diye etiketler. |
| `degerlendirme/test_seti.py` | Sınav kâğıdı | Dondurulmuş 45 girdi, 4 katman (kanser hotspot, eski adlı kalıtsal, rsID, literatürsüz); eğitim varyantlarıyla kesişimsiz. |
| `degerlendirme/b04_dogru_cevap.py` | Cevap anahtarı | Her girdi için "bu varyantı anan makaleler" listesi: girdiyle uyuşan tüm LitVar2 kayıtları birleştirilir (rsID, ad, eski ad, VEP proteini). rsID'lerden GRCh38/GRCh37 koordinat biçimleri türetilir. |
| `degerlendirme/b05_arama_dondur.py` | Arama ölçümü | Aramayı tarih damgasıyla dondurur, yeni hattın ve eski hattın P@5'ini aynı tanımla ölçer. Eski hat, git `b87d8a8` kodunun birebir kopyasıyla (`eski_hat/`) koşar. Hakem kararları sonradan çevrimdışı uygulanır (`--hakem`). |
| `degerlendirme/b06_toplu_uret.py`, `b07_sadakat.py`, `gece_kos.ps1` | Üretim ölçümü | Donmuş kaynaklarla her girdi için özet üretir; özeti cümle cümle yerel bir yargıç modelle kaynağa karşı denetler (destekleniyor / desteklenmiyor / çelişiyor). Kaldığı yerden devam eder. |
| `degerlendirme/colab_olcum.ipynb` | Colab'da ölçüm | Ollama'yı Colab GPU'suna kurar; ham `qwen2.5:7b` ve eğitilmiş `varchat` modelini aynı ortamda `b06` + `b07` ile ölçer, karşılaştırma tablosu çıkarır. Sonuçlar Drive'a yazılır. |
| `degerlendirme/b02`, `b03`, `denetim_testi.py` | Küçük ölçümler | `b02`: tek özet + modele giden kaynak metni. `b03`: yönlendirici doğruluğu. `denetim_testi.py`: atıf, cümle bölme ve çelişki denetimlerinin model çağırmadan çalışan testleri. (`b01` eski kelime eşleşmesi; sorguyla döngüsel, kullanılmıyor.) Sonuçlar `sonuclar/` altına. |
| `fine_tune/` | Oryantasyon paketi | 37 varyant, öğretmen (Claude) yazımı 204 örnek: özet, takip, çok turlu takip, başka gen sorusuna ret, kapsam dışı soruya ret. Gen bazlı ayrım: 171 eğitim / 33 doğrulama. Colab QLoRA defteri (Qwen2.5-7B, yalnız cevap üzerinden kayıp). |
| `arsiv/`, `beklemede/` | Denemeler | Eski testler; embedding denemesi (bge-m3). |

---

## 3. Kurulum ve çalıştırma

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

Yerel model için [Ollama](https://ollama.com) kurulu olmalı:

```bash
ollama pull qwen2.5:7b
python c04_varchat_ollama.py
```

İnternet yalnızca PubMed, VEP ve ClinVar sorguları için gerekir. Gemini sürümü (`c03`)
için `.env` dosyasına `GEMINI_API_KEY` yazılmalıdır; ana uygulama bunu kullanmaz.

---

## 4. Mevcut durum

Kod 13 Eylül 2026'da baştan sona denetlendi; 26 Eylül ve 4-5 Ekim'de denetim bulguları düzeltildi.

**Çalışan ve doğrulanan:**

- Girdi: koordinat, HGVS, rsID ve "GEN değişim" yazımları tek bir anotasyon kartına çözülüyor (referans harf doğrulanır,
  GRCh37 yedeği, indel). Çok alelli rsID'de kart ClinVar'da önemi olan alelle kuruluyor (rs6025 → Faktör V Leiden).
- Arama: PubMed varyanta özgü yapılandırılmış sorguyla aranıyor; varyanta özgü yayın yoksa kaynaklar "gen düzeyi" diye
  işaretleniyor ve bu, kullanıcıya kod tarafından söyleniyor.
- Üretim: pencere 8.192, sıcaklık 0, sabit tohum; sohbet geçmişi kayan pencereyle budanıyor (kaynak bloğu daima korunur).
  Üretim sonrası atıf, dil ve ClinVar yön çelişkisi denetimi; denetimlerin model çağırmadan çalışan testleri var.
- ClinVar: rsID/koordinat girdilerinde çalışıyor, kanonik kaydı seçiyor, üç sınıflandırmayı yıldızıyla gösteriyor.
- Yönlendirici: kural katmanı + aktif varyantı bilen model + takip sınıfı (39 mesajlık ölçümde 39/39).

**Arama ölçümü (5 Ekim 2026, `sonuclar/arama_ozet_2026-10-05.json`):** P@5, iki hat için aynı tanımla.
Eski hat = Temmuz'daki kod (git `b87d8a8`), birebir. "Otomatik" sütunu yalnız LitVar2/PubTator3/kürasyon listesine göre;
"hakemli" sütunu buna 14 insan hakem kararını ekler (`degerlendirme/hakem.jsonl`, 5 Ekim, ATU).

| Katman | Girdi | Yeni hat, otomatik | Eski hat, otomatik | Yeni hat, hakemli | Eski hat, hakemli |
|---|---|---|---|---|---|
| A: kanser hotspot | 15 | 0.84 | 0.79 | 0.91 | 0.88 |
| B: eski adlı kalıtsal | 15 | 0.89 | 0.85 | 0.91 | 0.87 |
| C: rsID | 10 | 0.96 | 0.90 | 1.00 | 0.90 |
| C: koordinat (GRCh38/GRCh37) | 11 | 0.98 | 0.20 | 1.00 | 0.20 |
| A+B+C | 51 | 0.91 | 0.70 | 0.94 | 0.73 |

Literatürsüz 5 girdinin 5'inde de sistem "gen düzeyi" uyarısı verdi, varyant hakkında iddia üretmedi.
Eski hat daha az makale döndürdüğü için yalnız döndürdükleri üzerinden kesinliği A/B'de biraz daha yüksek (0.88 ve 0.98);
en büyük fark koordinat girdisinde.

**Bilinen eksikler (öncelik sırasıyla):**

1. Üretim ölçümü (ham 7B ile toplu özet + iddia düzeyinde sadakat) hazır, Colab'da koşulacak (`colab_olcum.ipynb`).
2. Fine-tune henüz **yapılmadı**: düzeltilmiş 7B defteri hazır, eğitim çıktısı yok.
3. Otomatik doğru cevap listesi alt sınır: "GNASR201C" gibi bitişik yazımları kaçırıyor. Bu yüzden iki sütun raporlanıyor;
   kaçırılan 14 makale insan hakem kararıyla eklendi (`hakem.jsonl`, `b05 --hakem` ile çevrimdışı uygulandı).
4. Sistem yıldız alel adlarını (TPMT\*3A) ve eski numaralamayı (EZH2 Y641N = Y646N) bilmiyor; bu girdilerde P@5 düşük.
5. Çeviri kalitesi (ham 7B): yanlış Türkçe terimler ve bazı atıfsız cümleler; fine-tune'un birincil hedefi.
6. Anotasyon/ClinVar kartı prompt'a varsayılan olarak verilmiyor (eğitim verisiyle eşitlik için); `VERITABANI_PROMPTA`
   bayrağıyla ablasyon yapılacak.

---

## 5. Plan

| # | Adım | Durum |
|---|---|---|
| A | README ve iddiaları kanıta bağlamak; araştırma sorusunu tek cümleye indirmek | bu dosya |
| B | Girdiyi yapısal kayda çevirmek (gen, rsID, p./c. HGVS); referans harf ve GRCh37 kontrolü; indel | ✅ `c02` v2 |
| C | Sorgu kurucu: `gen AND (V600E OR Val600Glu OR rsID)`; alaka kapısı ("varyanta özgü yayın yok" uyarısı) | ✅ `c07` |
| D | Test seti (45 girdi + 11 türetilmiş koordinat, 4 katman) + LitVar2/PubTator3 doğru cevap listesi + dondurulmuş arama kaydı | ✅ `test_seti.py`, `b04`, `b05` (14 hakem kararı uygulandı) |
| E | Üretim: pencere 8.192, sıcaklık 0, kayan geçmiş, atıf ve dil kontrolü, ClinVar ile çelişki uyarısı, takip sınıfı | ✅ `c04` (prompt'a veritabanı kartı: bayrakla, ablasyon) |
| F | ClinVar: rsID yolu, yıldız (kanıt düzeyi), üç sınıflandırma, kanonik kayıt seçimi | ✅ `c06` v2 |
| G | Taban ölçümleri: ham 7B aynı test setinde (özet üretimi + iddia düzeyinde sadakat) | ⏳ Colab'da `colab_olcum.ipynb` ile, sırada |
| H | Fine-tune (7B, Colab Pro): düzeltilmiş defterle eğitim, aynı test setinde ölçüm | sırada: `colab_egitim.ipynb`, sonra `colab_olcum.ipynb` |
| I | Kendi arama motoru: PubTator3 varyant-anotasyonlu alt küme üzerinde BM25 + bge-m3 karma sıralama | zaman kalırsa |
| J | Tez yazımı | ☐ |

Web arayüzü ve tam metin korpusu: gelecek çalışma.

### Araştırma sorusu

Genom koordinatından başlayarak, yalnızca açık ve yerel bileşenlerle (VEP, PubMed/LitVar2,
Qwen), Türkçe ve kaynağı doğrulanabilir bir varyant özeti üretilebilir mi; literatür özeti ile
ClinVar/VEP bilgisi arasındaki çelişkiler otomatik yakalanabilir mi; küçük bir davranış ayarı
(LoRA) bunun neresini ne kadar iyileştirir?

### Nasıl ölçeceğiz

- **Bulucu:** P@5 = seçilen ilk 5 makaleden doğru olanların oranı (payda her zaman 5). Yanında "kesinlik (dönen)" ve 5 ile sınırlı recall.
  Doğru = LitVar2 listesinde, PubTator3 o makalede varyantı etiketlemiş ya da dbSNP/ClinVar kürasyonunda. Bu otomatik liste
  bir alt sınırdır ("GNASR201C" gibi bitişik yazımları kaçırır); kaçırdıkları insan hakem kararıyla ayrı sütunda sayılır.
  Model organizmada aynı değişimi inceleyen çalışma da doğrudur. Literatürsüz katmanda ölçü, "gen düzeyi" uyarısının verilmesidir.
- **Üretim:** iddia düzeyinde sadakat (destekleniyor / desteklenmiyor / çelişiyor; yerel yargıç, 30 iddia insan kontrolü),
  atıfsız cümle oranı, geçersiz atıf, yabancı alfabe, ClinVar yön çelişkisi
- **Yönlendirici:** 39 mesaj, karışıklık matrisi
- Her koşu tarih, PMID listesi ve model ayarlarıyla `degerlendirme/sonuclar/` altına kaydedilir

---

## 6. Kaynaklar

- VarChat makalesi: De Paoli ve ark., Bioinformatics 40(4), 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11055464/
- Ensembl VEP REST — https://rest.ensembl.org (GRCh37 için grch37.rest.ensembl.org)
- NCBI E-utilities (PubMed, ClinVar) — https://www.ncbi.nlm.nih.gov/books/NBK25497/
- LitVar2 — https://www.ncbi.nlm.nih.gov/research/litvar2-api/ · PubTator3 — https://www.ncbi.nlm.nih.gov/research/pubtator3/
- ACMG/AMP 2015 sınıflandırma kılavuzu — https://pubmed.ncbi.nlm.nih.gov/25741868/
- LoRA (Hu ve ark. 2022) — https://arxiv.org/abs/2106.09685 · QLoRA (Dettmers ve ark. 2023) — https://arxiv.org/abs/2305.14314
