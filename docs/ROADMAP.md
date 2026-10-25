# Yol Haritası (ROADMAP)

Her faz, kabul kriterlerinin tümü sağlanınca kapanır. İş akışı her fazda aynıdır:
**belge → kural kimlikli test → kod** (CLAUDE.md).

## Faz 0 — Motor + testler

**Durum: kapandı, `v0.1.0` (2026-10-24).** Kabul kanıtları, etiketteki koddan yeniden üretilebilir:

| Kriter | Nasıl doğrulanır | Sonuç (v0.1.0) |
|---|---|---|
| Her kural kimliğinin testi | `tests/test_rule_coverage.py` (MODEL.md'den okur) | 37/37 |
| INV-01 … INV-08, ≥ 200 seed × 300 tick | `uv run pytest --hypothesis-profile=full` | geçti |
| INV-02 bayt düzeyinde | `tests/invariants/test_INV02_*` (alt süreç + `PYTHONHASHSEED` dahil) | geçti |
| Ek A ile uyum | `uv run python -m tools.design_calcs` | 96/96 |
| Taktik modda tam oyun | `tests/tools/test_tactical.py` (belgedeki komut, 300 tick) | geçti |
| ≥ 5 000 tick/sn | `uv run python -m tools.bench`, `uv run pytest -m perf` | ≈ 7 600 (ADR-011) |
| Ghosting tablosu | CONTROLS.md §6 | dolduruldu, varsayılan düzen |

Sürüm tek yerde tutulur: `pyproject.toml` `version`; motor onu `engine.ENGINE_VERSION` olarak taşır (log
başlığı, EVENTS.md) ve bir test ikisinin eşitliğini korur. Bu etiketten sonra olay kataloğundaki her değişiklik
`EVENT_SCHEMA_VERSION`'ı artırır (EVENTS.md).

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
  Ölçüm: `uv run python -m tools.bench` (varsayılan config, sabit seed'li rastgele eylemler, 5 tekrarın en iyisi;
  `--stages` TICK.md adımı başına süre verir). Koruma: `uv run pytest -m perf` (makine yüküne duyarlı olduğu için
  varsayılan test koşusunda yoktur; push'tan önce koşulur). Sonuçlar ADR-011'de.
- Ghosting testi tablosu (CONTROLS.md §6) doldurulmuş ve varsayılan Shrek düzeni seçilmiş.

## Faz 1 — V0 oynanabilir

**Kapsam**
- `render/` (pygame-ce): VISUALS.md Kademe 1 (3/4 eğik, renk + desen skalası, HUD, belirsizlik halkası, dalga
  göstergesi, F1 hata ayıklama katmanı). Karakterler (VISUALS §9, `render/characters/`) Faz 1'in başında,
  önizleme aracıyla (`tools/character_preview.py`) birlikte yapıldı.
- `controllers/keyboard.py`: scancode eşlemesi, girdi tamponu, basılı tutma, taktik onay.
- `main.py`: gerçek zamanlı döngü (60 FPS, tick interpolasyonu), F2 taktik mod, F5 yeniden başlat, oyun sonu ekranı (skor).

**Kabul kriterleri**
- İki oyuncu aynı klavyede 3 dakikalık oyunu baştan sona oynayabiliyor; üç yetenek çalışıyor.
- Türkçe karakter testi (ğ ş ı İ ç ö ü) ekranda doğru (`tests/render/test_fonts.py`, VISUALS §7).
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

Ağ / iki cihaz, gamepad (mimari hazır), menü sistemi süslemeleri, karakter resimlerinin dağıtımı.

Karakterler kapsamdadır ama **yereldir**: Shrek ve Eşek, git'e girmeyen `assets/private/` resimleriyle çizilir
(VISUALS §9, ADR-012); resim yoksa VISUALS §9.4'teki soyut şekle düşülür. Depo ve sürümler resim içermez.

## Dizin yapısı (hedef)

```
River_Game/
├── CLAUDE.md
├── pyproject.toml          # Faz 0
├── docs/                   # bu belgeler
├── config/                 # default.yaml + profiles/
├── engine/                 # saf Python + numpy (ADR-005)
├── controllers/            # keyboard, bots/, rl policy — act(observation) -> action
├── render/                 # pygame-ce; characters/ (VISUALS §9)
├── logs/                   # replay + olay JSONL + metrikler
├── envs/                   # Gymnasium + PettingZoo
├── tools/                  # tactical_cli, design_calcs, ghosting_test, bench, character_preview
├── assets/fonts/           # Noto Sans (OFL)
├── assets/private/         # yerel karakter resimleri; .gitignore, git'e asla girmez (ADR-012)
└── tests/
    ├── rules/              # test_<KURAL>_*.py
    └── invariants/         # hypothesis
```
