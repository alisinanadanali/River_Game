# Biçimsel Model (MODEL)

Bu belge oyunun matematiksel tanımıdır. Her kural bir **kural kimliği** taşır. Her kimliğin `tests/rules/`
altında en az bir testi olur (`test_<KİMLİK>_<açıklama>.py`, ör. `test_W05_dam_release_volume.py`).
Sıralama TICK.md'de, olaylar EVENTS.md'de, parametreler `config/default.yaml`'da tanımlıdır.
Sembollerin config karşılıkları her kuralın altında `config:` satırıyla verilir.

Önekler: **M** harita · **W** su · **D** eşek · **S** Shrek · **I** yük · **R** rastgelelik.

---

## 1. Markov oyunu

Oyun, iki ajanlı, ortak ödüllü (tam işbirlikçi) stokastik bir oyundur: ⟨S, A_D, A_S, T, R, O_D, O_S, γ⟩.

- **S (durum):** `GameState` (ENTITIES.md). Değişmez `World` ve dinamik kısım. Durum uzayı sürekli bileşenler
  (B, dalga konumları, Q, yüzen yük konumları) içerdiği için tablolu yöntemlerde ayrıklaştırma ya da küçük
  harita gerekir (ROADMAP Faz 3–4).
- **A_D (eşek eylemleri):** `{NOOP, MOVE_N, MOVE_S, MOVE_E, MOVE_W, STANCE_LEFT, STANCE_RIGHT}`, 7 ayrık eylem.
- **A_S (Shrek eylemleri):** çok-ayrık üçlü `(move, aim, ability)`:
  `move ∈ {NONE, W, E}`, `aim ∈ {NONE, UP, DOWN}`, `ability ∈ {NONE, THROW, ROCK, DAM}`, toplam 3·3·4 = 36
  bileşik eylem. Düz (flatten) kodlama RL sarmalayıcısında yapılır.
- **T (geçiş):** `step(state, actions, rngs) -> (state', rngs', events)`. Saf ve deterministik (ADR-005, ADR-011).
  Rastgelelik yalnızca beş RNG akışından gelir (R-01).
- **R (ödül):** olaylardan türetilir (ADR-009). Varsayılan takım ödülü `r_t = Σ ItemDelivered.points`.
  Şekillendirme şablonları METRICS.md §4'te.
- **O (gözlem):** `observe(state, role) -> Observation` (`engine/observe.py`, ENTITIES.md Observation). V0'da
  iki rol aynı şeyi görür: durumun tamamı, **geleceği ele veren iki alan dışında**:
  - `world.seed`: beş akış seed'den türer (R-01) ve eylemler akışlara dokunmaz (R-02). Seed'i bilen bir ajan
    gelecekteki bütün dalgaları, yük varışlarını, atış inişlerini ve kaymaları önceden hesaplayabilirdi.
  - `projectiles[].landing`: atış anında çekilen iniş noktası (S-04) mermi inene kadar gizlidir (VISUALS §5:
    gölge hedef hücrede durur). İnişin sonucu adım 4'ün olaylarında görünür (`ItemCaught`, `ItemMissed`, …).

  RNG akışları zaten durumun parçası değildir (ADR-011). Gizli olmayan her alan gözlemde aynen durur; bunu,
  gözlemden ve gizli değerlerden durumu geri kuran test denetler. Gözlem kopya yapmaz: alt nesneler durumla
  paylaşılır ve diziler salt okunurdur. Arayüz V1'de kısmi gözleme (Shrek yukarı akışı, eşek taş sertliğini ve
  dengesini görür) değişmeden genişler: rol bazlı görünümler daha çok alanı gizler, imza aynı kalır.
  Bilinen sınır: harita seed'in bir fonksiyonudur; 2³² seed üzerinde kaba kuvvet araması seed'i haritadan
  bulabilir. Gözlem bunu doğrudan vermez; ajanların böyle bir arama yapmadığı varsayılır.
- **γ:** RL tarafında seçilir; süre sınırlı (T = 300 tick) bölümler için γ = 1 de geçerlidir.

Bölüm sonu: `t = game_length_ticks` (`TIME`) ya da `lives = 0` (`LIVES`). Skor = Σ teslim puanı; kalan can
skora eklenmez.

---

## 2. Harita (M)

**M-01 Izgara ve kıyılar.** R × C hücre. Satır −1 güney kıyısı, satır R kuzey kıyısı; kıyılar tüm sütunlarda
yürünebilir ve KURU'dur. Eşeğin hareket grafı: kıyı hücreleri ∪ taş hücreleri (kalıcı ya da geçici), 4-komşuluk.
config: `map.rows`, `map.cols`

**M-02 Site perkolasyonu.** Her nehir hücresi bağımsız olarak p olasılığıyla taştır: `is_stone ~ Bernoulli(p)`.
Çekiliş biçimi (ortak rastgele sayılar): bir üretim denemesi `rng_world`'den `WORLD_LAYERS × R × C` uniform
çeker (`WORLD_LAYERS = 3`: taş, yükseklik, yosun katmanı; `engine/world.py`). `is_stone = U_taş < p`. Her
hücre, taş olsun olmasın, kendi üç sayısını alır. Böylece aynı seed'de p büyüdükçe yalnız taş **eklenir**
(monoton eşleme) ve var olan taşların h ve yosun değerleri değişmez; profiller arası karşılaştırma ve
dengeleme (METRICS §5) aynı haritanın varyantları üzerinde yapılır.
config: `map.stone_density`

