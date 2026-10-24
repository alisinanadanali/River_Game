# Nehir Geçidi (River Crossing)

İki kişilik, aynı klavyede oynanan bir işbirliği oyunu: Shrek kıyıda yürür, yük fırlatır, kaya atar ve barajla
dalgaları tutar; eşek taşların üzerinde yükleri karşı kıyıya taşır. Aynı motor hem insanlar hem RL ajanları
için yazılmıştır ve stokastik süreçleri (OU, Poisson, perkolasyon, Markov zincirleri) ve karar/öğrenme
algoritmalarını denemek için bir öğrenme alanıdır.

**Sürüm 0.1.0, Faz 0 (motor ve testler):** saf ve deterministik `step`, 37 kural, 8 değişmez, metin taktik mod.
Grafik oyun Faz 1'dedir (`docs/ROADMAP.md`).

## Başlangıç

```
uv sync
uv run pytest                                                   # testler (hızlı profil)
uv run python -m tools.tactical_cli --seed 42 --profile percolation_edge   # metin taktik modda oyna (? yardım)
uv run python -m tools.design_calcs --quick                     # MODEL.md Ek A'yı motorla yeniden hesapla
uv run python -m tools.bench --stages                           # hız
```

## Belgeler

Tasarım belgeleri Türkçedir, kod İngilizcedir (ADR-007). Başlangıç noktası `CLAUDE.md` (çalışma kuralları ve
belge haritası); kuralların biçimsel tanımı `docs/MODEL.md`, tick sırası `docs/TICK.md`, olaylar
`docs/EVENTS.md`, kararlar `docs/adr/`.
