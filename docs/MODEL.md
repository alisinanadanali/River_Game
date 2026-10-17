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
- **T (geçiş):** `step(state, actions, rngs) -> (state', events)`. Saf ve deterministik (ADR-005).
  Rastgelelik yalnızca beş RNG akışından gelir (R-01).
- **R (ödül):** olaylardan türetilir (ADR-009). Varsayılan takım ödülü `r_t = Σ ItemDelivered.points`.
  Şekillendirme şablonları METRICS.md §4'te.
- **O (gözlem):** `observe(state, role)`. V0'da iki rol için de tam gözlem; arayüz V1'de kısmi gözleme
  (Shrek yukarı akışı, eşek taş sertliğini ve dengesini görür) değişmeden genişler.
- **γ:** RL tarafında seçilir; süre sınırlı (T = 300 tick) bölümler için γ = 1 de geçerlidir.

Bölüm sonu: `t = game_length_ticks` (`TIME`) ya da `lives = 0` (`LIVES`). Skor = Σ teslim puanı; kalan can
skora eklenmez.

---

## 2. Harita (M)

**M-01 Izgara ve kıyılar.** R × C hücre. Satır −1 güney kıyısı, satır R kuzey kıyısı; kıyılar tüm sütunlarda
yürünebilir ve KURU'dur. Eşeğin hareket grafı: kıyı hücreleri ∪ taş hücreleri (kalıcı ya da geçici), 4-komşuluk.
config: `map.rows`, `map.cols`

**M-02 Site perkolasyonu.** Her nehir hücresi bağımsız olarak p olasılığıyla taştır: `is_stone ~ Bernoulli(p)`.
config: `map.stone_density`

**M-03 Taş özellikleri.** Her taş için `h_i ~ U[h_lo, h_hi]`, `mossy_i ~ Bernoulli(p_moss)`;
`k_i = k_moss` (yosunluysa) ya da `k_normal`. Kayma çarpanı `μ_i = mossy_slip_multiplier` (yosunlu) ya da 1.
config: `map.stone_base_h_cm`, `map.mossy_prob`, `map.stiffness_kg_per_cm`, `map.mossy_stiffness_kg_per_cm`, `map.mossy_slip_multiplier`

**M-04 Çözülebilirlik (0-1 BFS).** Güney kıyısından kuzey kıyısına, taş hücresine giriş maliyeti 0, su
hücresine giriş maliyeti 1 olan en kısa yolun maliyeti `n_rock` = geçiş için gereken en az geçici taş sayısı.
Su seviyesi ve zaman hesaba katılmaz (topolojik ölçü). Profil koşulu:
- `path_guarantee: none` → koşul yok;
- `path_guarantee: path` → `n_rock = 0`;
- `path_guarantee: max_rocks` → `n_rock ≤ max_rocks_to_solve`.
config: `map.path_guarantee`, `map.max_rocks_to_solve`

**M-05 Yeniden üretim.** Koşul sağlanmazsa harita `rng_world`'ün i'inci alt akışıyla (SeedSequence.spawn)
yeniden üretilir; i = 0, 1, … `max_regen_attempts − 1`. Aşılırsa config geçersiz sayılır (hata). Aynı seed
her zaman aynı denemeyi seçer, determinizm korunur.
config: `map.max_regen_attempts`

---

## 3. Su (W)

**W-01 Taban seviyesi (Ornstein–Uhlenbeck, AR(1)).**
`B(t+1) = B(t) + θ(μ − B(t)) + σ·ε_t`, ε_t ~ N(0,1). `B(0) = μ`.
Durağan dağılım: N(μ, σ²/(1 − (1 − θ)²)). Varsayılanla std ≈ 6,4 cm, ilişki süresi 1/θ ≈ 12,5 tick.
config: `water.ou_theta_per_tick`, `water.ou_mu_cm`, `water.ou_sigma_cm`

