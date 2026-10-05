# VarChat eğitim verisi v4 — ÖĞRETMEN CEVABI YAZIM YÖNERGESİ

Bir Türkçe genetik varyant sohbet asistanı (Qwen2.5-7B, LoRA ile ince ayar) için eğitim örnekleri yazıyorsun. Model canlı sistemde
bir system mesajı alır: "SADECE aşağıdaki KAYNAKLAR'a dayanarak yanıt ver; her cümlenin sonuna kaynağını yaz [1]; kaynağı olmayan
cümle yazma; cevap kaynaklarda yoksa yalnızca 'Bu konuda elimdeki kaynaklarda bilgi yok.' de". Senin yazdığın cevaplar modelin
taklit edeceği ÖRNEKLERDİR: modelin öğreneceği davranış = kaynağa sadakat. Önceki sürümde öğretmen cevapları kaynakta olmayan
genellemeler, abartılar ve yanlış çeviriler içerdi ve eğitilen model daha çok uydurur hâle geldi. Bu yüzden KATI ol.

## Girdi
Paket JSON'u: her girdi için `girdi`, `etiket` (modelin varyanta verdiği ad), `kademe` ("varyant" ya da "gen"), `gen`, `alan`,
`ilk_soru` (özet sorusu, AYNEN kullanılır), `kaynaklar` ({"1": {"baslik", "ozet", "alaka"}, ...}) ve `istenen` (kaç örnek).
`alaka`: "varyant" = makale varyantı anıyor; "kurasyon" = dbSNP/ClinVar makaleyi varyanta bağlamış ama metinde ad geçmeyebilir;
"gen" = makale yalnız geni anlatıyor, varyantı ANMIYOR (modele "(GEN DÜZEYİ: varyantın kendisini anmıyor)" diye işaretli gider).

## Altın kurallar (hepsi zorunlu)
1. **Her cümle, işaret ettiği kaynağın başlık/özetinde AÇIKÇA yazanla desteklenmeli.** Kendi bilgini (doğru olsa bile) ekleme.
   Kaynakta "ilişkili bulundu" yazıyorsa "neden olur" yazma; "fare modelinde" ise insan için genelleme; "bir çalışmada" ise
   "genellikle" deme. Sayıları, yüzdeleri, örneklem büyüklüklerini, p değerlerini, popülasyonları AYNEN aktar (ondalık virgülle: %12,5).
2. **Her cümle [n] ile biter** (birden fazla kaynak: [1][3] ya da [1], [3]). Atıfsız giriş/geçiş cümlesi YOK ("Özetle," gibi bile).
   Madde işareti ve başlık kullanma; düz paragraf yaz.
3. **Atıf doğru kaynağa** gitmeli: bilgi [2]'deyse [2] yaz, [1] değil. Kaynak sayısından büyük numara kullanma.
4. **Varyant ≠ gen.** "gen" alakalı kaynaktaki bilgi varyanta mal edilmez: "X geni ... ile ilişkilidir [3]" doğru,
   "X G2019S ... yol açar [3]" YANLIŞ (kaynak varyantı anmıyorsa). Kaynak başka bir varyantı/aleli anlatıyorsa bunu açıkça söyle
   ya da kullanma.
5. **Atomik ve sade cümleler.** Bir cümle bir ya da iki iddia taşısın; 35 kelimeyi geçmesin. Doğal, akıcı Türkçe; çeviri kokan
   kalıplardan kaçın.
6. **Terimler:** missense = yanlış anlamlı (missense); nonsense = anlamsız / erken durdurma kodonu; frameshift = çerçeve kayması;
   splicing = kırpılma (splicing); loss/gain of function = işlev kaybı/kazanımı; penetrance = penetrans; founder mutation = kurucu
   mutasyon; odds ratio = olasılık oranı (OR); hazard ratio = tehlike oranı (HR); allele frequency = alel sıklığı; carrier = taşıyıcı;
   tight junction = sıkı bağlantı; knock-in mouse = knock-in fare; wild-type = yabanil tip; cohort = kohort; case-control =
   olgu-kontrol. Emin olmadığın terimde Türkçe karşılık + parantez içinde İngilizcesi. Gen/protein/ilaç adları ve varyant adları
   (G2019S, c.1100delC, rs671) olduğu gibi kalır. Uydurma Türkçe kelime üretme.
7. **Cevap uzunluğu:** özet 4-8 cümle (1-3 paragraf); takip 1-4 cümle. Kaynaklarda gerçekten bilgi varsa kısa da olsa CEVAP VER;
   gereksiz ret yok.

## Önceki sürümün denetiminde bulunan hatalar — BUNLARI YAPMA
- **Kaynakta olmayan genel bilgi:** "12. kodondaki glisinin valine dönüşmesi", "eski adıyla T877A" gibi doğru ama kaynakta yazmayan
  tanımlar. Kaynakta yoksa yazma.
- **Deney bağlamını düşürmek:** hücre hattı (HUDEP-2, NIH 3T3), fare modeli, in vitro bulgusu insan/doku/hasta bulgusu gibi yazılmış
  ("kemik iliğinde tetikler"). Bağlamı cümlede koru: "eritroid öncül hücre hattında ...", "fare modelinde ...".
- **Birleşik bulguyu tek varyanta mal etmek:** çok mutasyonlu bir modelin (L702H/H875Y/F877L/T878A) ya da birleşik hasta grubunun
  ("T878A veya L702H taşıyanlar") bulgusu yalnız bu varyantın bulgusu gibi yazılmış.
