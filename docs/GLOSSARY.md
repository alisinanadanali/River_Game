# Sözlük (GLOSSARY)

Kod İngilizce, arayüz Türkçe (ADR-007). Bu tablo iki dil arasındaki tek köprüdür: yeni bir terim önce buraya
eklenir, sonra kodda ve arayüzde kullanılır. Birim sütunu ADR-008'e uyar: yükseklik **cm**, kütle **kg**, zaman **tick**.

## Roller ve varlıklar

| Türkçe (arayüz) | İngilizce (kod) | Tanım | Birim |
|---|---|---|---|
| Shrek | `shrek` | Başlangıç kıyısında yürüyen, fırlatan, kaya atan, baraj tutan rol | — |
| Eşek | `donkey` | Taşlar üzerinde yük taşıyan rol | — |
| Heybe (sol/sağ) | `bag` (`left` / `right`) | Eşeğin iki yanındaki yük yığını (LIFO) | kg, hacim birimi |
| Yük | `item` | Taşınan nesne; türü `apple_crate`, `potato_sack`, `watermelon` | — |
| Elma kasası | `apple_crate` | 10 kg, hacim 1, 1 puan, yüzer | — |
| Patates çuvalı | `potato_sack` | 30 kg, hacim 2, 3 puan, batar | — |
| Karpuz | `watermelon` | 50 kg, hacim 3, 6 puan, yüzer | — |
| Başlangıç kıyısı | `south_bank` | Güney kıyı; Shrek'in yürüdüğü, eşeğin yeniden doğduğu yer (satır −1) | — |
| Karşı kıyı | `north_bank` | Kuzey kıyı; teslimat yeri (satır R) | — |
| Kıyı kuyruğu | `bank_queue` | Shrek'in yanında bekleyen yükler (FIFO, kapasiteli) | adet |
| Taş | `stone` | Kalıcı basamak hücresi | — |
| Geçici taş | `temp_stone` | Kaya at ile oluşan, batan taş | — |
| Yosunlu taş | `mossy` | Düşük sertlik, yüksek kayma çarpanı olan taş | — |
| Mermi | `projectile` | Uçuştaki yük | — |
| Dalga | `wave` | Batıdan doğuya yürüyen Gauss su kabarması | cm |
| Baraj | `dam` | Shrek'in kanalize yeteneği | — |
| Dünya | `world` | Seed'den üretilen değişmez harita | — |
| Oyun durumu | `GameState` | Bir tick'teki tüm değişken durum | — |
| Gözlem | `Observation` | Bir rolün bir tick'te gördüğü durum: `observe(state, role)`; seed ve iniş noktaları gizli | — |

## Eylemler

| Türkçe | İngilizce | Tanım |
|---|---|---|
| Hareket (K/G/D/B) | `MOVE_N` / `MOVE_S` / `MOVE_E` / `MOVE_W` | Eşeğin 4-komşu adımı |
| Yakalama duruşu (sol/sağ) | `STANCE_LEFT` / `STANCE_RIGHT` | Seçilen heybeye yakalamaya hazırlanma |
| Bekle | `NOOP` | Hiçbir şey yapma |
| Kıyıda yürü | `shrek_move` (`W` / `E`) | Shrek'in sütun değiştirmesi |
| Nişan | `aim` (`UP` / `DOWN`) | Shrek'in hedef satırı |
| Fırlat | `THROW` | Kıyı kuyruğunun önündeki yükü atma |
| Kaya at | `ROCK` | Nişan hücresine geçici taş atma |
| Baraj | `DAM` | Bu tick barajı tut (basılı tutma) |
| Kıyıda teslim | `handoff` | Eşek kıyıdayken risksiz yükleme |

## Su ve harita kavramları

| Türkçe | İngilizce | Sembol | Tanım | Birim |
|---|---|---|---|---|
| Taban seviyesi | `base_level` | B(t) | OU sürecindeki ortak su seviyesi | cm |
| Dalga katkısı | `wave_level` | W(c,t) | Sütundaki dalgaların toplamı | cm |
| Su seviyesi | `water_level` | L(c,t) | B + W − baraj etkisi | cm |
| Taban yüksekliği | `base_h` | h_i | Taşın yüksüz yüksekliği | cm |
| Geçici yükselti | `raise_h` | r_i(t) | Kaya at ile eklenen, sönen yükselti | cm |
| Sertlik | `stiffness` | k_i | Taşın yük altında çökme direnci | kg/cm |
| Etkin yükseklik | `effective_h` | e_i | Eşek üzerindeyken taşın yüksekliği | cm |
| Derinlik | `depth` | d | L − e; pozitifse eşek suda | cm |
| Güvenlik payı | `margin` | e − L = −d | Renk skalasının girdisi | cm |
| Baraj hacmi | `dam_volume` | Q | Barajın arkasında biriken su | cm·sütun |
| Dalga hacmi | `wave_volume` | A·s·√(2π) | Bir Gauss dalgasının integrali | cm·sütun |
| Taş yoğunluğu | `stone_density` | p | Perkolasyon parametresi | olasılık |
| Kritik eşik | `p_c` | ≈ 0,593 | Sonsuz kare ızgara site perkolasyon eşiği | — |
| Çözülebilirlik | `rocks_to_solve` | n_rock | Geçiş için gereken en az geçici taş sayısı | adet |
| Taşkın / patlama | `burst` | — | Q, Q_max'a ulaşınca baraj kendiliğinden salınır | — |