**M-03 Taş özellikleri.** Her taş için `h_i ~ U[h_lo, h_hi]` (`h_lo + (h_hi − h_lo)·U_yük`),
`mossy_i ~ Bernoulli(p_moss)` (`U_yosun < p_moss`); `k_i = k_moss` (yosunluysa) ya da `k_normal`.
Kayma çarpanı `μ_i = mossy_slip_multiplier` (yosunlu) ya da 1. Su hücrelerinde h ve k tanımsızdır ve `NaN`
tutulur (0 cm geçerli bir yükseklik olduğu için 0 yazmak hatayı gizlerdi); `mossy` yanlıştır.
config: `map.stone_base_h_cm`, `map.mossy_prob`, `map.stiffness_kg_per_cm`, `map.mossy_stiffness_kg_per_cm`, `map.mossy_slip_multiplier`

**M-04 Çözülebilirlik (0-1 BFS).** Güney kıyısından kuzey kıyısına, taş hücresine giriş maliyeti 0, su
hücresine giriş maliyeti 1 olan en kısa yolun maliyeti `n_rock` = geçiş için gereken en az geçici taş sayısı.
Su seviyesi ve zaman hesaba katılmaz (topolojik ölçü). Profil koşulu:
- `path_guarantee: none` → koşul yok;
- `path_guarantee: path` → `n_rock = 0`;
- `path_guarantee: max_rocks` → `n_rock ≤ max_rocks_to_solve`.
config: `map.path_guarantee`, `map.max_rocks_to_solve`

**M-05 Yeniden üretim.** Deneme i (i = 0, 1, … `max_regen_attempts − 1`), `rng_world`'ün i'inci ardışık
bloğunu (M-02) kullanır: deneme i, akıştan i blok çekildikten sonraki bloğu görür. Koşulu (M-04) sağlayan ilk
deneme haritayı verir (`World.regen_attempt = i`); `new_game` dönen `rngs.world`'ü i + 1 blok ilerlemiş
olarak döndürür. Hiçbir deneme koşulu sağlamazsa config bu seed için geçersiz sayılır (`MapGenerationError`).
Aynı seed her zaman aynı denemeyi seçer, determinizm korunur. (2026-10-20: "SeedSequence.spawn alt akışı"
yerine ardışık bloklar seçildi; `rng_world` ADR-011 gereği bir `StreamState` değeridir.)
config: `map.max_regen_attempts`

---

## 3. Su (W)

**W-01 Taban seviyesi (Ornstein–Uhlenbeck, AR(1)).**
`B(t+1) = B(t) + θ(μ − B(t)) + σ·ε_t`, ε_t ~ N(0,1). `B(0) = μ`. ε_t, σ = 0 olsa da her tick çekilir (R-02, INV-03).
Durağan dağılım: N(μ, σ²/(1 − (1 − θ)²)). Varsayılanla std ≈ 6,4 cm, ilişki süresi 1/θ ≈ 12,5 tick.
config: `water.ou_theta_per_tick`, `water.ou_mu_cm`, `water.ou_sigma_cm`

**W-02 Dalga varışı (Poisson).** Her tick `N_t ~ Poisson(λ)` dalga doğar; genlik `A ~ Üstel(ortalama ā)`.
Doğuş konumu `x = −k_spawn · s` (profil haritaya yumuşakça girer). N_t her tick çekilir; genlikler N_t adet üstel
çekilişle aynı çağrıda alınır. (numpy, λ = 0'da Poisson için sayı tüketmez; çekiliş miktarı yine yalnız
config'e ve akışa bağlıdır, eyleme bağlı değildir — INV-03'ün istediği budur.) Dalga kimlikleri doğuş sırasıyla artar (`Water.next_wave_id`),
baraj dalgaları (W-05) da aynı sayacı kullanır.
config: `water.wave_rate_per_tick`, `water.wave_amp_mean_cm`, `water.wave_spawn_offset_widths`

**W-03 Yürüyen dalga profili.** `x_k(t+1) = x_k(t) + v`.
`W(c,t) = Σ_k A_k · exp(−(c − x_k(t))² / 2s²)`. Profil sütuna bağlıdır, satırdan bağımsızdır (bütün sütun
birlikte yükselir). `x_k > (C − 1) + k_cull·s` olan dalga silinir ve `WaveExited` yayılır.
Dalga hacmi: `V_k = A_k · s · √(2π)` [cm·sütun].
config: `water.wave_speed_cols_per_tick`, `water.wave_width_cols`, `water.wave_cull_offset_widths`