- **Atıf kayması:** bilgi [1]'deyken [4] yazmak. Her cümleyi yazınca kaynağını yeniden bul.
- **Niteleyici düşürmek / derecelendirme eklemek:** "ilk kovalent olmayan inhibitör" -> "ilk inhibitör"; "birçok mekanizmadan biri"
  -> "başlıca neden"; "çalışmalarda" -> "her zaman". Kaynağın kesinlik derecesini koru.
- **Bağlam karıştırmak:** bir çalışmanın sonucunu başka bir çalışmaya (FLAURA birinci basamak sonucu -> T790M tedavisi) bağlamak.
- **Çeviri hataları:** "first-line" = birinci basamak (tedavi sırası), "birinci nesil" DEĞİL; "germline" = germ hattı (Türkçeleştir);
  "driver" = sürücü ("onkojenik sürücü"), fiil olarak "sürükler" DEĞİL; bispecific = bispesifik; leukemogenesis = lösemogenez;
  prime editing = prime düzenleme (prime editing). İlaç adlarını kaynaktaki yazımıyla bırak (elexacaftor), Türkçeleştirme.
- **Gen/mutasyon sınıfı bulgusunu varyanta mal etmek:** "IDH2 mutasyonları AML'nin %15'inde" bilgisi R140Q'nun sıklığı değildir;
  "PIK3CA mutasyonları ..." bulgusu H1047R'ye ait değildir. Cümlede öznenin kaynaktaki gibi kalmasına dikkat et.
- **Onay/kılavuz bilgisini genellemek:** kaynak "Avrupa'da onaylandı" diyorsa bölgeyi koru; kaynak onaydan söz etmiyorsa "onaylı" deme.

## Örnek türleri (`istenen` kadar yaz)
- **ozet:** `ilk_soru`nun cevabı. Varyant kademesinde: varyant nedir/nerede, işlevsel etkisi, hastalık/fenotip ilişkisi, sıklık,
  klinik/tedavi bulguları — yalnız kaynaklarda olanlar. Gen kademesinde ("X geni hakkında kaynaklı bir özet yaz."): YALNIZ gen
  hakkında; girilen varyant/koordinat hakkında HİÇBİR iddia yok (patojenik/zararsız deme, etkisini tahmin etme).
- **takip:** kaynaklardan cevaplanabilen, ÇEŞİTLİ bir soru + kaynaklı cevap. Soru tipleri karışık olsun: mekanizma, sıklık/popülasyon,
  fenotip/klinik tablo, tedavi/ilaç yanıtı, çalışma tasarımı/örneklem ("bu bulgu hangi çalışmadan?"), evet/hayır soruları
  ("... ile ilişkili mi?"), karşılaştırma ("heterozigot ile homozigot arasında fark var mı?"). Soru üslubu da karışık: resmi, günlük,
  kısa ("bu ilaç yanıtını etkiler mi?"), arada bir küçük harf/noktalamasız yazılmış soru. Soru varyantın adını ya da "bu varyant"ı
  kullanabilir. Gen kademesinde takip soruları GEN hakkında olur.
- **cok_turlu:** özetten SONRA sorulan, özette olmayan bir ayrıntıyı isteyen soru + kaynaklı cevap (özetin tekrarı olmasın).
- **ret_kapsam:** kaynaklarda CEVABI OLMAYAN ama gerçekçi bir soru; cevap tam olarak "Bu konuda elimdeki kaynaklarda bilgi yok."
  Örnek yönler: ilaç dozu, kişisel tıbbi tavsiye ("bende bu var, ne yapmalıyım"), Türkiye'deki sıklık, test maliyeti, kaynaklarda
  geçmeyen bir hastalık/ilaç, kaynakta olmayan bir sayı. Kaynakları dikkatle oku: soru kısmen bile cevaplanabiliyorsa başka soru seç.
- **gen_ret** (yalnız gen kademesi): girilen VARYANTIN kendisi hakkında soru (etkisi, patojenitesi, hangi hastalığa yol açtığı,
  taşıyıcıya ne olacağı); cevap tam olarak "Bu konuda elimdeki kaynaklarda bilgi yok." Soru varyantı `etiket`teki adıyla ya da
  "bu varyant / bu değişim" diye ansın. **İlk gen_ret sorusu, gen özetinden HEMEN SONRA sorulacak** (sohbetin 2. sorusu): özeti
  okuyan birinin doğal sorusu gibi yaz ("Peki bu değişim zararlı mı?", "Benim bulduğum varyant bu hastalığa yol açar mı?").
  İkincisi bağımsız tek soru olarak sorulur; varyantı adıyla ansın.

Sorular Türkçe; cevaplar YALNIZ Türkçe (Latin alfabesi; Çince/İngilizce cümle yok).

## Çıktı
`yazim_<N>.json` dosyasına (UTF-8, geçerli JSON) yaz:
```json
{"paket": N, "girdiler": [
  {"girdi": "...", "ozet": "...",
   "takip": [{"soru": "...", "cevap": "..."}],
   "cok_turlu": {"soru": "...", "cevap": "..."},
   "ret_kapsam": ["soru", ...],
   "gen_ret": ["soru", ...],
   "not": "kaynaklarla ilgili dikkat çeken durum (örn. 'kaynak 4 başka bir alel', 'kaynak 2 konu dışı'), yoksa boş"}
]}
```
İstenmeyen alanı boş liste/null bırak. Yazdıktan sonra dosyayı Python ile `json.load` edip doğrula ve her cevabın her cümlesinin
[n] ile bittiğini kontrol et.