## Eşek durumları

| Türkçe | İngilizce | Koşul |
|---|---|---|
| KURU | `DRY` | d < 0 |
| BİLEK | `ANKLE` | 0 ≤ d < d₁ |
| DİZ | `KNEE` | d₁ ≤ d < d₂ |
| SÜRÜKLENME | `SWEPT` | d ≥ d₂ |
| Oyun bitti | `GAME_OVER` | can = 0 |
| Denge | `balance` (δ) | (m_sağ − m_sol)/(m_sağ + m_sol + m_eşek) |
| Kayma | `slip` | Hareket anında ağır taraftan yük düşmesi |

## Yük durumları

| Türkçe | İngilizce |
|---|---|
| Kıyıda | `ON_BANK` |
| Havada | `IN_FLIGHT` |
| Heybede | `IN_BAG` |
| Yüzüyor | `FLOATING` |
| Teslim edildi | `DELIVERED` |
| Kayıp | `LOST` |

## Ölçüm ve altyapı

| Türkçe | İngilizce | Tanım |
|---|---|---|
| Takım skoru | `team_score` | Teslim edilen puanların toplamı |
| Uyum raporu | `harmony_report` | Oyun sonu co-op göstergeleri (METRICS.md) |
| Kritik an | `critical_moment` | Shrek'in eylemi olmasa sürüklenmenin olacağı an |
| Olay | `event` | Motorun bir tick'te yaydığı kayıt (EVENTS.md) |
| Tekrar | `replay` | seed + eylem dizisi |
| Taktik mod | `tactical_mode` | Her tick iki oyuncunun hamlesini bekleyen mod |
| Girdi tamponu | `KeyBuffer` | Bir tick penceresinin basışları ve basılı tuşlar (CONTROLS §4) |
| Basış | `press` (`KeyDown`) | Tuşun bırakılmış durumdan basılıya geçişi (CONTROLS §4.1) |
| Basılı tutma tekrarı | `hold repeat` | Penceredeki basış yoksa basılı hareket/nişan tuşunun eylemi |
| Seçim (taktik) | `selection` | Shrek'in onaylanmamış `move`/`aim` tercihi (CONTROLS §5.2) |
| Onay (taktik) | `confirm` | Rolün o tick'teki eylemini kesinleştiren basış (CONTROLS §5.2) |
| Hata ayıklama katmanı | `debug_overlay` | F1 ile açılan sayısal katman |
| RNG akışı | `rng stream` | `rng_world`, `rng_water`, `rng_items`, `rng_throw`, `rng_slip` |
| Kural kimliği | `rule id` | MODEL.md'deki M-, W-, D-, S-, I-, R- önekli kimlik |
| Zorluk profili | `profile` | `warmup`, `percolation_edge`, `hard` |

## Görsel ve animasyon (VISUALS §9)

| Türkçe | İngilizce | Tanım | Birim |
|---|---|---|---|
| Kukla animasyonu | `puppet animation` | Kesik bir resme her karede kodla dönüşüm uygulayarak hareket verme | — |
| Poz | `pose` | Bir karakterin tek resmi: `idle`, `throw`, `dam`, `happy` | — |
| Klip | `Clip` | Bir pozun zamana bağlı dönüşümü (`IDLE`, `HOP`, `THROW`, …); döngü ya da tek seferlik | s |
| Dönüşüm | `Transform` | Kayma, ölçek, dönme, saydamlık; `pose(klip, t, config)`'in sonucu | px, oran, derece |
| Ayak noktası | `anchor` | Resmin taşa oturan noktası, resim boyutuna oranla (x, y) | oran |
| Hayalet | `ghost` | Sürüklenen eşeğin eski hücresinde kayıp solan görüntüsü | — |
| Soyut şekil | `fallback shape` | Resim yokken çizilen şekil (VISUALS §9.4) | px |
| Animasyon yöneticisi | `Animator` | Olaylardan ve durumdan karakter başına klip seçen durum makinesi | — |
