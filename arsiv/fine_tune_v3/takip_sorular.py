# Öğretmen (Claude) tarafından yazılmış TAKİP-SORU örnekleri.
# Her örnek: aynı varyantın kaynaklarına dayanan, odaklı ve kaynaklı bir soru-cevap.
# Kullanıcının özet sonrası soracağı gerçekçi soruları taklit eder; veriyi zenginleştirir.
# [n] atıfları, o varyantın kaynaklar.jsonl'daki kaynak numaralarıyla uyumludur.

TAKIP = [

# ---- BRAF V600E ----
{"varyant": "BRAF V600E", "soru": "BRAF V600E hangi kanserlerde görülür?",
 "cevap": "Ameloblastomda yüksek sıklıkta (%70,49) [1], papiller tiroid karsinomunda en yaygın onkojenik sürücü olarak [3] ve gliomlarda en sık BRAF değişimi olarak (çocukluk çağı düşük dereceli astrositomları, pleomorfik ksantoastrositom, gangliogliom gibi) görülür [5]. Kolon kanseri ve melanomda da bulunur [2]."},
{"varyant": "BRAF V600E", "soru": "BRAF V600E tedavisinde hangi ilaçlar kullanılır?",
 "cevap": "Vemurafenib, dabrafenib ve selumetinib gibi seçici BRAF ve MEK inhibitörleri ileri tiroid kanserlerinde etkinlik gösterir; dabrafenib-trametinib kombinasyonu BRAF V600E'li anaplastik tiroid karsinomu için FDA onaylıdır [3]. Kolon kanserinde ise EGFR geri besleme direnci nedeniyle BRAF ve EGFR inhibitörlerinin birlikte kullanımı gerekebilir [2]."},
{"varyant": "BRAF V600E", "soru": "BRAF V600E nasıl tespit edilir?",
 "cevap": "Mutasyon durumu genellikle PCR temelli DNA testleriyle belirlenir; 2011'den beri BRAF V600E'ye özgü antikorlar (klon VE1) immünohistokimyasal saptamaya da olanak tanır [4]."},

# ---- EGFR L858R ----
{"varyant": "EGFR L858R", "soru": "EGFR L858R kimlerde daha sık görülür?",
 "cevap": "EGFR mutasyonları Asya kökenli hastalarda (%30-50), Kafkas kökenlilere göre (%10-15) daha sıktır [1]."},
{"varyant": "EGFR L858R", "soru": "EGFR L858R'de tedaviye direnç nasıl gelişir?",
 "cevap": "TKİ tedavisi sırasında en sık ikincil T790M mutasyonu ile direnç gelişir; EAI045 gibi allosterik inhibitörler L858R/T790M mutantını hedefleyip setuksimab ile sinerji gösterir [3][5]."},
{"varyant": "EGFR L858R", "soru": "EGFR L858R ile ekson 19 delesyonu arasında fark var mı?",
 "cevap": "İkisi de klasik aktive edici mutasyonlardır ve EGFR tirozin kinaz inhibitörlerine iyi yanıt öngörür [2]; ancak klinik davranışları farklıdır ve sonuçların ekson 19 delesyonlu hastalarda daha iyi olabileceği giderek kabul görmektedir [1][4]."},

# ---- EGFR T790M ----
{"varyant": "EGFR T790M", "soru": "EGFR T790M neden önemlidir?",
 "cevap": "Birinci nesil EGFR tirozin kinaz inhibitörlerine (gefitinib, erlotinib, afatinib) karşı kazanılmış direncin en sık nedenidir ve dirençli hastaların yaklaşık yarısında bulunur [1][4]."},
{"varyant": "EGFR T790M", "soru": "EGFR T790M tedavisinde ne kullanılır?",
 "cevap": "Üçüncü nesil TKİ osimertinib, T790M mutasyonlu metastatik küçük hücreli dışı akciğer kanseri için onay alan ilk ilaçtır [2] ve FLAURA çalışmasında birinci nesil TKİ'lere göre daha uzun progresyonsuz sağkalım sağlamıştır [5]."},
{"varyant": "EGFR T790M", "soru": "Osimertinibe direnç gelişir mi?",
 "cevap": "Evet; en sık üçlü mutasyonla (duyarlılaştıran mutasyon/T790M/C797S) ortaya çıkar ve mevcut tüm EGFR TKİ'lerine dirençlidir; bu mutantlara karşı EAI045 ve CH7233163 gibi yeni bileşikler geliştirilmektedir [1][5]."},

# ---- KRAS G12C ----
{"varyant": "KRAS G12C", "soru": "KRAS G12C hangi ilaçlarla hedeflenir?",
 "cevap": "AMG 510 (sotorasib) klinik geliştirmeye giren ilk KRAS G12C inhibitörüdür [1]; sotorasib ve adagrasib ileri/metastatik küçük hücreli dışı akciğer kanseri için onaylanmıştır [2]."},
{"varyant": "KRAS G12C", "soru": "KRAS G12C inhibitörleri neden kolorektal kanserde daha az işe yarar?",
 "cevap": "Küçük hücreli dışı akciğer kanserinin aksine kolorektal kanser bu inhibitörlere nadiren yanıt verir; başlıca neden EGFR sinyalinin yeniden aktive olmasıdır ve EGFR ile G12C'nin birlikte hedeflenmesi direnci aşar [4]."},
{"varyant": "KRAS G12C", "soru": "KRAS G12C'ye hangi mutasyonlar eşlik eder?",
 "cevap": "STK11, KEAP1 ve TP53 sık görülen ko-mutasyonlardır; STK11 birlikteliği immünoterapinin etkisini zayıflatabilir [2][3]."},

# ---- KRAS G12D ----
{"varyant": "KRAS G12D", "soru": "KRAS G12D en çok hangi kanserde görülür?",
 "cevap": "Solid tümörlerde en sık görülen onkojenik KRAS alt tipidir ve özellikle pankreas adenokarsinomlarının neredeyse yarısında bulunur [1][2]."},
{"varyant": "KRAS G12D", "soru": "KRAS G12D'yi hedefleyen ilaç var mı?",
 "cevap": "MRTX1133 ilk güçlü ve seçici KRAS G12D inhibitörüdür; yaban tipe kıyasla yaklaşık 700 kat seçicidir ve pankreas modellerinin çoğunda tümör gerilemesi sağlar [3][4]. HRS-4642 de faz 1'de umut verici antitümör aktivitesi göstermiştir [2]."},
{"varyant": "KRAS G12D", "soru": "MRTX1133 bağışıklık sistemini etkiler mi?",
 "cevap": "Evet; pankreas modellerinde tümör mikroçevresini yeniden programlayarak tümör içi CD8+ T hücrelerini artırır ve immün kontrol noktası blokajı ile sinerji göstererek sağkalımı uzatır [1]."},

# ---- TP53 R175H ----
{"varyant": "TP53 R175H", "soru": "TP53 R175H ne kadar sık görülür?",
 "cevap": "R175H, en yüksek sıklıkta görülen TP53 sıcak nokta mutasyonudur [1][5]."},
{"varyant": "TP53 R175H", "soru": "R175H, p53'ün işlevini nasıl değiştirir?",
 "cevap": "Yaban tip p53 'genomun bekçisi' olarak DNA onarımı, hücre döngüsü durması ve apoptozu tetiklerken, R175H bu işlevleri kaybeder ve proliferasyon, göç, invazyon ve ilaç direnci gibi kanseri destekleyen yeni işlevler kazanır [5]."},
{"varyant": "TP53 R175H", "soru": "TP53 R175H hedeflenebilir mi?",
 "cevap": "Mutant p53'ün ilaçlanabilir bir aktif bölgesi olmadığından hedefleme zordur [4]; yaklaşımlar arasında R175H'ye özgü bir antikorun biespesifik immünoterapötik ajana dönüştürülmesi [1] ve p53-R175H'yi seçici olarak yıkan bir PROTAC (dp53m) yer alır [4]."},

# ---- JAK2 V617F ----
{"varyant": "JAK2 V617F", "soru": "JAK2 V617F hangi hastalıkta görülür?",
 "cevap": "Miyeloproliferatif neoplazilerde (MPN) en yaygın sürücü mutasyondur ve JAK/STAT sinyal yolunu sitokinlerden bağımsız olarak sürekli aktive eder [1]."},
{"varyant": "JAK2 V617F", "soru": "JAK2 V617F kalp krizi riskini artırır mı?",
 "cevap": "Klonal hematopoez bağlamında miyokard enfarktüsü riskini artırır; özellikle plak erozyonuyla güçlü ilişkilidir (OR 16,2), plak rüptürüyle ise anlamlı ilişki göstermez [4]."},
{"varyant": "JAK2 V617F", "soru": "JAK inhibitörleri JAK2 V617F'yi tamamen tedavi eder mi?",
 "cevap": "Hayır; JAK inhibitörleri yaygın kullanılsa da MPN hücrelerini kökten yok edemez, bu nedenle uzun süreli tedavi gerekir ve diğer ilaçlarla kombinasyonları araştırılmaktadır [1]."},

# ---- PIK3CA H1047R ----
{"varyant": "PIK3CA H1047R", "soru": "PIK3CA H1047R hangi kanserde en sık görülür?",
 "cevap": "Meme kanserinde en sık görülen PIK3CA sıcak nokta mutasyondur; tüm PIK3CA mutasyonlarının yaklaşık %35'ini oluşturur ve hormon reseptörü pozitif/HER2-negatif alt tipte daha sıktır [1]."},
{"varyant": "PIK3CA H1047R", "soru": "PIK3CA H1047R için onaylı bir tedavi var mı?",
 "cevap": "İleri PIK3CA-mutant meme kanserinde therascreen tanı testi ve alfa-özgül PI3K inhibitörü alpelisib onaylıdır [1]."},
{"varyant": "PIK3CA H1047R", "soru": "PIK3CA H1047R kanser dışında hastalığa yol açar mı?",
 "cevap": "Evet; somatik H1047R mutasyonu PI3Kα-AKT-mTOR yolunu aşırı aktive ederek venöz malformasyonlara neden olur ve fare modellerinde TIE2 veya ANGPT hedeflenmesi lezyon büyümesini baskılamıştır [2]."},

# ---- NRAS Q61R ----
{"varyant": "NRAS Q61R", "soru": "NRAS Q61R en çok hangi kanserde görülür?",
 "cevap": "Melanomda en sık ikinci onkojenik sürücü olan NRAS Q61* mutasyonları arasında yer alır [4]."},
{"varyant": "NRAS Q61R", "soru": "NRAS Q61R nasıl tespit edilir?",
 "cevap": "Tiroid patolojisinde NRAS Q61R immünohistokimyası, RAS Q61R mutasyonunu yüksek duyarlılık (%90,6) ve özgüllükle (%92,3) saptar; ancak antikor NRAS, KRAS ve HRAS Q61R proteinlerine çapraz reaksiyon verir [2]."},
{"varyant": "NRAS Q61R", "soru": "NRAS Q61R hedeflenebilir mi?",
 "cevap": "NRAS Q61* mutantlarını seçici hedefleyen klinik ajanlar henüz yoktur; ancak NRAS Q61R ile doğrudan etkileşen SHOC2, RAS Q61* tümörleri için bir bağımlılık olarak tanımlanmış ve SHOC2-RAS etkileşimini bozan küçük moleküller geliştirilmiştir [4]."},

# ---- IDH1 R132H ----
{"varyant": "IDH1 R132H", "soru": "IDH1 R132H prognozu nasıl etkiler?",
 "cevap": "Dünya Sağlık Örgütü derece II-III ve sekonder gliomlarda daha iyi prognozla ilişkilidir [4][5]; glioblastom modellerinde hücre çoğalmasını, göçü ve invazyonu azaltır ve apoptozu artırır [5]."},
{"varyant": "IDH1 R132H", "soru": "IDH1 R132H için aşı çalışması var mı?",
 "cevap": "Evet; IDH1(R132H)-özgül peptit aşısı, yeni tanı almış derece 3-4 astrositomlu hastalarda faz I çalışmasında güvenli bulunmuş ve hastaların %93,3'ünde bağışıklık yanıtı oluşturmuştur [2]."},
{"varyant": "IDH1 R132H", "soru": "IDH1 R132H'yi hedefleyen ilaç var mı?",
 "cevap": "Mutant enzimin aktivitesini düzenleyen C269 otopalmitoilasyon bölgesi, klinik bir IDH1-mutant inhibitörünün (LY3410738) hedefidir [3]."},

# ---- KIT D816V ----
{"varyant": "KIT D816V", "soru": "KIT D816V hangi hastalıkta görülür?",
 "cevap": "Mastositoz ve mast hücresi aktivasyon sendromlarının (MCAS) tanı ve sınıflandırmasında temel taşıdır [1]."},
{"varyant": "KIT D816V", "soru": "KIT D816V nasıl tespit edilir?",
 "cevap": "Deri lezyonu olmayan hastalarda düşük mutant hücre yükü nedeniyle saptanması zordur; yeni Flow-SuperRCA testi geleneksel ASO-qPCR'a göre daha duyarlıdır (saptama sınırı %0,001'e karşı %0,01 alel sıklığı) [1]."},
{"varyant": "KIT D816V", "soru": "KIT D816V tedavisinde ne kullanılır?",
 "cevap": "Avapritinib, sistemik mastositozda hastalığı değiştirebilen ilk ruhsatlı ilaçtır; bezuklastinib ve elenestinib gibi güçlü, oral ve seçici KIT tirozin kinaz inhibitörleri de uzun süreli remisyon olasılığı sunar [4]."},

# ---- FLT3 D835Y ----
{"varyant": "FLT3 D835Y", "soru": "FLT3 D835Y hangi hastalıkta görülür?",
 "cevap": "Akut miyeloid lösemide (AML) FLT3 reseptörünün tirozin kinaz alanında en sık görülen nokta mutasyonudur [5]."},
{"varyant": "FLT3 D835Y", "soru": "FLT3 D835Y prognozu nasıl?",
 "cevap": "FLT3-ITD taşıyan hastaların prognozu daha kötüdür; knock-in fare modellerinde D835Y'li fareler ITD'li farelere göre daha uzun yaşar ve daha az agresif miyeloproliferatif neoplazi geliştirir [5]."},
{"varyant": "FLT3 D835Y", "soru": "FLT3 D835Y direnç oluşturur mu?",
 "cevap": "Evet; seçici FLT3 inhibitörlerine karşı kazanılmış direncin başlıca nedenlerindendir ve bu hücreler AC220 (quizartinib) ile sorafenibe yüksek direnç gösterir [4]. Direnci aşmak için FLT3/Aurora A inhibitörü CCT245718 gibi ikili inhibitörler geliştirilmektedir [3]."},

# ---- MYD88 L265P ----
{"varyant": "MYD88 L265P", "soru": "MYD88 L265P en çok hangi hastalıkta görülür?",
 "cevap": "Waldenström makroglobulinemisi vakalarının yaklaşık %90'ında bulunur; ayrıca aktive B-hücre tipi difüz büyük B-hücreli lenfomalarda ve IgM monoklonal gammopatilerde önemli oranda görülür [1]."},
{"varyant": "MYD88 L265P", "soru": "MYD88 L265P tedavisinde ne kullanılır?",
 "cevap": "Waldenström makroglobulinemisinde Bruton tirozin kinaz (BTK) inhibitörleri (ör. zanubrutinib) ve kemoimmünoterapi ön plandadır [3]; L265P, NF-κB yolunu aktive ederek hastalığı sürükler [2]."},
{"varyant": "MYD88 L265P", "soru": "MCD tipi lenfoma nedir?",
 "cevap": "MYD88 L265P ile CD79B mutasyonlarının birlikte bulunmasıyla tanımlanan, kötü prognoz ve ekstranodal (özellikle immün-ayrıcalıklı bölge) tutulumuyla karakterize bir difüz büyük B-hücreli lenfoma alt grubudur [2][5]."},

# ---- CFTR F508del ----
{"varyant": "CFTR F508del", "soru": "CFTR F508del hangi hastalığa yol açar?",
 "cevap": "Kistik fibrozisin en sık nedenidir; hastaların %80'inden fazlası bu mutasyonu taşır [1]."},
{"varyant": "CFTR F508del", "soru": "CFTR F508del proteini nasıl etkiler?",
 "cevap": "Üç nükleotitlik bir delesyon olan bu mutasyon CFTR'nin katlanmasını bozar ve protein, endoplazmik retikulum ilişkili yıkım (ERAD) ile parçalanarak hücre yüzeyine ulaşamaz [1]."},
{"varyant": "CFTR F508del", "soru": "CFTR F508del için tedavi var mı?",
 "cevap": "Evet; elexakaftor + tezakaftor + ivakaftor üçlü kombinasyonu, F508del için homozigot hastalarda beklenen FEV1 yüzdesini yaklaşık 10 puan artırmış ve ter klorürünü belirgin düşürmüştür [3]. Bu düzelticiler CFTR-F508del'i yıkımdan kurtararak çalışır [1]."},

# ---- AKT1 E17K ----
{"varyant": "AKT1 E17K", "soru": "AKT1 E17K hangi kanserlerde görülür?",
 "cevap": "Meme, kolorektal ve over kanserlerinde görülen bir sıcak nokta mutasyondur [2]."},
{"varyant": "AKT1 E17K", "soru": "AKT1 E17K tedavisinde ne kullanılır?",
 "cevap": "NCI-MATCH çalışmasında pan-AKT inhibitörü kapivasertib, AKT1 E17K mutasyonlu metastatik tümörlerde %28,6 objektif yanıt oranı sağlamıştır [1]; meningiom modellerinde AKT inhibitörü AZD5363 etkili bulunmuştur [4]."},
{"varyant": "AKT1 E17K", "soru": "AKT1 E17K'nın çelişkili etkileri nelerdir?",
 "cevap": "Melanomda beyin metastazını FAK aktivasyonu yoluyla artırırken [3], bazı bağlamlarda β-katenin sinyalini baskılayıp E-kaderin ifadesini artırarak hücre göçünü paradoksal olarak engeller; bu nedenle AKT inhibitörlerinin bazı genetik zeminlerde metastazı hızlandırabileceği öne sürülmüştür [2][5]."},

# ---- ABL1 T315I ----
{"varyant": "ABL1 T315I", "soru": "ABL1 T315I neden önemlidir?",
 "cevap": "İlaç bağlanma cebindeki 'bekçi' (gatekeeper) kalıntısını değiştirerek çoğu tirozin kinaz inhibitörüne kazanılmış direnç oluşturur ve kötü prognozla ilişkilidir [3]."},
{"varyant": "ABL1 T315I", "soru": "T315I mutasyonuna hangi ilaçlar etkilidir?",
 "cevap": "T315I taşıyan hastalarda yalnızca ponatinib, asciminib ve olverembatinib etkilidir; diğer tirozin kinaz inhibitörlerinin çoğu bu mutasyona karşı işe yaramaz [1]."},
{"varyant": "ABL1 T315I", "soru": "Asciminib nasıl çalışır?",
 "cevap": "Asciminib, ABL miristoil cebini özgül olarak hedefleyen (STAMP) ilk onaylı BCR::ABL1 inhibitörüdür [4] ve en az iki önceki tirozin kinaz inhibitörü almış ya da T315I taşıyan KML hastaları için onaylıdır [2]."},

# ---- IDH2 R140Q ----
{"varyant": "IDH2 R140Q", "soru": "IDH2 R140Q hangi hastalıkta görülür?",
 "cevap": "İzositrat dehidrogenaz 2'deki en sık mutasyondur ve sitogenetik olarak normal akut miyeloid löseminin %15'inden fazlasında görülür [1][2]."},
{"varyant": "IDH2 R140Q", "soru": "IDH2 R140Q hücreleri nasıl etkiler?",
 "cevap": "TF-1 hücrelerini sitokinden bağımsız çoğalmaya dönüştürür; bu, STAT3 ve STAT5'in anormal sürekli fosforilasyonuyla ilişkilidir ve STAT3/5 inhibisyonu bu çoğalmayı baskılar [1]."},
{"varyant": "IDH2 R140Q", "soru": "IDH2 R140Q tedavisinde direnç olur mu?",
 "cevap": "IDH2/R140Q'yu hedeflemek klinikte umut verici sonuçlar vermiştir; ancak tedavi edilen hastaların %12'sinde direnç gelişir [1]."},

# ---- DNMT3A R882H ----
{"varyant": "DNMT3A R882H", "soru": "DNMT3A R882H ne yapar?",
 "cevap": "DNA metilasyon örüntüsünü bozarak klonal hematopoezin en yaygın biçimini sürükler ve akut miyeloid lösemi riskini artırır [1][3]."},
{"varyant": "DNMT3A R882H", "soru": "DNMT3A R882H lösemi için gerekli mi?",
 "cevap": "CRISPR çalışmaları, mutasyonun lösemi başlangıcı için gerekli olduğunu ancak yerleşmiş hastalığın sürdürülmesi için büyük ölçüde gereksiz olduğunu göstermiştir [3]."},
{"varyant": "DNMT3A R882H", "soru": "Metformin DNMT3A R882H ile ilişkili mi?",
 "cevap": "Mutant hücreler oksidatif fosforilasyona daha bağımlıdır; metformin klonal genişlemeyi baskılar ve metformin kullanan bireylerde DNMT3A-R882-mutant klonal hematopoez prevalansı belirgin biçimde düşük bulunmuştur [1]."},

# ---- PDGFRA D842V ----
{"varyant": "PDGFRA D842V", "soru": "PDGFRA D842V hangi tümörde görülür?",
 "cevap": "Gastrointestinal stromal tümörlerde (GİST) görülür; PDGFRA geninin ekson 18'indeki en sık mutasyondur [2]."},
{"varyant": "PDGFRA D842V", "soru": "PDGFRA D842V neden imatinibe dirençlidir?",
 "cevap": "D842V, imatinib ve sunitinib başta olmak üzere konvansiyonel tirozin kinaz inhibitörlerine birincil (intrinsik) direnç sağlar [2][4]."},
{"varyant": "PDGFRA D842V", "soru": "PDGFRA D842V tedavisinde ne kullanılır?",
 "cevap": "Avapritinib, bu mutasyonu taşıyan GİST için ilk onaylı ajandır ve klinik çalışmalarda %88-95 gibi yüksek genel yanıt oranları sağlamıştır [1][3][5]."},

# ---- RET M918T ----
{"varyant": "RET M918T", "soru": "RET M918T hangi kanserde görülür?",
 "cevap": "Medüller tiroid karsinomunun başlıca sürücülerindendir; MEN2B vakalarının %95'inde ve sporadik medüller tiroid karsinomlarının yaklaşık %50'sinde bulunur [5]."},
{"varyant": "RET M918T", "soru": "RET M918T tedavisinde ne kullanılır?",
 "cevap": "Vandetanib ve kabozantinib gibi çoklu kinaz inhibitörleri ileri hastalıkta etkilidir; sonrasında yüksek seçicilikli RET inhibitörleri selperkatinib ve pralsetinib daha yüksek etkinlik ve daha az hedef-dışı yan etkiyle kliniğe girmiştir [2]."},
{"varyant": "RET M918T", "soru": "RET M918T prognozu etkiler mi?",
 "cevap": "Dolaşımdaki hücre dışı DNA'da (cfDNA) RET M918T saptanması, kötü genel sağkalımla güçlü biçimde ilişkilidir ve kalsitonin ikilenme süresinden daha güvenilir bir prognostik belirteç olabilir [4]."},

# ---- ESR1 Y537S ----
{"varyant": "ESR1 Y537S", "soru": "ESR1 Y537S neye yol açar?",
 "cevap": "Östrojen reseptörünün östrojenden bağımsız (ligandsız) aktivasyonuna yol açar ve metastatik meme kanserinde endokrin tedaviye dirençle ilişkilidir [2][4]."},
{"varyant": "ESR1 Y537S", "soru": "ESR1 Y537S prognozu nasıl etkiler?",
 "cevap": "Saldırgan hastalık biyolojisiyle ilişkilidir; BOLERO-2 çalışmasında Y537S taşıyan hastaların genel sağkalımı yaban tipe göre daha kısa bulunmuştur [4]."},
{"varyant": "ESR1 Y537S", "soru": "ESR1 Y537S fulvestranta dirençli mi?",
 "cevap": "Evet; Y537S mevcut östrojen reseptörü antagonisti fulvestranta göreli direnç gösterir; AZD9496 gibi yeni nesil antagonistler ve vepdegestrant (ARV-471) gibi oral PROTAC yıkıcılar bu mutantı daha etkili baskılayabilir [2][5]."},

# ---- PIK3CA E545K ----
{"varyant": "PIK3CA E545K", "soru": "PIK3CA E545K ne kadar sık görülür?",
 "cevap": "Meme kanserinde H1047R'den sonra ikinci en sık PIK3CA mutasyonudur; tüm PIK3CA mutasyonlarının %17'sini oluşturur ve serviks ile kolorektal kanserde de sık görülür [2]."},
{"varyant": "PIK3CA E545K", "soru": "PIK3CA E545K prognozu etkiler mi?",
 "cevap": "Kolorektal kanser hastalarında daha kötü genel sağkalımın bağımsız bir göstergesi olarak bulunmuştur [3]."},
{"varyant": "PIK3CA E545K", "soru": "PIK3CA E545K radyoterapiye direnç yapar mı?",
 "cevap": "Evet; serviks kanserinde SIRT4'ü baskılayıp glutamin metabolizmasını artırarak ve β-katenin yolunu aktive ederek radyoterapiye direnç sağlar; PI3K inhibitörü BYL719 veya β-katenin hedeflemesi bu direnci azaltabilir [1][4]."},

# ---- KRAS G12V ----
{"varyant": "KRAS G12V", "soru": "KRAS G12V hedeflenebilir mi?",
 "cevap": "Henüz doğrudan hedefleyen onaylı bir inhibitör yoktur; ancak KRAS'ı çalıştıran SOS1'in inhibisyonuyla dolaylı hedefleme ve EGFR'ye yönlendirilen seçici RNA interferansı (EFTX-G12V) gibi yaklaşımlar araştırılmaktadır [1][3]."},
{"varyant": "KRAS G12V", "soru": "KRAS G12V hangi kanserde sık görülür?",
 "cevap": "Kanserde en sık ikinci KRAS mutasyonudur ve pankreas duktal adenokarsinomlarında KRAS mutasyonlarının yaklaşık %34'ünü oluşturur [1][3]."},
{"varyant": "KRAS G12V", "soru": "KRAS G12V için immünoterapi var mı?",
 "cevap": "KRAS G12V mutant neoantijeni HLA-A*11:01 bağlamında sunulur ve buna özgü T hücresi reseptörleriyle donatılmış T hücreleri, mutasyonu taşıyan tümör hücrelerine karşı sitotoksik etki gösterir [2]."},

# ---- HFE C282Y ----
{"varyant": "HFE C282Y", "soru": "HFE C282Y hangi hastalığa yol açar?",
 "cevap": "Demir emilimini düzenleyen HFE genindeki en sık patojenik varyanttır; kalıtsal hemokromatoz büyük ölçüde C282Y homozigotluğundan (iki kopya) kaynaklanır [1][3]."},
{"varyant": "HFE C282Y", "soru": "HFE C282Y kanser riskini artırır mı?",
 "cevap": "UK Biobank kohortunda C282Y homozigot erkeklerde primer karaciğer kanseri riski belirgin biçimde artmıştır (HR 10,5); meta-analizler meme ve kolorektal kanser riskiyle de ilişki bildirmiştir [2][3][5]."},
{"varyant": "HFE C282Y", "soru": "HFE C282Y metabolik sendromla ilişkili mi?",
 "cevap": "Hayır; metabolik sendrom bileşenleriyle (diyabet, hipertansiyon, lipid düzeyleri) yapılan meta-analizde anlamlı bir ilişki bulunmamıştır [4]."},

# ---- SF3B1 K700E ----
{"varyant": "SF3B1 K700E", "soru": "SF3B1 K700E hangi hastalıkta görülür?",
 "cevap": "Hematolojik malignitelerde, özellikle miyelodisplastik sendromda (MDS) görülen, RNA kırpma faktörü SF3B1'deki en sık mutasyondur [1][2]."},
{"varyant": "SF3B1 K700E", "soru": "SF3B1 K700E halka sideroblasta nasıl yol açar?",
 "cevap": "Kemik iliğinde halka sideroblast oluşumunu doğrudan tetikler; ABCB7 ve ALAS2 ifadesini bozar ve ABCB7 kaybı demir-kükürt kümesi taşınmasını engelleyerek halka sideroblast oluşumuna yol açar [2]."},
{"varyant": "SF3B1 K700E", "soru": "SF3B1 K700E prognozu nasıl etkiler?",
 "cevap": "SF3B1 mutasyonları MDS'de genellikle olumlu kabul edilir; ancak bir çalışma, yalnızca K700E mutasyonunun bağımsız olarak daha iyi genel sağkalım öngördüğünü göstermiştir [3]."},

# ---- TERT promoter C228T ----
{"varyant": "TERT promoter C228T", "soru": "TERT promoter C228T ne işe yarar?",
 "cevap": "TERT ifadesini artırarak telomeraz aktivitesini yükseltir; glioblastomada en sık görülen mutasyondur ve gliom gelişiminin en erken olaylarından biridir [1]."},
{"varyant": "TERT promoter C228T", "soru": "TERT promoter C228T prognozu etkiler mi?",
 "cevap": "Baş-boyun skuamöz hücreli karsinomunda C228T, daha kısa hastalıksız ve genel sağkalımla ilişkilidir; bu nedenle prognostik bir biyobelirteç olabilir [2]."},
{"varyant": "TERT promoter C228T", "soru": "C228T ve C250T birlikte bulunur mu?",
 "cevap": "TERT promotörünün bu iki sıcak nokta mutasyonu genellikle birbirini dışlar; oligodendrogliomlarda IDH mutasyonu ve 1p/19q ko-delesyonuyla birlikte görülürler [4]."},

# ---- GNAQ Q209L ----
{"varyant": "GNAQ Q209L", "soru": "GNAQ Q209L hangi kanserde görülür?",
 "cevap": "Başlıca üveal (göz içi) melanomda görülür; bu tümörlerin %80-90'ı GNAQ ya da homolog GNA11'de Q209 mutasyonları taşır [2][3]. Ayrıca leptomeningeal melanositik neoplazileri de sürükler [1]."},
{"varyant": "GNAQ Q209L", "soru": "GNAQ Q209L hedeflenebilir mi?",
 "cevap": "Bu G proteinini doğrudan hedefleyen bilinen bir ilaç yoktur; siRNA/rAAV ile allel-özgül susturma ve Gαq'yu katlayan şaperon Ric-8A'nın inhibisyonu gibi yaklaşımlar araştırılmaktadır [2][3]."},
{"varyant": "GNAQ Q209L", "soru": "GNAQ Q209L ile GNA11 arasında ilişki nedir?",
 "cevap": "Üveal melanomda GNAQ ve homolog GNA11 mutasyonları birbirini dışlar; ikisi de aynı Q209 pozisyonunu etkileyerek G proteinini sürekli aktive eder [2][4]."},

# ---- CTNNB1 S45F ----
{"varyant": "CTNNB1 S45F", "soru": "CTNNB1 S45F hangi tümörde görülür?",
 "cevap": "Desmoid tip fibromatoz (desmoid tümör) vakalarında görülür; T41A ile birlikte en sık CTNNB1 değişimlerindendir [1][2]."},
{"varyant": "CTNNB1 S45F", "soru": "CTNNB1 S45F nüksü etkiler mi?",
 "cevap": "Evet; S45F mutasyonu (HR 5,25) ve ekstremite yerleşimi cerrahi sonrası lokal nüks için bağımsız risk faktörleridir ve diğer mutasyonlara göre daha yüksek nüks olasılığıyla ilişkilidir [2][3]."},
{"varyant": "CTNNB1 S45F", "soru": "CTNNB1 S45F tedaviye yanıtı etkiler mi?",
 "cevap": "Evet; COX-2 inhibitörü meloksikam ile tedavide S45F taşıyan tüm olgular kötü yanıt (hastalık ilerlemesi) göstermiştir, diğer mutasyonların etkisi olmamıştır [1]."},

# ---- POLE P286R ----
{"varyant": "POLE P286R", "soru": "POLE P286R ne yapar?",
 "cevap": "DNA polimeraz epsilon'un düzeltme-okuma işlevini bozarak 'ultra-mutatör' bir fenotipe ve çok yüksek tümör mutasyon yüküne yol açar; endometriyum ve kolorektal kanserde görülür [1][4]."},
{"varyant": "POLE P286R", "soru": "POLE P286R immünoterapiye yanıtı etkiler mi?",
 "cevap": "Evet; mikrosatellit kararlı olmasına rağmen immün kontrol noktası blokajına duyarlı, hipermutasyonlu bir alt sınıfı tanımlar ve immünoterapi için potansiyel bir biyobelirteçtir [3][4]."},
{"varyant": "POLE P286R", "soru": "POLE P286R nasıl bağışıklık yanıtı uyandırır?",
 "cevap": "DNA hasarını artırıp sitoplazmik DNA birikimine yol açar; bu, cGAS-STING yolunu aktive ederek kansere karşı içsel bağışıklığı uyarır ve tümör oluşumunu baskılar [2]."},

# ---- TP53 R248Q ----
{"varyant": "TP53 R248Q", "soru": "TP53 R248Q p53'ü nasıl etkiler?",
 "cevap": "DNA-bağlanma alanındaki R248 kalıntısını değiştirir; uzak bölgelerde konformasyon değişikliğine ve çinko-bağlanma cebinde bozulmaya yol açarak dominant-negatif etki gösterir ve agregasyona eğilim kazandırır [5]."},
{"varyant": "TP53 R248Q", "soru": "TP53 R248Q tedaviye direnç yapar mı?",
 "cevap": "Evet; akut lenfoblastik lösemi hücre modellerinde R248Q, p53 transaktivasyon aktivitesini bozarak kemoterapötik ajanlara ve ışınlamaya direnç kazandırmıştır [2]."},
{"varyant": "TP53 R248Q", "soru": "TP53 R248Q kazanılmış işlev gösterir mi?",
 "cevap": "Evet; over karsinomunda aşırı ifade edildiğinde AKT fosforilasyonunu artırır ve EGFR sinyalini sürdürür; glioblastomda ise hücre yapışması ve göçünü artırır [1][3]."},

# ---- KRAS G13D ----
{"varyant": "KRAS G13D", "soru": "KRAS G13D hangi kanserde önemlidir?",
 "cevap": "Kolorektal kanserde sık görülür, kötü prognozla ilişkilidir ve kendine özgü biyolojik davranış gösterir [1]."},
{"varyant": "KRAS G13D", "soru": "KRAS G13D setuksimaba dirençli mi?",
 "cevap": "KRAS mutasyonları setuksimaba doğal direnç sağlar; G13D-mutant kolorektal kanserde HER2-ELF3-KRAS ekseni bu direnci sürükler ve bu eksenin bozulması hücreleri setuksimaba duyarlı hale getirir [1][2]."},
{"varyant": "KRAS G13D", "soru": "KRAS G13D'nin biyokimyasal özelliği nedir?",
 "cevap": "Aktif bölgedeki elektrostatik yük dağılımını değiştirerek diğer KRAS mutantlarına kıyasla hızlı nükleotit değişim kinetiği gösterir [5]."},

# ---- FGFR3 S249C ----
{"varyant": "FGFR3 S249C", "soru": "FGFR3 S249C hangi kanserde görülür?",
 "cevap": "Mesane kanserinde en sık görülen tekrarlayan FGFR3 mutasyonudur; düşük dereceli papiller ürotelyal karsinomların %60'ından fazlası aktive edici FGFR3 mutasyonları taşır [1][3]."},
{"varyant": "FGFR3 S249C", "soru": "FGFR3 S249C neden bu kadar sık görülür?",
 "cevap": "S249C (TCC→TGC) bir APOBEC motifini temsil eder ve muhtemelen APOBEC aracılı mutasyonel süreçten kaynaklanır; bu, tümörlerdeki fazla temsilini açıklar [1]."},
{"varyant": "FGFR3 S249C", "soru": "FGFR3 S249C, FGFR inhibitörlerine yanıt verir mi?",
 "cevap": "Ürotelyal karsinomda erdafitinib gibi FGFR inhibitörleri onaylıdır; ancak S249C mutasyonu tedavi yanıtıyla negatif korelasyon gösterirken FGFR3-TACC3 füzyonları daha yüksek yanıtla ilişkilidir [2]."},

# ---- MPL W515L ----
{"varyant": "MPL W515L", "soru": "MPL W515L hangi hastalıkta görülür?",
 "cevap": "JAK2 V617F-negatif miyeloproliferatif neoplazilerde, özellikle esansiyel trombositoz ve primer miyelofibrozda görülür; sıklığı düşüktür (ET/PMF'de yaklaşık %2,6) [5]."},
{"varyant": "MPL W515L", "soru": "MPL W515L tanıda ne işe yarar?",
 "cevap": "Philadelphia kromozomu ya da JAK2 V617F taşımayan MPN hastalarında klonaliteyi göstermede yardımcı olabilir; saptanan olgular genellikle JAK2 V617F-negatiftir [5]."},
{"varyant": "MPL W515L", "soru": "MPL W515L için tedavi hedefi var mı?",
 "cevap": "MPN'lerin lösemiye dönüşümünde rol oynayan DUSP6 inhibisyonu, MPLW515L fare modellerinde hastalık gelişimini baskılar ve JAK2 inhibitörü direncini aşabilir [4]."},

# ---- AR T878A ----
{"varyant": "AR T878A", "soru": "AR T878A neden önemlidir?",
 "cevap": "Androjen reseptörünün ligand-bağlanma alanındaki bir mutasyon olarak prostat kanserinde hormonal tedavilere dirençle ilişkilidir [4]."},
{"varyant": "AR T878A", "soru": "AR T878A tedavi direncine nasıl yol açar?",
 "cevap": "Abirateron tedavisi sırasında ilerleme anında ortaya çıkabilir ve taşıyan hastalarda PSA yanıtı daha düşük, sağkalım daha kötüdür [2]. Ayrıca F877L ile birlikte enzalutamid gibi antagonistleri agoniste dönüştürebilir [1][5]."},
{"varyant": "AR T878A", "soru": "AR T878A için hedefe yönelik tedavi var mı?",
 "cevap": "T878A-mutant AR'yi seçici hedefleyen yeni bir antagonist (S-94), yaban tip AR'ye kıyasla yaklaşık 50 kat daha güçlü etkiyle önemli T878A-ilişkili mutantları baskılamıştır [3]."},

# ---- PTEN R130Q ----
{"varyant": "PTEN R130Q", "soru": "PTEN R130Q ne yapar?",
 "cevap": "Tümör baskılayıcı PTEN'in fosfataz alanındaki bir sıcak nokta mutasyondur; PTEN'in PIP2'ye bağlanmasını bozup işlevini yitirmesine yol açar [3][5]."},
{"varyant": "PTEN R130Q", "soru": "PTEN R130Q hangi kanserde görülür?",
 "cevap": "Endometriyum kanserinde en sık PTEN missense mutasyonlarından biridir (R130G ile birlikte); hepatoselüler karsinom ve glioblastomda da görülür [2][3][4]."},
{"varyant": "PTEN R130Q", "soru": "PTEN R130Q tedavi edilebilir mi?",
 "cevap": "PTEN alterasyonları mTORC1 inhibitörleriyle (ör. everolimus) tedavi edilebilir; pineal bölge tümörlü bir hastada tek başına everolimusla tümör gerilemesi bildirilmiştir [1]."},

# ---- HRAS G12V ----
{"varyant": "HRAS G12V", "soru": "HRAS G12V ne yapar?",
 "cevap": "RAS'ı sürekli aktif hale getiren onkojenik bir mutasyondur; NIH 3T3 hücrelerinde hücre boyutu kontrolünü bozmaya tek başına yeterlidir [3][4]."},
{"varyant": "HRAS G12V", "soru": "HRAS G12V, Costello sendromu ile ilişkili mi?",
 "cevap": "Evet; HRAS'ın germline G12V mutasyonu Costello sendromuna (bir RASopati) neden olur; konjenital kalp anomalileri, gelişme geriliği ve kansere yatkınlıkla karakterizedir [4]."},
{"varyant": "HRAS G12V", "soru": "HRAS G12V immün kaçışa katkıda bulunur mu?",
 "cevap": "Orofarengeal skuamöz hücreli karsinomda HRAS G12V, laktat varlığında MEK/ERK yolunu aktive ederek immün kaçışa katkıda bulunan PD-L1 ifadesini artırır [5]."},

# ---- ALK F1174L ----
{"varyant": "ALK F1174L", "soru": "ALK F1174L hangi kanserde görülür?",
 "cevap": "Nöroblastomdaki en sık ALK somatik mutasyonlarından biridir ve kötü sağkalımın belirteci MYCN amplifikasyonuyla birlikte görülür [4]."},
{"varyant": "ALK F1174L", "soru": "ALK F1174L nöroblastomu nasıl sürükler?",
 "cevap": "Tek başına nöroblastom oluşturmaya yetmez; ancak MYCN ile birlikte ifade edildiğinde MYCN'nin onkojenik yeteneğini belirgin biçimde güçlendirerek ölümcül nöroblastoma yol açar [4]."},
{"varyant": "ALK F1174L", "soru": "ALK F1174L ilaç direnci yapar mı?",
 "cevap": "Evet; ALK-translokasyonlu kanserlerde krizotinibe kazanılmış direnç oluşturur; kimyasal olarak farklı bir ALK inhibitörü (TAE684) ve HSP90 inhibitörü 17-AAG bu mutasyonu taşıyan modellerde etkilidir [1][5]."},

]