**W-04 Baraj birikimi.** Baraj tutulduğu her tick (S-08):
- `c > c_d` sütunlarında seviye `drop` kadar düşer (W-07);
- `Q(t+1) = Q(t) + q_in`, `q_in = drop · v` (türetilir; config'de ayrı anahtar yoktur).
Fiziksel yorum: baraj, akış hızıyla gelen `drop` yüksekliğindeki su şeridini tutar. Varsayılan q_in = 5 cm·sütun/tick.
config: `dam.downstream_drop_cm`, `water.wave_speed_cols_per_tick`

**W-05 Baraj salınımı ve patlama.** Baraj bırakıldığında ya da `Q ≥ Q_max` olduğunda (patlama, `burst`)
`x = c_d` konumunda yeni bir dalga doğar: `A = Q / (s·√(2π))`, `origin = DAM`. Ardından Q = 0 ve bölüm
sayaçları (`accumulated_volume`, `absorbed_volume`, `held_ticks`) sıfırlanır. Elle bırakma TICK adım 2(a)'da
(dalga aynı tick adım 5'te ilerler), patlama adım 5(e)'de olur (dalga bu tick ilerlemez). İkisinde de
`DamReleased` ve ardından `WaveSpawned(origin=DAM)` yayılır. `held_ticks` = bölümde birikim (W-04) yapılan tick sayısı. Patlama, birikim
ya da emilim Q'yu Q_max'a ulaştırdığı tick'te olur ve Q kırpılmadan olduğu gibi salınır. Q_max bir sınır değil,
tetikleyicidir; hacim kaybolmaz. Patlamadan sonra Shrek'in yeniden baraj kurması için DAM'i bir tick bırakması gerekir.
Korunum: bir baraj bölümünde `salınan hacim = Σ q_in + Σ emilen V_k` (α = 1 sabit; ayarlanabilir değildir).
Varsayılanla 10 tick tutmak A ≈ 13 cm (≈ ortalama dalga), patlama (30 tick) A ≈ 40 cm verir.
config: `dam.q_max_cm_cols`

**W-06 Dalga emilimi.** Baraj aktifken merkezi `c_d`'yi geçen (`x_k(t) < c_d ≤ x_k(t+1)`) her dalga silinir,
hacmi Q'ya eklenir (`WaveAbsorbed`). Baraj aktifken `c > c_d` sütunlarına yalnızca merkezi `x_k ≥ c_d` olan (emilmemiş)
dalgalar katkı verir; batıdaki dalgaların doğu kuyrukları kesilir. Sınır: tam `c_d` üzerindeki merkez doğuya
sayılır (emilim koşulu `c_d ≤ x_k(t+1)` ile aynı taraf).
config: —

**W-07 Sütun seviyesi.**
`L(c,t) = B(t) + W_eff(c,t) − drop · 1[baraj aktif ∧ c > c_d]`.
`W_eff`, W-06'daki kesmeyi uygulanmış W'dir. V0 basitleştirmesi: barajın batısında seviye yükselmez.
config: —

*(V1 adayı)* Gizli rejimler (sakin / kabaran / taşkın) θ, σ, λ, ā'yı bir Markov zinciriyle değiştirir (HMM).

---

## 4. Eşek (D)

**D-01 Etkin taş yüksekliği.** Eşek i taşının üzerindeyken
`e_i = h_i + r_i(t) − (m_D + M_bag) / k_i`. Geçici taşta `h_i + r_i` yerine taşın anlık yüksekliği `h(t)`,
`k_i` yerine `rock_stiffness_kg_per_cm` kullanılır; geçici taşta ayrı bir r_i yoktur (kaya doğrudan h'ye eklenir,
S-07). `M_bag` iki heybenin toplam kütlesidir. Eşek **taşsız** bir nehir hücresindeyse (altındaki geçici taş
kayboldu ya da yavaş hareketin hedefi kayboldu, D-05) e tanımsızdır ve durum SWEPT olur (D-04).
Eşek üzerinde değilken renk skalası, eşeğin **o anki** yüküyle hesaplanan tahmini `e_i`'yi kullanır (VISUALS.md).
Örnek: 260 kg / 50 kg/cm = 5,2 cm; 320 kg / 25 kg/cm (yosunlu) = 12,8 cm çökme.
config: `donkey.mass_kg`, `map.stiffness_kg_per_cm`, `shrek.rock_stiffness_kg_per_cm`

**D-02 Denge.** `δ = (m_R − m_L) / (m_R + m_L + m_D)`, δ ∈ (−1, 1). Ağır taraf: δ > 0 sağ, δ < 0 sol,
δ = 0 → `rng_slip` ile yazı-tura (R-02).
config: `donkey.mass_kg`

**D-03 Kayma (yalnızca hareket başlangıcında).** `p_slip = min(1, p₀ + κ·δ²·μ_i)`, μ_i ayrılınan taşın kayma
çarpanı: yosunlu kalıcı taşta `mossy_slip_multiplier`, öteki kalıcı taşlarda ve geçici taşta 1 (2026-10-23
kararı). Denetim yalnız bir **taştan** ayrılırken ve heybelerde en az bir yük varken yapılır; kıyıdan çıkarken
kayma yoktur (p = 0; formüldeki p₀ kıyıya uygulanmaz). Kayma `u_slip[0] < p_slip` ile olur; δ = 0 ise taraf
`u_slip[1] < 0,5` → sol, aksi hâlde sağ. Kayınca ağır taraftaki **en üst** yük düşer
(`DonkeySlipped`, `ItemDropped(cause=slip)`); hareket yine gerçekleşir. Düşen yük ayrılınan hücreye düşer (I-04).
Örnek: 50 kg dengesizlik → δ = 0,20 → p = 0,09; yosunlu taşta 0,13.
config: `donkey.slip_base_prob`, `donkey.slip_kappa`

**D-04 Derinlik durumları.** `d = L(c, t) − e_i`.
| d | Durum |
|---|---|
| d < d₀ | DRY |
| d₀ ≤ d < d₁ | ANKLE |
| d₁ ≤ d < d₂ | KNEE |
| d ≥ d₂ | SWEPT |
Kıyıda d tanımsızdır (`depth = None`; skaler `NaN` dataclass eşitliğini bozardı, `nan != nan`), durum DRY'dır. Eşek taşsız bir nehir hücresindeyse (altındaki geçici taş
kayboldu, S-07, ya da yavaş hareketin hedefi kayboldu, D-05) durum doğrudan SWEPT olur
(`DonkeySwept(cause=stone_vanished)`, `depth_cm = null`). Durum DRY/ANKLE/KNEE arasında değişince
`DonkeyDepthChanged` yayılır; SWEPT için `DonkeySwept` yayılır, `DonkeyDepthChanged` yayılmaz.
config: `donkey.depth_ankle_cm` (d₀), `donkey.depth_knee_cm` (d₁), `donkey.depth_swept_cm` (d₂)

**D-05 Hareket.** Hedef hücre graf içindeyse (M-01) hareket geçerlidir; değilse eylem no-op olur
(`ActionRejected`). Hareket başlarken eşeğin durumu DRY ise hareket aynı tick'te tamamlanır. ANKLE ya da
KNEE ise `slow_move_ticks` tick sürer: hareket başlatılır, sonraki tick'lerde eşeğin girdisi yok sayılır ve son
tick'te eşek hedefe geçer. Hareket sürerken eşek çıkış hücresindedir (derinlik oradan hesaplanır).
`slow_move_ticks = 1` ise hareket anında tamamlanır. Hedef varış tick'inde yeniden denetlenmez: hedefteki geçici
taş bu arada kaybolduysa eşek yine geçer ve adım 7'de SWEPT olur (2026-10-23 kararı; zamanlama hatası can
götürür). Eşek oyuna güney kıyısında, `⌊C/2⌋` sütununda başlar (Shrek'le aynı sütun, S-06 teslimi ilk tick'ten
mümkün; 2026-10-23 kararı). *(Netleştirme: prompt yalnız BİLEK için yavaşlama tanımlıyordu; DİZ'de daha hızlı
olmak tutarsız olacağından DİZ'e de uygulanır.)*
config: `donkey.slow_move_ticks`

**D-06 Diz kaybı.** Durum KNEE iken her tick `knee_drop_prob` olasılıkla (`u_slip[2] < knee_drop_prob`)
ağır taraftaki en üst yük düşer (`ItemDropped(cause=knee)`); δ = 0 ise taraf `u_slip[3] < 0,5` → sol. Heybeler
boşsa etkisizdir.
config: `donkey.knee_drop_prob`

**D-07 Sürüklenme ve yeniden doğuş.** Durum SWEPT olduğunda: heybelerdeki tüm yükler eşeğin hücresine düşer
(`cause=swept`), can 1 azalır (`DonkeySwept`, `LifeLost`), eşek aynı sütunda başlangıç kıyısında **anında**
yeniden doğar (`DonkeyRespawned`); duruş ve süren hareket iptal olur; dokunulmazlık yoktur. Can 0 olursa
eşek yine kıyıya konur ama `DonkeyRespawned` yayılmaz; `GameOver(reason=lives)`. Olay sırası: `DonkeySwept`,
düşen her yük için (kimlik sırasıyla) `ItemDropped` + I-04 olayları, `LifeLost`, varsa `DonkeyStance(NONE, swept)`,
`DonkeyRespawned`, gerekiyorsa `GameOver`.
config: `time.lives`, `donkey.respawn_delay_ticks` (V0'da 0; ileride gecikme için ayrıldı)

**D-08 Yakalama duruşu.** `STANCE_LEFT/RIGHT` eylemi `stance` ve `stance_since = t` değerlerini atar. Duruş şu
durumlarda biter: eşek hareket eylemi verirse, sürüklenirse, ya da `t − stance_since ≥ stance_max_ticks` olursa.
Duruş ancak **alındığı tick'ten sonraki** tick'lerde yakalama sağlar (`t > stance_since`). Yani yük iniş
anında eşek en az bir tick önce durmuş olmalıdır. NOOP duruşu bozmaz; aynı ya da öteki tarafa yeni bir duruş
`stance_since`'i yeniler. Süre adım 11'de, `t` artmadan önce denetlenir: t₀'da alınan duruş t₀ + 1 … t₀ +
`stance_max_ticks` tick'lerinde yakalama sağlar. Duruş kıyıda da alınabilir; uçuşta yakalama yalnız nehirde
(S-05), teslim yalnız güney kıyısında (S-06) olur, kuzey kıyıda duruşun etkisi yoktur.
config: `donkey.stance_max_ticks`

**D-09 Heybeler.** İki LIFO yığın. Bir yük, seçilen tarafa ancak `mass + m ≤ bag_max_kg_per_side` ve
`volume + v ≤ bag_max_volume_per_side` ise girer. Kapasite hiçbir koşulda aşılmaz (değişmez).
config: `donkey.bag_max_kg_per_side`, `donkey.bag_max_volume_per_side`

**D-10 Teslimat.** Eşek kuzey kıyısındayken (r = R) her tick heybedeki tüm yükler, kimlik sırasıyla,
`DELIVERED` olur, puanlar skora eklenir. Tuş gerekmez.
config: `items.types.*.points`

---

## 5. Shrek (S)

**S-01 Kıyıda yürüme.** `move = W/E` sütunu ±1 değiştirir, [0, C−1] aralığına sessizce kırpılır; yalnız değişince
`ShrekMoved`. Bu tick baraj tutuluyorsa (S-03) yürüme yok sayılır. Shrek oyuna `⌊C/2⌋` sütununda başlar
(2026-10-23 kararı; türetilir, config anahtarı yoktur).

**S-02 Nişan.** `aim = UP/DOWN` `aim_row`'u ±1 değiştirir, [0, R−1] aralığına sessizce kırpılır; yalnız değişince
`ShrekAimed`. Nişan hücresi her zaman `(aim_row, shrek.col)`. Nişan, aynı tick'teki yetenekten önce uygulanır.
Başlangıçta `aim_row = 0` (Shrek'e en yakın satır).

**S-03 Yetenek dışlaması ve cooldown.** Bir tick'te en çok bir yetenek (eylemin tek bir `ability` bileşeni
vardır). "Bu tick baraj tutuluyor" = `ability = DAM` ve `burst_lock` yok; o zaman yürüme geçersizdir. THROW ya da
ROCK gelmesi barajı bırakır (S-08), yani "bırak ve at" tek tick'tir; bırakılan tick'te yürüme de serbesttir
(TICK adım 2a; 2026-10-23 netleştirmesi). Cooldown'ı sıfırdan büyük bir yetenek ya da koşulu sağlanmayan bir
yetenek no-op olur ve cooldown harcamaz (`ActionRejected`; önce cooldown, sonra koşul denetlenir). Koşullar:
THROW için kuyruk boş olmamalı; ROCK için hedef bir su hücresiyse geçici taş sınırı dolu olmamalı. Kullanılan
yetenek cooldown'ı `n` yapar; adım 11'de 1 azalır, yani `n` tick sonra yeniden kullanılabilir (`n = 0` ise her
tick).
config: `shrek.throw_cooldown_ticks`, `shrek.rock_cooldown_ticks`

**S-04 Fırlatma (atış).** Kuyruğun başındaki yük, nişan hücresine doğru atılır. Uçuş süresi `throw_flight_ticks`.
İniş noktası atış anında çekilir: `landing = target + σ·(z₁, z₂)`, z ~ N(0, I₂) (`rng_throw`),
`σ = σ₀ + σ₁·(aim_row + 1) + σ₂·m`. Burada `aim_row + 1` Shrek'e satır cinsinden uzaklıktır, m yükün kütlesi.
`z₁` satıra, `z₂` sütuna eklenir (`u_throw[0]`, `u_throw[1]`). Hedef, bu tick'in yürüme ve nişanından sonraki
`(aim_row, col)`'dur. Mermi atıldığı tick'in adım 4'ünde ilerlemez (dalgalardaki gibi): `throw_flight_ticks = 2`
ile t'de atılan yük t + 2'de iner (TICK zamanlama örneği).
config: `shrek.throw_flight_ticks`, `shrek.throw_sigma0_cells`, `shrek.throw_sigma_per_row_cells`, `shrek.throw_sigma_per_kg_cells`

**S-05 İniş çözümü.** Bir mermi indiğinde (`ticks_left = 0`):
1. Eşek nehirde, D-08'e göre geçerli duruştaysa ve `‖landing − (r_D, c_D)‖₂ ≤ r_catch` ise:
   seçilen heybeye sığıyorsa `ItemCaught(source=flight)`; sığmıyorsa `ItemBounced` ve yük eşeğin hücresinde suya düşer.
2. Aksi hâlde `ItemMissed`. İniş hücresi `round(landing)`:
   - satır < 0 (güney kıyısı) → yük kuyruğun sonuna döner (`ItemReturnedToBank`; kuyruk doluysa `LOST(bank_overflow)`);
   - satır > R − 1 ya da sütun ızgara dışında → `LOST(off_map)`;
   - aksi hâlde yük o hücrede suya düşer (I-04), konumu `(satır, x = iniş sütunu)` (sürekli). Taş hücresine düşen
     yük de kayarak suya düşer.

`ItemMissed.reason` ilk tutan koşuldur: eşek nehirde değil → `donkey_on_bank`; duruş yok → `no_stance`;
`t ≤ stance_since` → `stance_too_late`; aksi hâlde `out_of_radius`.
Yuvarlama: `round(x) = ⌊x + 0,5⌋` (yarım yukarı). Python ve numpy'nin "bankacı yuvarlaması" (`round(2,5) = 2`)
kullanılmaz; böylece güney kıyısı ölçütü ENTITIES'teki "satır < −0,5" ile aynıdır.
config: `shrek.catch_radius_cells`

**S-06 Kıyıda teslim (handoff).** THROW anında eşek güney kıyısında, Shrek'le aynı sütunda ve duruştaysa
(D-08'in "bir tick önce" koşulu burada aranmaz) atış gürültüsüz bir teslime dönüşür: mermi `kind = HANDOFF`,
uçuş `bank_load_ticks`. İnişte eşek hâlâ aynı yerde ve duruştaysa yük seçilen heybeye girer
(`ItemCaught(source=handoff)`, `miss_distance = 0`). Eşek ayrılmışsa ya da heybe sığmıyorsa yük kuyruğun sonuna
döner (`ItemReturnedToBank(cause=handoff_cancelled)`). Normal cooldown uygulanır. Teslimin hedefi `(−1, col)`,
σ = 0'dır; `u_throw` kullanılmaz (yine çekilir, R-02).
config: `shrek.bank_load_ticks`

**S-07 Kaya at.** Nişan hücresine gürültüsüz bir kaya atılır (uçuş yok; etkisi aynı tick'te).
- Su hücresi: `rock_max_active` sınırı dolu değilse yeni geçici taş doğar, `h = rock_initial_h_cm`. Sınır doluysa
  no-op olur, cooldown harcanmaz. Sınır yalnız doğuşu kısıtlar; var olan bir taşı yükseltmek sınır doluyken de
  geçerlidir.
- Kalıcı taş: `r_i += rock_raise_cm`; r_i her tick `rock_raise_decay_cm_per_tick` azalır, alt sınır 0.
- Geçici taş: yüksekliğine doğrudan `rock_raise_cm` eklenir (tazeleme).
Geçici taş her tick (doğduğu tick dahil, adım 6) `rock_sink_cm_per_tick` batar; `h < rock_vanish_h_cm` olunca
kaybolur. Böylece varsayılanla taş 25 tick'in sonunda var olur (Ek A.6). Kaybolduğu anda eşek üzerindeyse eşek
sürüklenir (D-04). r_i'nin sönümü de aynı tick başlar. Geçici taş kimlikleri `Stones.next_temp_id` sayacından
gelir.
config: `shrek.rock_*`

**S-08 Baraj (kanalize).** `ability = DAM` olan her tick baraj aktiftir. Aktif değilken DAM gelirse baraj
başlar (`DamStarted`, `c_d = shrek.col`). Aktifken DAM dışında bir yetenek ya da NONE gelirse baraj bırakılır
(`DamReleased(reason=manual)`, W-05). Baraj aktifken Shrek yürüyemez ve atış yapamaz; nişan değişebilir.
Patlamadan sonra (`reason=burst`) `burst_lock` kurulur: DAM dışında bir eylem gelene kadar DAM yok sayılır.
Böylece basılı tutulan tuş barajı hemen yeniden kurmaz.
config: `dam.*`

---

## 6. Yükler (I)

**I-01 Varış.** Her tick `N_t ~ Poisson(λ_items)` yük doğar; türü `types.*.prob` dağılımından çekilir
(`rng_items`). Çekiliş biçimi W-02 ile aynıdır: tek çağrıda N_t ve N_t uniform `U_j`; tür, türlerin **ada göre
sıralı** listesinde birikimli olasılığı `U_j`'yi ilk aşan türdür (ters CDF). Sıralı ad, YAML'daki yazım sırasından
bağımsızdır; `config_hash` da anahtarları sıraladığı için aynı hash'li iki config aynı yükleri üretir. Yük
kimliği doğuş sırasıdır ve `GameState.items` içindeki konumuna eşittir (yükler silinmez, ayrı sayaç gerekmez).
config: `items.arrival_rate_per_tick`, `items.types.*.prob`

**I-02 Kıyı kuyruğu.** FIFO, kapasite `bank_capacity`. Doluyken doğan yük `LOST(bank_overflow)` olur
(kuyruk sistemi: M/D/1/K benzeri kayıplı kuyruk): önce `ItemArrived`, sonra `ItemLost(origin=null)`.
config: `items.bank_capacity`

**I-03 Yaşam döngüsü.** ENTITIES.md'deki durum makinesi. Her yük her tick tam olarak bir durumdadır;
DELIVERED ve LOST soğurucudur.

**I-04 Suya düşme ve yüzme.** `(r, x)` konumunda suya düşen yük: `floats = true` ise `FLOATING` olur, konumu
`(r, x)`'tir; değilse `ItemSank` ve `LOST(sank)` olur. Yüzen yük her tick `x += flow_speed` ile doğuya
sürüklenir; `x > C − 0,5` olunca `LOST(drifted_off)` olur. Satır değişmez. Heybeden düşen yük (D-03, D-06,
D-07, S-05 sekme) eşeğin hücresinde, `x = c` ile suya düşer.
config: `water.flow_speed_cols_per_tick`, `items.types.*.floats`

**I-05 Yüzen yükü yakalama.** Eşek `(r, round(x))` hücresindeyse, D-08'e göre geçerli duruştaysa ve yük
seçilen heybeye sığıyorsa `ItemCaught(source=floating, miss_distance = |x − c|)`. Sığmıyorsa yakalama denenmez
(sekme yok). Aynı tick'te birden çok uygun yük varsa kimlik sırasıyla sığdığı kadar yakalanır.

---

## 7. Rastgelelik (R)

**R-01 Akışlar.** Ana seed'den `SeedSequence(seed).spawn(5)` ile beş bağımsız akış türetilir:
`rng_world` (M-02, M-03, M-05), `rng_water` (W-01, W-02), `rng_items` (I-01), `rng_throw` (S-04),
`rng_slip` (D-02 yazı-tura, D-03, D-06). Bir akış yalnız kendi süreçleri için kullanılır.
`spawn` sırası sabittir ve replay uyumluluğunun parçasıdır: 0 `world`, 1 `water`, 2 `items`, 3 `throw`, 4 `slip`.
Üreteç PCG64'tür; akış durumu değişmez bir değerdir ve çekiliş yeni bir değer döndürür (ADR-011, `engine/rng.py`).

**R-02 Sabit çekiliş blokları (ortak rastgele sayılar).** Oyuncu eylemine bağlı akışlar her tick, kullanılsın
ya da kullanılmasın, sabit sayıda sayı çeker:
- `rng_throw`: tick başına 2 standart normal (o tick atış varsa kullanılır);
- `rng_slip`: tick başına 4 uniform (kayma, kayma tarafı, diz kaybı, diz tarafı).
`rng_world` yalnız `new_game` içinde, deneme başına `WORLD_LAYERS × R × C` uniform çeker (M-02, M-05).
`rng_water` her tick 1 normal + 1 Poisson + N_t üstel çeker; bu sayı eylemlerden bağımsızdır (baraj emilimi
çekiliş yapmaz). Böylece iki farklı strateji aynı tick'te aynı rastgele sayıları görür. Bu, karşı-olgusal
analizi (METRICS.md "kritik an") ve adil strateji karşılaştırmasını mümkün kılar. Blok boyutları model
yapısının parçasıdır; adlandırılmış modül sabitleridir (`THROW_BLOCK = 2`, `SLIP_BLOCK = 4`) ve config hash'ine
motor sürümü üzerinden girer.

---

## 8. Değişmezler (tests/invariants, hypothesis)

| Kimlik | Değişmez |
|---|---|
| INV-01 | Yük korunumu: doğan = ON_BANK + IN_FLIGHT + IN_BAG + FLOATING + DELIVERED + LOST (her tick, her seed) |
| INV-02 | Determinizm: aynı seed + aynı eylem dizisi → bit düzeyinde aynı durum ve olay akışı |
| INV-03 | Akış bağımsızlığı: atış/kayma eylemlerini değiştirmek B(t) ve dalga doğuş dizisini değiştirmez |
| INV-04 | Baraj korunumu: her bölümde salınan hacim = Σ q_in + Σ emilen hacim |
| INV-05 | Kapasite: heybe kütle/hacim sınırı hiçbir tick'te aşılmaz |
| INV-06 | Can: yalnızca `DonkeySwept` olan tick'te ve tam olarak 1 azalır |
| INV-07 | Bağımlılık sınırı: `engine/` yalnızca standart kütüphane (`random`/`time`/`datetime` hariç), numpy, pydantic, pyyaml ve kendisini import eder (statik test, ADR-005) |
| INV-08 | Geçici taş sayısı ≤ `rock_max_active`; tick sonunda 0 ≤ Q < Q_max |

---

## 9. Config doğrulaması (ADR-008, `engine/config.py`)

Doğrulama profil derin birleştirmesinden **sonra** yapılır; profil tek başına eksik bir config'tir. Tek alan
aralıkları `config/default.yaml` yorumlarındadır. Alanlar arası kurallar (`tests/engine/test_config_cross.py`):

| Kural | Kaynak |
|---|---|
| `path_guarantee = max_rocks` ise `max_rocks_to_solve ≤ shrek.rock_max_active` (aksi hâlde garanti edilen harita tek geçişte çözülemez) | M-04, MODEL A.6 |
| `depth_ankle_cm < depth_knee_cm < depth_swept_cm` | D-04 |
| `stone_base_h_cm = [lo, hi]` ile `lo ≤ hi` | M-03 |
| `items.types.*.prob` toplamı 1 (mutlak tolerans `PROB_SUM_ABS_TOL = 1e-9`) | I-01 |
| Her Shrek düzeni için `donkey ∪ shrek_<düzen> ∪ global` içinde bir scancode iki eyleme bağlanamaz | CONTROLS.md §1–§3 |

Yapısal sabitler (config'te değil, `engine/config.py` modül sabiti): `CONFIG_VERSION = 1` (şemanın okuduğu
`meta.config_version`), `SDL_NUM_SCANCODES = 512` (geçerli scancode 0…511), `PROB_SUM_ABS_TOL = 1e-9`.

---

## Ek A — Tasarım hesapları (Monte Carlo, 2026-10-17)

Yöntem: numpy ile bellek içi simülasyon. Perkolasyon için 20 000 harita; su için 120 000 tick'lik tek yörünge
ve rastgele (taş, tick) örnekleri; eşek yüklü (200 + 60 kg). Sonuçlar ilk oyun testinde yeniden doğrulanacak.
Faz 0'da bu hesaplar `tools/design_calcs.py` olarak motorun kendisiyle tekrarlanır.

### A.1 Perkolasyon (9×9, güney → kuzey, 4-komşu)

| p | P(kayasız yol) | min. kaya = 0 / 1 / 2 / 3 / ≥4 | Ort. en kısa yol (adım) |
|---|---|---|---|
| 0,45 | 0,085 | — | 12,5 |
| 0,50 | 0,193 | 0,18 / 0,43 / 0,30 / 0,07 / 0,00 | 12,5 |
| 0,55 | 0,353 | — | 12,3 |
| 0,58 | 0,482 | 0,48 / 0,41 / 0,10 / 0,01 / 0,00 | 12,1 |
| 0,62 | 0,641 | 0,64 / 0,32 / 0,04 / 0,00 / 0,00 | 11,8 |
| 0,70 | 0,894 | 0,90 / 0,10 / 0,00 / 0,00 / 0,00 | 11,1 |

Sonuç: p_c ≈ 0,593 sonsuz ızgara değeridir; 9×9'da geçiş yumuşaktır. p = 0,50 "imkânsız" değildir (%19 yol
var). Profiller bu yüzden kaya sayısıyla tanımlanır (M-04).

### A.2 Su ve derinlik

| Set | Boş taş su altında | Normal taş, yüklü: KURU / BİLEK / DİZ / SÜRÜKLENME | Yosunlu: SÜRÜKLENME |
|---|---|---|---|
| Prompt (σ=1,5, λ=0,02, h∈[5,25]) | %5 | 0,86 / 0,11 / 0,02 / 0,009 | 0,015 |
| **Seçilen (σ=2,5, λ=0,03, h∈[0,20])** | **%21** | **0,61 / 0,24 / 0,115 / 0,032** | **0,058** |

Seçilen setle oyun başına ≈ 9 dalga gelir; P(A > 20 cm) ≈ 0,19. Dalgaları yok sayan bir eşek oyun başına
1–2 can kaybeder.

### A.3 Atış yakalama olasılığı (2B izotrop Gauss, P = 1 − exp(−r²/2σ²))

Seçilen: σ₀ = 0,2, σ₁ = 0,05/satır, σ₂ = 0,004/kg, r = 0,75. Prompt değerleri (σ₁ = 0,1, r = 0,5) satır 5'te
karpuz için %14 veriyordu.

| Uzaklık (satır) | Elma 10 kg | Patates 30 kg | Karpuz 50 kg |
|---|---|---|---|
| 1 | 0,96 | 0,87 | 0,75 |
| 3 | 0,84 | 0,72 | 0,61 |
| 5 | 0,69 | 0,58 | 0,49 |
| 7 | 0,55 | 0,47 | 0,39 |
| 9 | 0,45 | 0,38 | 0,32 |

### A.4 Kayma (κ = 2, p₀ = 0,01)

| Dengesizlik | δ | p_slip | Yosunlu | 12 adımda ≥ 1 kayma |
|---|---|---|---|---|
| 10 kg | 0,048 | 0,015 | 0,024 | 0,16 |
| 50 kg | 0,200 | 0,090 | 0,250 | 0,68 |
| 60 kg | 0,231 | 0,117 | 0,330 | 0,77 |

### A.5 Yük ekonomisi

Yük başına ortalama 24 kg, 1,7 hacim, 2,6 puan; oyun başına ≈ 30 yük (≈ 78 puan potansiyel). Tek yön ≈ 12 adım,
tur ≈ 25–30 tick → tur başına ≈ 3 yük gelir. Heybe kapasitesi (2 × 60 kg, 2 × 4 hacim ≈ 4–5 yük) yeterlidir;
kıyı ancak Shrek uzun süre barajla meşgulken taşar.

### A.6 Kaya ömrü

Geçici taş 20 cm'de doğar, 1 cm/tick batar, −5 cm'de kaybolur: ömür 25 tick. Yüklü eşek altında KURU kalma
süresi ≈ 15 tick (motor 14 verir: taş doğduğu tick de batar; `tests/rules/test_S07_matches_appendix_A6.py`). Prompt'taki 20 tick'lik cooldown ile iki geçici taş yalnızca 5 tick birlikte var olabilir. Bu
yüzden varsayılan cooldown **15** tick'tir (10 tick örtüşme). `hard` profilinde ≤ 3 kaya gereken haritalar
için `rock_max_active = 3` ve cooldown 12'dir.
