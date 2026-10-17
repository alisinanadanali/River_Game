# Yol Haritası (ROADMAP)

Her faz, kabul kriterlerinin tümü sağlanınca kapanır. İş akışı her fazda aynıdır:
**belge → kural kimlikli test → kod** (CLAUDE.md).

## Faz 0 — Motor + testler

**Kapsam**
- `pyproject.toml` (uv, Python 3.12): numpy, pyyaml, pydantic v2, pytest, hypothesis.
- `engine/config.py`: pydantic şeması, profil derin birleştirme, `config_hash`.
- `engine/rng.py`: R-01 akışları, R-02 blokları.
- `engine/world.py`: M-01 … M-05 (perkolasyon, özellikler, 0-1 BFS, alt-seed ile yeniden üretim).
- `engine/water.py`: W-01 … W-07. `engine/donkey.py`, `engine/shrek.py`, `engine/items.py`: D-, S-, I- kuralları.
- `engine/step.py`: TICK.md'nin 12 adımı; `engine/events.py`: EVENTS.md kataloğu; `engine/observe.py`: V0 tam gözlem.
- `tools/tactical_cli.py`: metin tabanlı taktik mod (ASCII harita, iki oyuncu sırayla eylem girer).
- `tools/design_calcs.py`: MODEL Ek A hesaplarını motorun kendi fonksiyonlarıyla yeniden üretir.
- `tools/ghosting_test.py`: CONTROLS.md §6 (pygame-ce; motorla bağı yok).

**Kabul kriterleri**
- MODEL.md'deki her kural kimliği için `tests/rules/test_<ID>_*.py` var ve geçiyor.
- INV-01 … INV-08 hypothesis ile (≥ 200 seed × 300 tick, rastgele eylemler) geçiyor.
- INV-02: aynı seed + eylemler → aynı olay JSONL'i (bayt düzeyinde).
- `tools/design_calcs.py` çıktısı MODEL Ek A tablolarıyla istatistiksel tolerans içinde uyumlu.
- Metin taktik modda tam bir oyun (300 tick) oynanabiliyor.
- Hız: tek çekirdekte ≥ 5 000 tick/sn (RL için alt sınır; ölçülmezse yerinde güncellemeye geçiş değerlendirilir).
- Ghosting testi tablosu (CONTROLS.md §6) doldurulmuş ve varsayılan Shrek düzeni seçilmiş.

## Faz 1 — V0 oynanabilir

**Kapsam**
- `render/` (pygame-ce): VISUALS.md Kademe 1 (3/4 eğik, renk + desen skalası, HUD, belirsizlik halkası, dalga
  göstergesi, F1 hata ayıklama katmanı).
- `controllers/keyboard.py`: scancode eşlemesi, girdi tamponu, basılı tutma, taktik onay.
- `main.py`: gerçek zamanlı döngü (60 FPS, tick interpolasyonu), F2 taktik mod, F5 yeniden başlat, oyun sonu ekranı (skor).

**Kabul kriterleri**
- İki oyuncu aynı klavyede 3 dakikalık oyunu baştan sona oynayabiliyor; üç yetenek çalışıyor.
- Türkçe karakter testi (ğ ş ı İ ç ö ü) ekranda doğru.
- Renk skalası deuteranopi/protanopi simülasyonunda ayırt edilebilir (desenler dahil).
- 60 FPS'te kare düşmesi yok (9×9 harita).
- **İlk oyun testi**: ≥ 5 oyun, her profil ≥ 1 kez. Not alınacaklar: skor, can kaybı, "anlaşılmayan an"lar.
  Sonuçlarla parametre ayarı yapılır, değişiklikler config ve MODEL Ek A'ya işlenir.

## Faz 1.5 — Görsel cila ve ses

**Kapsam:** VISUALS.md §8 (tileset, yük ikonları, juice, ses).
**Kabul kriterleri:** işlevsel okunabilirlik kaybı yok (Faz 1 renk/desen testleri yeniden geçer); ikinci oyun
testi yapıldı.

## Faz 2 — Replay, olay logları, Uyum raporu

**Kapsam:** `logs/` (replay yazma/okuma, JSONL, başlık doğrulama), replay oynatıcı (hız kontrolü, tick tick
ilerleme), METRICS.md U-01 … U-07, kritik an karşı-olgusal analizi.
**Kabul kriterleri:**
- Kayıtlı her oyun bit düzeyinde yeniden oynatılıyor; uyumsuz başlık açık hata veriyor.
- Uyum raporu oyun sonunda gösteriliyor ve kayıtlı loglardan sonradan da üretilebiliyor.
- Kritik an analizi bir test senaryosunda (elle kurulmuş harita + eylem dizisi) beklenen sayıyı veriyor.

## Faz 3 — Betik botlar ve planlama

**Kapsam:** `controllers/bots/`: A* eşek (taş grafı, maliyet = beklenen derinlik riski), kural tabanlı Shrek
(eşeğin önündeki boşluğa kaya, dalgaya karşı baraj, eşeğe en yakın satıra atış). Küçük haritada (ör. 4×4,
ayrıklaştırılmış su) değer iterasyonu.
**Kabul kriterleri:** bot–bot oyunları her profilde çalışıyor; bot skorları oturum metrikleri olarak raporlanıyor
(dengeleme taban çizgisi); değer iterasyonu politikası mini haritada A*'dan iyi ya da eşit.

## Faz 4 — RL

**Kapsam:** `envs/`: Gymnasium (tek ajan: eşek, Shrek betik bot) ve PettingZoo (iki ajan) sarmalayıcıları;
tablolu Q-learning (mini harita), stable-baselines3 ile PPO eşek, MAPPO.
**Kabul kriterleri:**
- Sarmalayıcılar `gymnasium.utils.env_checker` ve PettingZoo API testinden geçiyor.
- Q-learning mini haritada değer iterasyonu politikasına yakınsıyor.
- PPO eşek, betik Shrek ile A* eşekten yüksek ortalama skor alıyor (ya da neden almadığı raporlanıyor).
- MAPPO deneyi, sabit seed kümesinde betik bot çiftiyle karşılaştırmalı raporlanıyor.

## Faz 5 — V1

- Bilgi asimetrisi: iki görünüm (`observe` rol bazlı kısmi gözlem; Shrek yukarı akışı, eşek sertlik ve dengeyi görür).
- Gizli su rejimleri (sakin / kabaran / taşkın; HMM) ve rejim çıkarımı.
- Mancınık adayı (ADR-004'te ertelendi).
- İnsan replay'lerinden davranış klonlanmış yapay partner.
- Tavlama benzetimi / GA ile oyun dengeleme (METRICS.md §5 hedefi).
- Shrek'in kıyı kuyruğundan yük seçmesi (V0'da FIFO).

## Kapsam dışı (şimdilik)

Ağ / iki cihaz, karakter sprite'ları, gamepad (mimari hazır), menü sistemi süslemeleri.

## Dizin yapısı (hedef)

```
River_Game/
├── CLAUDE.md
├── pyproject.toml          # Faz 0
├── docs/                   # bu belgeler
├── config/                 # default.yaml + profiles/
├── engine/                 # saf Python + numpy (ADR-005)
├── controllers/            # keyboard, bots/, rl policy — act(observation) -> action
├── render/                 # pygame-ce
├── logs/                   # replay + olay JSONL + metrikler
├── envs/                   # Gymnasium + PettingZoo
├── tools/                  # tactical_cli, design_calcs, ghosting_test
├── assets/fonts/           # Noto Sans (OFL)
└── tests/
    ├── rules/              # test_<KURAL>_*.py
    └── invariants/         # hypothesis
```
