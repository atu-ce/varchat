# Eğitim verisi v4: nasıl üretildi

`fine_tune/egitim_verisi.jsonl` (501 örnek) iki kaynaktan oluşur. Bu klasör o sürecin ham kayıtlarıdır.

## 1. Eski 204 örneğin denetimi (`denetim_v3/`)

- **Ne:** v3 verisindeki (Temmuz 2026, öğretmen = Claude) her cevabın her cümlesi, atıf verdiği kaynağın başlık + özetiyle karşılaştırıldı.
  Denetimi 6 bağımsız Claude alt ajanı yaptı (paket başına 32-38 örnek).
- **Kararlar:** `AYNEN`, `DUZELTILDI` (düzeltilmiş metin eklenir), `SIL`, `RET_DOGRU`, `RET_YANLIS`. Ham çıktılar `sonuc_1..6.json`.
- **Birleştirme:** `birlestir_denetim.py` → `fine_tune/denetim_v3.json`. Bir karar elle geri çevrildi (örnek 172; gerekçe betikte).
- **Sonuç:** 56 aynen, 92 düzeltildi, 0 silindi, 56/56 ret doğru. Özetlerin 35/37'si düzeltme istedi.
  377 cümlenin %56'sı tam destekli, %32'si kısmen, %7'si yanlış kaynağa atıflı, %5'i dil hatalı.
- **Tekrarlayan hatalar:** kaynakta olmayan genel bilgi, fare/hücre bulgusunun insana genellenmesi, birleşik bulgunun tek varyanta
  mal edilmesi, atıf kayması, niteleyici düşürme, çeviri hataları ("first-line" → "birinci nesil").

## 2. 74 yeni girdinin örnekleri (`yeni_ornekler/`)

- **Girdiler ve kaynaklar:** `fine_tune/kaynak_topla_v4.py` → `fine_tune/kaynaklar_v4.jsonl`. Uygulamanın kendi arama hattı
  (c07) kullanıldı; system mesajı canlı sistemle aynı.
  - 19 tıp alanı.
  - Biçimler: gen-değişim, eski ad, rsID, GRCh38/GRCh37 koordinat, intron (gen düzeyi).
  - Test setinin ve v3'ün genleri dışarıda bırakıldı.
- **Yazım:** `YONERGE.md` kurallarıyla 8 alt ajan yazdı (`yazim_1..8.json`). Paketleri `paket_uret.py` hazırladı.
- **Doğrulama:** `DOGRULAMA.md` ile, yazmamış 8 ayrı alt ajan cümle cümle denetledi (`dogrulama_1..8.json`).
  - Ret dışı 207 cevabın 42'si (%20) düzeltildi, 0 silindi.
  - 60 ret sorusundan 1'i değiştirildi.
- **Toplama:** `topla.py` → `fine_tune/yeni_ornekler_v4.jsonl`. Bir özet elle düzeltildi (rs9923231; gerekçe betikte).

## 3. Birleştirme

`fine_tune/birlestir_v4.py` → `fine_tune/egitim_verisi.jsonl`.

- **Ne yapar:**
  - Denetim kararlarını uygular; çok turlu örneklerde önceki özet de düzeltilmiş hâliyle değişir.
  - Yeni örnekleri ekler.
  - "Yabancı soru" ret örnekleri üretir: soru başka bir girdinin genini/değişimini/rsID'sini açıkça anmalı, bunlar bu girdinin
    kaynaklarında geçmemeli.
  - Bölmeyi gen bazlı yapar: 14 doğrulama geni.
- **Sonuç:** 501 örnek (438 eğitim, 63 doğrulama).
  - Tür dağılımı: 111 özet, 130 takip, 114 çok turlu, 146 ret (%29).
  - En uzun örnek 4146 token (Qwen tokenizer); defterdeki sınır 4608.

v3'ün değişmemiş hâli: `fine_tune/egitim_verisi_v3.jsonl`.
