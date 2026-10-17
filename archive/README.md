# Arşiv

Projenin artık kullanılmayan ama kayıt olarak saklanan dosyaları. Buradaki betikler çalıştırılmak için değil, geçmişi
göstermek içindir; taşındıkları için birbirlerini ya da kök klasördeki modülleri bulamayabilirler.
İstisna: `dataset_build_v4/` içindeki betiklerin yolları yeni yerlerine göre düzeltildi, çalışırlar.

| Dosya / klasör | Ne idi | Neden arşivde |
|---|---|---|
| `a01`-`a05` | İlk denemeler (Gemini, Ollama, sohbet, yönlendirici) | Yerlerini `m01` ve `evaluation/e09_router_eval` aldı |
| `c03_varchat_gemini.py` | Uygulamanın ilk sürümü (Gemini, bulut modeli) | Uygulama yerel modele (`m01`, Ollama) geçti |
| `beklemede/` | Embedding denemesi, Gemini ile veri üretme denemesi, ilk küçük eğitim verisi | Kullanılmadı |
| `degerlendirme/b01`, `b02` (eski ölçüm klasörünün adıyla), `faithfulness_verisi.jsonl` | İlk arama ve sadakat ölçümleri | Yerlerini `evaluation/e02`-`e05` aldı (b01 sorguyla döngüseldi) |
| `degerlendirme/b09_ogretmen_denetimi.py` | Eğitim verisini yerel yargıçla denetleme | Denetim Claude alt ajanlarıyla yapıldı (`archive/dataset_build_v4/`) |
| `degerlendirme/gece_kos.ps1` | Yerelde gece boyu ölçüm | Bütün ölçümler Colab'da, aynı ortamda yapıldı |
| `dataset_build_v4/` | 501 örneklik eğitim verisinin üretim hattı: 204 eski örneğin denetimi (`denetim_v3/`), 297 yeni örneğin yazımı ve doğrulaması (`yeni_ornekler/`), kaynak toplama (`f01_collect_sources.py`), birleştirme (`f02_build_dataset.py`) ve girdileri (`inputs/`) | Veri bir kez üretildi; ürün `fine_tune/egitim_verisi.jsonl`. Ayrıntı: `dataset_build_v4/README.md` |
| `fine_tune_v3/` | Eğitim verisinin ilk hattı (v3, 204 örnek): kaynak çekme, öğretmen özetleri, takip soruları, birleştirme | v4 hattı (`archive/dataset_build_v4/f01_collect_sources.py`, `f02_build_dataset.py`) yerini aldı; v3 verisi `archive/dataset_build_v4/inputs/egitim_verisi_v3.jsonl` |
| `sonuclar_ilk_baseline/` | Ham qwen2.5:7b'nin ilk Colab ölçümü (kod 8442021) | Koordinat girdilerinin hepsini reddettiren hata sonradan düzeltildi; geçerli ölçüm `evaluation/results/` |
| `VarChat_Proje_Sunumu.html` | Temmuz 2026 proje durumu sunumu | Güncel değil |
| `inj_sonuc.json` | Eylül 2026 istem saldırısı (prompt injection) denemesinin çıktısı | Tek seferlik deneme |
