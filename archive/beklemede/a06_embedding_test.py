"""
EMBEDDING / SEMANTİK ARAMA — deneme (kendi bulucumuzun ilk adımı).

Amaç: "Embedding gerçekten ANLAMI yakalıyor mu?" bunu elle görmek.
Cümleleri vektöre çevirip benzerliklerini ölçüyoruz. Anlamca yakın cümleler
(farklı kelimelerle, hatta farklı dilde olsa bile) yüksek benzerlik vermeli.

Model: bge-m3 (çok dilli — Türkçe + İngilizce; çapraz dil eşleştirme yapar).
Ollama ile yerelde çalışır.
"""

import math
import sys

import ollama

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "bge-m3"


def embed(metin):
    """Metni bir vektöre (sayı listesi) çevirir."""
    return ollama.embed(model=MODEL, input=metin)["embeddings"][0]


def kosinus_benzerlik(a, b):
    """İki vektörün kosinüs benzerliği (1'e yakın = aynı yön/anlam, 0 = alakasız)."""
    nokta = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return nokta / (na * nb)


if __name__ == "__main__":
    cumleler = [
        "Kalp krizi acil tıbbi müdahale gerektirir.",
        "Miyokard enfarktüsü hayatı tehdit eden bir durumdur.",   # aynı anlam, farklı kelimeler
        "Otomobilin motoru bozuldu, tamirciye götürdüm.",         # alakasız
        "BRAF geni melanom kanserinde önemli rol oynar.",         # farklı konu (genetik)
    ]
    print("Cümleler vektöre çevriliyor...\n")
    vektorler = [embed(c) for c in cumleler]
    print(f"Her vektörün boyutu: {len(vektorler[0])} sayı\n")

    # Sorgu İNGİLİZCE — çapraz dil eşleştirmeyi de görelim
    sorgu = "heart attack emergency"
    sorgu_v = embed(sorgu)
    print(f"Sorgu (İngilizce): {sorgu!r}\n")
    print("Benzerlikler (yüksek = daha alakalı):")
    skorlar = [(kosinus_benzerlik(sorgu_v, v), c) for v, c in zip(vektorler, cumleler)]
    for skor, c in sorted(skorlar, reverse=True):
        print(f"  {skor:.3f}  {c}")