**W-02 Dalga varışı (Poisson).** Her tick `N_t ~ Poisson(λ)` dalga doğar; genlik `A ~ Üstel(ortalama ā)`.
Doğuş konumu `x = −k_spawn · s` (profil haritaya yumuşakça girer).
config: `water.wave_rate_per_tick`, `water.wave_amp_mean_cm`, `water.wave_spawn_offset_widths`

**W-03 Yürüyen dalga profili.** `x_k(t+1) = x_k(t) + v`.
`W(c,t) = Σ_k A_k · exp(−(c − x_k(t))² / 2s²)`. Profil sütuna bağlıdır, satırdan bağımsızdır (bütün sütun
birlikte yükselir). `x_k > (C − 1) + k_cull·s` olan dalga silinir.
Dalga hacmi: `V_k = A_k · s · √(2π)` [cm·sütun].
config: `water.wave_speed_cols_per_tick`, `water.wave_width_cols`, `water.wave_cull_offset_widths`

**W-04 Baraj birikimi.** Baraj tutulduğu her tick (S-08):
- `c > c_d` sütunlarında seviye `drop` kadar düşer (W-07);
- `Q(t+1) = Q(t) + q_in`, `q_in = drop · v` (türetilir; config'de ayrı anahtar yoktur).
Fiziksel yorum: baraj, akış hızıyla gelen `drop` yüksekliğindeki su şeridini tutar. Varsayılan q_in = 5 cm·sütun/tick.
config: `dam.downstream_drop_cm`, `water.wave_speed_cols_per_tick`

**W-05 Baraj salınımı ve patlama.** Baraj bırakıldığında ya da `Q ≥ Q_max` olduğunda (patlama, `burst`)
`c_d` konumunda yeni bir dalga doğar: `A = Q / (s·√(2π))`, `origin = DAM`. Ardından Q = 0. Patlama, birikim
ya da emilim Q'yu Q_max'a ulaştırdığı tick'te olur ve Q kırpılmadan olduğu gibi salınır. Q_max bir sınır değil,
tetikleyicidir; hacim kaybolmaz. Patlamadan sonra Shrek'in yeniden baraj kurması için DAM'i bir tick bırakması gerekir.
Korunum: bir baraj bölümünde `salınan hacim = Σ q_in + Σ emilen V_k` (α = 1 sabit; ayarlanabilir değildir).
Varsayılanla 10 tick tutmak A ≈ 13 cm (≈ ortalama dalga), patlama (30 tick) A ≈ 40 cm verir.
config: `dam.q_max_cm_cols`

**W-06 Dalga emilimi.** Baraj aktifken merkezi `c_d`'yi geçen (`x_k(t) < c_d ≤ x_k(t+1)`) her dalga silinir,
hacmi Q'ya eklenir (`WaveAbsorbed`). Baraj aktifken `c > c_d` sütunlarına yalnızca merkezi zaten `c_d`'nin
doğusunda olan dalgalar katkı verir; batıdaki dalgaların doğu kuyrukları kesilir.
config: —

**W-07 Sütun seviyesi.**
`L(c,t) = B(t) + W_eff(c,t) − drop · 1[baraj aktif ∧ c > c_d]`.
`W_eff`, W-06'daki kesmeyi uygulanmış W'dir. V0 basitleştirmesi: barajın batısında seviye yükselmez.
config: —

*(V1 adayı)* Gizli rejimler (sakin / kabaran / taşkın) θ, σ, λ, ā'yı bir Markov zinciriyle değiştirir (HMM).

---

## 4. Eşek (D)

**D-01 Etkin taş yüksekliği.** Eşek i taşının üzerindeyken
`e_i = h_i + r_i(t) − (m_D + M_bag) / k_i`. Geçici taşta `h_i + r_i` yerine taşın anlık yüksekliği kullanılır.
Eşek üzerinde değilken renk skalası, eşeğin **o anki** yüküyle hesaplanan tahmini `e_i`'yi kullanır (VISUALS.md).
Örnek: 260 kg / 50 kg/cm = 5,2 cm; 320 kg / 25 kg/cm (yosunlu) = 12,8 cm çökme.
config: `donkey.mass_kg`, `map.stiffness_kg_per_cm`, `shrek.rock_stiffness_kg_per_cm`

**D-02 Denge.** `δ = (m_R − m_L) / (m_R + m_L + m_D)`, δ ∈ (−1, 1). Ağır taraf: δ > 0 sağ, δ < 0 sol,
δ = 0 → `rng_slip` ile yazı-tura (R-02).
config: `donkey.mass_kg`

**D-03 Kayma (yalnızca hareket başlangıcında).** `p_slip = min(1, p₀ + κ·δ²·μ_i)`, μ_i ayrılınan taşın kayma
çarpanı (kıyıda μ = 0, yani kıyıdan çıkarken kayma yoktur). Kayınca ağır taraftaki **en üst** yük düşer
(`ItemDropped(cause=slip)`); hareket yine gerçekleşir. Düşen yük ayrılınan hücreye düşer (I-04).
Örnek: 50 kg dengesizlik → δ = 0,20 → p = 0,09; yosunlu taşta 0,13.
config: `donkey.slip_base_prob`, `donkey.slip_kappa`

**D-04 Derinlik durumları.** `d = L(c, t) − e_i`.
| d | Durum |
|---|---|
| d < d₀ | DRY |
| d₀ ≤ d < d₁ | ANKLE |
| d₁ ≤ d < d₂ | KNEE |
| d ≥ d₂ | SWEPT |
Kıyıda d tanımsızdır, durum DRY'dır. Eşeğin altındaki geçici taş kaybolursa (S-07) durum doğrudan SWEPT olur.
config: `donkey.depth_ankle_cm` (d₀), `donkey.depth_knee_cm` (d₁), `donkey.depth_swept_cm` (d₂)

**D-05 Hareket.** Hedef hücre graf içindeyse (M-01) hareket geçerlidir; değilse eylem no-op olur
(`ActionRejected`). Hareket başlarken eşeğin durumu DRY ise hareket aynı tick'te tamamlanır. ANKLE ya da
KNEE ise `slow_move_ticks` tick sürer: hareket başlatılır, sonraki tick'lerde eşeğin girdisi yok sayılır ve son
tick'te eşek hedefe geçer. *(Netleştirme: prompt yalnız BİLEK için yavaşlama tanımlıyordu; DİZ'de daha hızlı
olmak tutarsız olacağından DİZ'e de uygulanır.)*
config: `donkey.slow_move_ticks`

**D-06 Diz kaybı.** Durum KNEE iken her tick `knee_drop_prob` olasılıkla ağır taraftaki en üst yük düşer
(`ItemDropped(cause=knee)`); heybeler boşsa etkisizdir.
config: `donkey.knee_drop_prob`

**D-07 Sürüklenme ve yeniden doğuş.** Durum SWEPT olduğunda: heybelerdeki tüm yükler eşeğin hücresine düşer
(`cause=swept`), can 1 azalır (`DonkeySwept`, `LifeLost`), eşek aynı sütunda başlangıç kıyısında **anında**
yeniden doğar (`DonkeyRespawned`); duruş ve süren hareket iptal olur; dokunulmazlık yoktur. Can 0 olursa
`GameOver(reason=lives)`.
config: `time.lives`, `donkey.respawn_delay_ticks` (V0'da 0; ileride gecikme için ayrıldı)

**D-08 Yakalama duruşu.** `STANCE_LEFT/RIGHT` eylemi `stance` ve `stance_since = t` değerlerini atar. Duruş şu
durumlarda biter: eşek hareket eylemi verirse, sürüklenirse, ya da `t − stance_since ≥ stance_max_ticks` olursa.
Duruş ancak **alındığı tick'ten sonraki** tick'lerde yakalama sağlar (`t > stance_since`). Yani yük iniş
anında eşek en az bir tick önce durmuş olmalıdır. NOOP duruşu bozmaz; aynı ya da öteki tarafa yeni bir duruş
`stance_since`'i yeniler.
config: `donkey.stance_max_ticks`

**D-09 Heybeler.** İki LIFO yığın. Bir yük, seçilen tarafa ancak `mass + m ≤ bag_max_kg_per_side` ve
`volume + v ≤ bag_max_volume_per_side` ise girer. Kapasite hiçbir koşulda aşılmaz (değişmez).
config: `donkey.bag_max_kg_per_side`, `donkey.bag_max_volume_per_side`

**D-10 Teslimat.** Eşek kuzey kıyısındayken (r = R) her tick heybedeki tüm yükler `DELIVERED` olur, puanlar
skora eklenir. Tuş gerekmez.
config: `items.types.*.points`

---

## 5. Shrek (S)

**S-01 Kıyıda yürüme.** `move = W/E` sütunu ±1 değiştirir, [0, C−1] dışına çıkamaz. Baraj aktifken yürüme
yok sayılır.

**S-02 Nişan.** `aim = UP/DOWN` `aim_row`'u ±1 değiştirir, [0, R−1] aralığına kırpılır. Nişan hücresi her zaman
`(aim_row, shrek.col)`. Nişan, aynı tick'teki yetenekten önce uygulanır.

**S-03 Yetenek dışlaması ve cooldown.** Bir tick'te en çok bir yetenek. Baraj aktifken THROW ve ROCK geçersizdir.
Cooldown'ı sıfırdan büyük bir yetenek ya da koşulu sağlanmayan bir yetenek no-op olur ve cooldown harcamaz
(`ActionRejected`).
config: `shrek.throw_cooldown_ticks`, `shrek.rock_cooldown_ticks`

**S-04 Fırlatma (atış).** Kuyruğun başındaki yük, nişan hücresine doğru atılır. Uçuş süresi `throw_flight_ticks`.
İniş noktası atış anında çekilir: `landing = target + σ·(z₁, z₂)`, z ~ N(0, I₂) (`rng_throw`),
`σ = σ₀ + σ₁·(aim_row + 1) + σ₂·m`. Burada `aim_row + 1` Shrek'e satır cinsinden uzaklıktır.
config: `shrek.throw_flight_ticks`, `shrek.throw_sigma0_cells`, `shrek.throw_sigma_per_row_cells`, `shrek.throw_sigma_per_kg_cells`

**S-05 İniş çözümü.** Bir mermi indiğinde (`ticks_left = 0`):
1. Eşek nehirde, D-08'e göre geçerli duruştaysa ve `‖landing − (r_D, c_D)‖₂ ≤ r_catch` ise:
   seçilen heybeye sığıyorsa `ItemCaught(source=flight)`; sığmıyorsa `ItemBounced` ve yük eşeğin hücresinde suya düşer.
2. Aksi hâlde `ItemMissed`. İniş hücresi `round(landing)`:
   - satır < 0 (güney kıyısı) → yük kuyruğun sonuna döner (`ItemReturnedToBank`; kuyruk doluysa `LOST(bank_overflow)`);
   - satır > R − 1 ya da sütun ızgara dışında → `LOST(off_map)`;
   - aksi hâlde yük o hücrede suya düşer (I-04). Taş hücresine düşen yük de kayarak suya düşer.
config: `shrek.catch_radius_cells`

**S-06 Kıyıda teslim (handoff).** THROW anında eşek güney kıyısında, Shrek'le aynı sütunda ve duruştaysa
(D-08'in "bir tick önce" koşulu burada aranmaz) atış gürültüsüz bir teslime dönüşür: mermi `kind = HANDOFF`,
uçuş `bank_load_ticks`. İnişte eşek hâlâ aynı yerde ve duruştaysa yük seçilen heybeye girer
(`ItemCaught(source=handoff)`). Eşek ayrılmışsa ya da heybe sığmıyorsa yük kuyruğun sonuna döner. Normal
cooldown uygulanır.
config: `shrek.bank_load_ticks`

**S-07 Kaya at.** Nişan hücresine gürültüsüz bir kaya atılır (uçuş yok; etkisi aynı tick'te).
- Su hücresi: `rock_max_active` sınırı dolu değilse yeni geçici taş doğar, `h = rock_initial_h_cm`. Sınır doluysa
  no-op olur, cooldown harcanmaz.
- Kalıcı taş: `r_i += rock_raise_cm`; r_i her tick `rock_raise_decay_cm_per_tick` azalır, alt sınır 0.
- Geçici taş: yüksekliğine doğrudan `rock_raise_cm` eklenir (tazeleme).
Geçici taş her tick `rock_sink_cm_per_tick` batar; `h < rock_vanish_h_cm` olunca kaybolur. Kaybolduğu anda
eşek üzerindeyse eşek sürüklenir (D-04).
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
(`rng_items`).
config: `items.arrival_rate_per_tick`, `items.types.*.prob`

**I-02 Kıyı kuyruğu.** FIFO, kapasite `bank_capacity`. Doluyken doğan yük `LOST(bank_overflow)` olur
(kuyruk sistemi: M/D/1/K benzeri kayıplı kuyruk).
config: `items.bank_capacity`

**I-03 Yaşam döngüsü.** ENTITIES.md'deki durum makinesi. Her yük her tick tam olarak bir durumdadır;
DELIVERED ve LOST soğurucudur.

**I-04 Suya düşme ve yüzme.** `(r, x)` konumunda suya düşen yük: `floats = true` ise `FLOATING` olur, konumu
`(r, x)`'tir; değilse `ItemSank` ve `LOST(sank)` olur. Yüzen yük her tick `x += flow_speed` ile doğuya
sürüklenir; `x > C − 0,5` olunca `LOST(drifted_off)` olur. Satır değişmez.
config: `water.flow_speed_cols_per_tick`, `items.types.*.floats`

**I-05 Yüzen yükü yakalama.** Eşek `(r, round(x))` hücresindeyse, D-08'e göre geçerli duruştaysa ve yük
seçilen heybeye sığıyorsa `ItemCaught(source=floating)`. Sığmıyorsa yakalama denenmez (sekme yok). Aynı
tick'te birden çok uygun yük varsa kimlik sırasıyla sığdığı kadar yakalanır.

---

## 7. Rastgelelik (R)

**R-01 Akışlar.** Ana seed'den `SeedSequence(seed).spawn(5)` ile beş bağımsız akış türetilir:
`rng_world` (M-02, M-03, M-05), `rng_water` (W-01, W-02), `rng_items` (I-01), `rng_throw` (S-04),
`rng_slip` (D-02 yazı-tura, D-03, D-06). Bir akış yalnız kendi süreçleri için kullanılır.

**R-02 Sabit çekiliş blokları (ortak rastgele sayılar).** Oyuncu eylemine bağlı akışlar her tick, kullanılsın
ya da kullanılmasın, sabit sayıda sayı çeker:
- `rng_throw`: tick başına 2 standart normal (o tick atış varsa kullanılır);
- `rng_slip`: tick başına 4 uniform (kayma, kayma tarafı, diz kaybı, diz tarafı).
`rng_water` her tick 1 normal + 1 Poisson + N_t üstel çeker; bu sayı eylemlerden bağımsızdır (baraj emilimi
çekiliş yapmaz). Böylece iki farklı strateji aynı tick'te aynı rastgele sayıları görür. Bu, karşı-olgusal
analizi (METRICS.md "kritik an") ve adil strateji karşılaştırmasını mümkün kılar. Blok boyutları model
yapısının parçasıdır; adlandırılmış modül sabitleridir ve config hash'ine motor sürümü üzerinden girer.

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
| INV-07 | Bağımlılık sınırı: `engine/` dış katmanları import etmez (statik test) |
| INV-08 | Geçici taş sayısı ≤ `rock_max_active`; tick sonunda 0 ≤ Q < Q_max |

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
süresi ≈ 15 tick. Prompt'taki 20 tick'lik cooldown ile iki geçici taş yalnızca 5 tick birlikte var olabilir. Bu
yüzden varsayılan cooldown **15** tick'tir (10 tick örtüşme). `hard` profilinde ≤ 3 kaya gereken haritalar
için `rock_max_active = 3` ve cooldown 12'dir.
