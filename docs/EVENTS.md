# Olay Kataloğu (EVENTS)

Motor her tick bir olay listesi yayar (ADR-009). Olaylar değişmez kayıtlardır ve her biri şu ortak alanları taşır:
`t` (tick), `seq` (tick içindeki sıra), `type`. Olaylar JSONL'e satır başına bir olay olarak yazılır (ADR-010).
Olay adları ve alan adları İngilizcedir; arayüzde gösterilen metinler GLOSSARY.md üzerinden Türkçeleştirilir.

**Tüketiciler:** **R** render (animasyon, ses, ekran sarsıntısı) · **L** log/replay (hepsi) · **Ö** RL ödülü ·
**U** Uyum raporu ve metrikler (METRICS.md).

Bir olay eklemek ya da alan değiştirmek, log şema sürümünü (`event_schema_version`) artırır.

## Eylem ve rol olayları

| Olay | Alanlar | Adım | Tüketici |
|---|---|---|---|
| `ActionRejected` | `role`, `component`, `reason` (`cooldown`, `dam_active`, `queue_empty`, `rock_limit`, `no_stone`, `busy_moving`, `burst_lock`) | 1, 3 | L, U |
| `ShrekMoved` | `from_col`, `to_col` | 2 | R, L |
| `ShrekAimed` | `row` | 2 | R, L |
| `DonkeyMoveStarted` | `from`, `to`, `ticks` | 3 | R, L |
| `DonkeyMoved` | `from`, `to` | 3 | R, L, U |
| `DonkeySlipped` | `side`, `p_slip`, `delta`, `mossy` | 3 | R, L, U |
| `DonkeyStance` | `side` (`LEFT`/`RIGHT`/`NONE`), `reason` (`set`, `moved`, `expired`, `swept`) | 3, 7, 11 | R, L, U |

## Yük olayları

| Olay | Alanlar | Adım | Tüketici |
|---|---|---|---|
| `ItemArrived` | `item_id`, `kind`, `queue_len` | 9 | R, L, U |
| `ItemThrown` | `item_id`, `kind` (`THROW`/`HANDOFF`), `from_col`, `target`, `sigma`, `flight_ticks` | 2 | R, L, U |
| `ItemCaught` | `item_id`, `side`, `source` (`flight`/`handoff`/`floating`), `miss_distance` | 4, 8 | R, L, Ö, U |
| `ItemMissed` | `item_id`, `landing`, `miss_distance`, `reason` (`no_stance`, `stance_too_late`, `out_of_radius`, `donkey_on_bank`) | 4 | R, L, U |
| `ItemBounced` | `item_id`, `side` (heybe dolu) | 4 | R, L, U |
| `ItemReturnedToBank` | `item_id`, `cause` (`handoff_cancelled`, `landed_on_bank`) | 4 | R, L, U |
| `ItemDropped` | `item_id`, `side`, `cause` (`knee`/`slip`/`swept`) | 3, 7 | R, L, U |
| `ItemFloated` | `item_id`, `row`, `x` | 3, 4, 7 | R, L |
| `ItemSank` | `item_id`, `row`, `col` | 3, 4, 7 | R, L |
| `ItemLost` | `item_id`, `reason` (`bank_overflow`, `sank`, `drifted_off`, `off_map`), `origin` (son durum) | 3, 4, 7, 8, 9 | L, Ö, U |
| `ItemDelivered` | `item_id`, `kind`, `points` | 10 | R, L, Ö, U |

Not: batan bir yük için `ItemSank` ve hemen ardından `ItemLost(reason=sank)` yayılır. Sayımlar (korunum, kayıp
dağılımı) yalnızca `ItemLost`'u kullanır; `ItemSank` görsel/ses içindir.

## Eşek durumu olayları

| Olay | Alanlar | Adım | Tüketici |
|---|---|---|---|
| `DonkeyDepthChanged` | `old`, `new`, `depth_cm`, `row`, `col` | 7 | R, L, U |
| `DonkeySwept` | `row`, `col`, `depth_cm`, `cause` (`depth`/`stone_vanished`), `items_dropped` | 7 | R, L, Ö, U |
| `LifeLost` | `lives_left` | 7 | R, L, Ö, U |
| `DonkeyRespawned` | `col` | 7 | R, L |

## Taş, su ve baraj olayları

| Olay | Alanlar | Adım | Tüketici |
|---|---|---|---|
| `TempStoneSpawned` | `stone_id`, `row`, `col`, `h` | 2 | R, L, U |
| `TempStoneRaised` | `row`, `col`, `delta_cm`, `target` (`stone`/`temp_stone`) | 2 | R, L, U |
| `TempStoneVanished` | `stone_id`, `row`, `col`, `under_donkey` | 6 | R, L, U |
| `DamStarted` | `col` | 2 | R, L, U |
| `DamReleased` | `col`, `volume`, `amplitude`, `accumulated`, `absorbed`, `held_ticks`, `reason` (`manual`/`burst`) | 2, 5 | R, L, U |
| `WaveSpawned` | `wave_id`, `amplitude`, `x`, `origin` (`UPSTREAM`/`DAM`) | 5 | R, L, U |
| `WaveAbsorbed` | `wave_id`, `volume`, `dam_col` | 5 | R, L, U |

Dalga konumları olaylarda her tick yayılmaz; `WaveSpawned` + config (v) ile kinematik olarak yeniden
hesaplanabilir (dalgalar deterministik ilerler). Render konumu doğrudan durumdan okur.

## Oyun olayları

| Olay | Alanlar | Adım | Tüketici |
|---|---|---|---|
| `GameOver` | `reason` (`time`/`lives`), `score`, `t` | 7, 11 | R, L, Ö, U |

## Log başlığı (JSONL ilk satırı)

```json
{"type": "Header", "engine_version": "0.1.0", "event_schema_version": 1,
 "config_hash": "sha256:…", "profile": "percolation_edge", "seed": 42,
 "tactical_mode": false, "created_at": "2026-10-17T10:00:00Z"}
```

`config_hash`, pydantic ile doğrulanmış config'in kanonik JSON'unun SHA-256'sıdır (`engine/config.py`).
Kanonik JSON: `model_dump(mode="json", by_alias=True)`, anahtarlar sıralı, ayırıcılar `","` ve `":"` (boşluksuz),
UTF-8, NaN yasak. Biçim `"sha256:" + 64 küçük onaltılık hane`. Hash ham YAML'dan değil doğrulanmış modelden
alındığı için yorumlar, anahtar sırası ve `50` / `50.0` yazımı hash'i değiştirmez. Replay dosyası aynı başlığı
ve tick başına `{t, donkey_action, shrek_action}` satırlarını içerir (ADR-010).
