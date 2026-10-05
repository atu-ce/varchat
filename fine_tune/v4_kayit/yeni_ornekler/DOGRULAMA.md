# VarChat eğitim verisi v4 — BAĞIMSIZ DOĞRULAMA YÖNERGESİ

Başka bir yazarın yazdığı eğitim örneklerini denetliyorsun. Yazım kuralları `YONERGE.md`'de (önce onu oku). Senin işin şüpheci
olmak: her cümleyi kaynağıyla tek tek karşılaştır. Varsayılan tutum: kaynakta açıkça yazmıyorsa DESTEKSİZ say.

## Girdi
- `paket_<N>.json`: girdiler ve numaralı kaynakları (başlık + özet + alaka)
- `yazim_<N>.json`: yazarın örnekleri

## Her örnek için kontrol et
1. **Sadakat:** Her cümledeki her iddia, atıf verilen kaynakta açıkça var mı? Sayılar/yüzdeler/popülasyonlar birebir mi?
   Abartma ("ilişkili" -> "neden olur"), genelleme (fare -> insan; tek çalışma -> "genellikle"), yanlış kaynağa atıf var mı?
2. **Varyant/gen karışması:** "gen" alakalı kaynağın bilgisi varyanta mal edilmiş mi? Gen kademesinde varyant hakkında iddia var mı?
3. **Atıf biçimi:** her cümle [n] ile bitiyor mu; numara kaynak sayısı içinde mi; atıfsız cümle var mı?
4. **Ret örnekleri** (ret_kapsam, gen_ret): soru GERÇEKTEN kaynaklardan cevaplanamaz mı? Kısmen bile cevaplanıyorsa RET_YANLIS.
5. **Türkçe:** yanlış/uydurma terim, çeviri hatası, anlamı bozan ifade, yabancı alfabe var mı?
6. **Bilinen hata kalıpları:** YONERGE.md'deki "Önceki sürümün denetiminde bulunan hatalar" listesindeki her kalıbı özellikle ara
   (genel bilgi ekleme, deney bağlamını düşürme, birleşik bulguyu tek varyanta mal etme, atıf kayması, niteleyici düşürme,
   çalışma bağlamı karıştırma, çeviri hatası).
7. **Soru kalitesi:** takip/çok turlu sorusu kaynaklardan cevaplanabilir ve özetin tekrarı değil mi?

## Karar ve düzeltme
Her örneğe bir karar ver:
- `GECER`: sorun yok.
- `DUZELTILDI`: sorunlu cümleleri düzelt ya da çıkar; düzeltilmiş tam metni yaz (kurallara uygun, her cümle [n] ile).
- `SIL`: kurtarılamaz (soru kaynaklardan cevaplanamıyor ama ret değil, ya da cevabın çoğu desteksiz).
- Ret örneklerinde: `RET_DOGRU` ya da `RET_YANLIS` (yanlışsa `duzeltilmis_soru` olarak kaynaklardan cevaplanamayan başka gerçekçi bir
  soru öner; öneremiyorsan SIL).
Düzeltirken yeni bilgi ekleme; yalnız kaynakta olanı bırak. Özet düzeltilirse çok turlu örneğin önceki özeti de o olacak (ayrıca
yazma, yalnız `ozet` alanını düzelt).

## Çıktı
`dogrulama_<N>.json` (UTF-8, geçerli JSON). Yazarın dosyasıyla AYNI yapı, alanlar SON (düzeltilmiş) hâliyle; ek olarak kararlar:
```json
{"paket": N, "girdiler": [
  {"girdi": "...",
   "ozet": "son metin ya da null (SIL)", "ozet_karar": "GECER|DUZELTILDI|SIL", "ozet_aciklama": "kısa neden",
   "takip": [{"soru": "...", "cevap": "son metin", "karar": "...", "aciklama": "..."}],
   "cok_turlu": {"soru": "...", "cevap": "...", "karar": "...", "aciklama": "..."} ,
   "ret_kapsam": [{"soru": "son soru", "karar": "RET_DOGRU|RET_YANLIS|SIL", "aciklama": "..."}],
   "gen_ret": [{"soru": "son soru", "karar": "...", "aciklama": "..."}]}
 ],
 "ozet": {"incelenen": 0, "gecer": 0, "duzeltildi": 0, "sil": 0, "ret_dogru": 0, "ret_yanlis": 0,
          "tekrarlayan_sorunlar": ["yazarın sık yaptığı hata türleri, kısa"]}}
```
SIL kararlı takip/çok turlu öğelerini listede bırak (karar SIL); birleştirici onları atar. Yazdıktan sonra dosyayı Python ile
`json.load` edip doğrula.
