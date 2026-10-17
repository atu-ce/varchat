# Arşiv

Projenin artık kullanılmayan ama kayıt olarak saklanan dosyaları. Buradaki betikler çalıştırılmak için değil, geçmişi
göstermek içindir; taşındıkları için birbirlerini ya da kök klasördeki modülleri bulamayabilirler.

| Dosya / klasör | Ne idi | Neden arşivde |
|---|---|---|
| `a01`-`a05` | İlk denemeler (Gemini, Ollama, sohbet, yönlendirici) | Yerlerini `m01` ve `evaluation/e09_router_eval` aldı |
| `c03_varchat_gemini.py` | Uygulamanın ilk sürümü (Gemini, bulut modeli) | Uygulama yerel modele (`m01`, Ollama) geçti |
| `beklemede/` | Embedding denemesi, Gemini ile veri üretme denemesi, ilk küçük eğitim verisi | Kullanılmadı |
| `degerlendirme/b01`, `b02` (eski ölçüm klasörünün adıyla), `faithfulness_verisi.jsonl` | İlk arama ve sadakat ölçümleri | Yerlerini `evaluation/e02`-`e05` aldı (b01 sorguyla döngüseldi) |
| `degerlendirme/b09_ogretmen_denetimi.py` | Eğitim verisini yerel yargıçla denetleme | Denetim Claude alt ajanlarıyla yapıldı (`fine_tune/v4_kayit/`) |
| `degerlendirme/gece_kos.ps1` | Yerelde gece boyu ölçüm | Bütün ölçümler Colab'da, aynı ortamda yapıldı |
| `fine_tune_v3/` | Eğitim verisinin ilk hattı (v3, 204 örnek): kaynak çekme, öğretmen özetleri, takip soruları, birleştirme | v4 hattı (`fine_tune/f01_collect_sources.py`, `f02_build_dataset.py`) yerini aldı; v3 verisi `fine_tune/ara_veri/egitim_verisi_v3.jsonl` |
| `sonuclar_ilk_baseline/` | Ham qwen2.5:7b'nin ilk Colab ölçümü (kod 8442021) | Koordinat girdilerinin hepsini reddettiren hata sonradan düzeltildi; geçerli ölçüm `evaluation/sonuclar_colab/` |
| `VarChat_Proje_Sunumu.html` | Temmuz 2026 proje durumu sunumu | Güncel değil |
| `inj_sonuc.json` | Eylül 2026 istem saldırısı (prompt injection) denemesinin çıktısı | Tek seferlik deneme |
