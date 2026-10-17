"""
VarChat benzeri mini chatbot — İLK TAM HALİ.

Burada RAG'ın iki parçasını BİRLEŞTİRİYORUZ:
  1) BULUCU : varyantla ilgili makaleleri PubMed'den çek  (makale_getir.py'den hazır fonksiyonlar)
  2) BEYİN  : bu makaleleri Gemini'ye okutup KAYNAKLI bir özet ürettir

Akış: varyant gir -> makaleleri çek -> Gemini'ye bağlam olarak ver -> kaynaklı özet al
"""

import os
import sys

from dotenv import load_dotenv
from google import genai

# Arşiv dosyası: üst klasördeki (c01_/c02_) modülleri bulabilmek için üst klasörü yola ekliyoruz.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Kendi yazdığımız bulucu fonksiyonları. Tekrar yazmıyoruz; mevcut dosyadan çağırıyoruz.
from c01_makale_getir import makale_idleri_bul, makale_detaylari_al

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "gemini-2.5-flash"


def gemini_client_olustur():
    """Anahtarı .env'den okuyup Gemini bağlantısını hazırlar."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "buraya_kendi_anahtarini_yapistir":
        print("HATA: .env dosyasına geçerli bir GEMINI_API_KEY koymalısın.")
        raise SystemExit(1)
    return genai.Client(api_key=api_key)


def baglam_metni_olustur(makaleler):
    """Makaleleri, Gemini'ye verilecek NUMARALI tek bir metne dönüştürür.

    Her makaleye [1], [2]... numarası veriyoruz ki Gemini, özetinde hangi bilginin
    hangi kaynaktan geldiğini bu numaralarla gösterebilsin.
    """
    parcalar = []
    for i, m in enumerate(makaleler, start=1):
        parcalar.append(
            f"[{i}] Başlık: {m['baslik']}\n"
            f"    Özet: {m['ozet']}"
        )
    return "\n\n".join(parcalar)


def ozet_uret(client, varyant, baglam):
    """Gemini'ye makaleleri verip, kafadan uydurmadan, kaynaklı bir özet ürettirir."""
    talimat = (
        f"Aşağıda '{varyant}' genetik varyantıyla ilgili bilimsel makale özetleri var.\n"
        "Görevin: Bu varyantı, SADECE aşağıdaki kaynaklara dayanarak, anlaşılır bir Türkçe ile özetlemek.\n\n"
        "Kurallar:\n"
        "- Kendi bilginden bilgi EKLEME; yalnızca verilen özetlerdeki bilgileri kullan.\n"
        "- Her bilginin sonuna, onu aldığın kaynağın numarasını köşeli parantezle yaz: [1], [2] gibi.\n"
        "- Kaynaklarda cevabı yoksa 'Verilen kaynaklarda bu bilgi bulunmuyor' de.\n\n"
        f"KAYNAKLAR:\n{baglam}"
    )
    cevap = client.models.generate_content(model=MODEL, contents=talimat)
    return cevap.text


def main():
    varyant = input("Bir genetik varyant girin (örn. BRAF V600E): ").strip()
    if not varyant:
        varyant = "BRAF V600E"
        print("(Boş bırakıldı, örnek olarak 'BRAF V600E' kullanılıyor.)")
    print(f"\nAranan varyant: {varyant}\n")

    # 1) BULUCU: ilgili makaleleri çek
    pmidler = makale_idleri_bul(varyant, adet=5)
    if not pmidler:
        print("Bu varyantla ilgili makale bulunamadı.")
        return
    makaleler = makale_detaylari_al(pmidler)
    print(f"{len(makaleler)} makale bulundu. Gemini özetliyor...\n")

    # 2) BEYİN: makaleleri Gemini'ye okutup kaynaklı özet al
    client = gemini_client_olustur()
    baglam = baglam_metni_olustur(makaleler)
    ozet = ozet_uret(client, varyant, baglam)

    # 3) Sonucu göster: önce özet, sonra kaynak listesi (numaralar buradakilerle eşleşir)
    print("=" * 70)
    print("ÖZET:\n")
    print(ozet)
    print("\n" + "=" * 70)
    print("KAYNAKLAR:")
    for i, m in enumerate(makaleler, start=1):
        print(f"[{i}] {m['baslik']} — https://pubmed.ncbi.nlm.nih.gov/{m['pmid']}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
