"""
FINE-TUNE VERİSİ ÜRETME (Faz 3) — distillation.

Fikir: İyi çalışan Gemini'yi "ÖĞRETMEN" gibi kullanıp, her varyant için temiz,
kaynaklı, Türkçe bir özet ürettiriyoruz. Böylece elde ettiğimiz
   (girdi = varyant + makaleler)  ->  (çıktı = iyi özet)
çiftleri, yerel modeli (ÖĞRENCİ) fine-tune etmek için eğitim verisi olur.

Çıktı: egitim_verisi.jsonl  (her satır bir eğitim örneği)

Bu bir DEMO ölçeği (küçük varyant listesi). Mekanik çalışınca listeyi büyütürüz.
"""

import json
import os
import sys
import time

from dotenv import load_dotenv
from google import genai

# Beklemede klasöründe: ana klasördeki (c01_/c03_) modülleri bulabilmek için üst klasörü yola ekliyoruz.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c01_makale_getir import makale_idleri_bul, makale_detaylari_al
from c03_varchat_gemini import baglam_metni, arama_terimi_belirle

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "gemini-2.5-flash"   # öğretmen
CIKTI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "egitim_verisi.jsonl")

# Demo varyant listesi (çeşitli: gen, protein HGVS, rsID). İleride büyütülecek.
VARYANTLAR = [
    "BRAF V600E",
    "EGFR L858R",
    "KRAS G12C",
    "TP53 R175H",
    "JAK2 V617F",
    "rs334",
    "PIK3CA H1047R",
    "NRAS Q61R",
]


def ogretmen_ozet(client, varyant, baglam, deneme=4):
    """Öğretmen modele (Gemini) kaynaklı, temiz Türkçe özet ürettirir.
    Geçici hatalarda (503/429) bekleyip birkaç kez tekrar dener."""
    talimat = (
        f"Aşağıda '{varyant}' genetik varyantıyla ilgili bilimsel makale özetleri var.\n"
        "Bu varyantı, SADECE bu kaynaklara dayanarak, anlaşılır ve akıcı bir Türkçe ile özetle.\n"
        "- Kendi bilginden bilgi ekleme; yalnızca verilen özetleri kullan.\n"
        "- Her bilginin yanına kaynağını köşeli parantezle yaz: [1], [2] gibi.\n"
        "- Tıbbi terimleri doğru ve tutarlı kullan.\n\n"
        f"KAYNAKLAR:\n{baglam}"
    )
    for d in range(deneme):
        try:
            return client.models.generate_content(model=MODEL, contents=talimat).text
        except Exception as e:
            if d == deneme - 1:
                raise
            bekle = 5 * (d + 1)
            print(f"   (geçici hata, {bekle}s sonra tekrar: {str(e)[:45]}...)")
            time.sleep(bekle)


def main():
    load_dotenv()
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "").strip())

    yazilan = 0
    # Her örneği ÜRETİLDİĞİ ANDA dosyaya yazıyoruz ki bir hata olursa ilerleme kaybolmasın.
    with open(CIKTI, "w", encoding="utf-8") as f:
        for i, varyant in enumerate(VARYANTLAR, start=1):
            print(f"[{i}/{len(VARYANTLAR)}] {varyant} ...")
            terim = arama_terimi_belirle(varyant)
            makaleler = makale_detaylari_al(makale_idleri_bul(terim, adet=5))
            if not makaleler:
                print("   makale yok, atlanıyor.")
                continue

            baglam = baglam_metni(makaleler)
            try:
                ozet = ogretmen_ozet(client, varyant, baglam)
            except Exception as e:
                print(f"   üretilemedi, atlanıyor: {str(e)[:70]}")
                continue

            # Eğitim örneği: girdi = varyant + kaynaklar, cikti = öğretmenin özeti
            ornek = {
                "varyant": varyant,
                "girdi": f"'{varyant}' varyantını, aşağıdaki kaynaklara dayanarak Türkçe özetle.\n\n"
                         f"KAYNAKLAR:\n{baglam}",
                "cikti": ozet,
            }
            f.write(json.dumps(ornek, ensure_ascii=False) + "\n")
            f.flush()
            yazilan += 1
            print(f"   ✓ yazıldı ({len(ozet)} karakter).")
            time.sleep(1)   # öğretmen API'sini yormamak için minik bekleme

    print(f"\n{yazilan} örnek '{os.path.basename(CIKTI)}' dosyasına yazıldı.")


if __name__ == "__main__":
    main()
