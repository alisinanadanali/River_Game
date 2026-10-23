# Tick Boru Hattı (TICK)

`step(state, actions, rngs) -> (new_state, new_rngs, events)` (ADR-011) her çağrıda aşağıdaki 12 adımı **bu sırayla** uygular.
Sıra oyunun anlamını belirler. Değiştirmek bir ADR ve ilgili kural testlerinin güncellenmesini gerektirir.
Kural kimlikleri MODEL.md'dedir.

**Kodda:** `engine/step.py`. `PIPELINE` demeti bu 13 adımı (0 … 12) aynı sırayla tutar. Her aşama bir `Tick`
değeri alır ve yenisini döndürür. Aşamanın docstring'i `TICK.md step N:` ile başlar ve aşağıdaki özet tablonun
Kurallar sütununu birebir anar (`Rules: …`). `tests/engine/test_step.py` bu belgeyi okuyup ikisini karşılaştırır;
buradaki bir sıra ya da kural değişikliği kodda yapılmazsa test kırmızı olur.

## Özet

| # | Adım | Kurallar | RNG | Yayılan olaylar |
|---|---|---|---|---|
| 0 | RNG blokları çekilir | R-02 | `rng_throw`, `rng_slip` | — |
| 1 | Eylem doğrulama | S-03, D-05, S-08 | — | `ActionRejected` |
| 2 | Shrek eylemleri | S-01, S-02, S-04, S-06, S-07, S-08, W-05 | `rng_throw` (blok) | `ShrekMoved`, `ShrekAimed`, `ItemThrown`, `TempStoneSpawned`, `TempStoneRaised`, `DamStarted`, `DamReleased`, `WaveSpawned(DAM)` |
| 3 | Eşek eylemi | D-02, D-03, D-05, D-08 | `rng_slip` (blok) | `DonkeyMoved`, `DonkeyMoveStarted`, `DonkeySlipped`, `ItemDropped`, `DonkeyStance`, `ItemFloated`, `ItemSank`, `ItemLost` |
| 4 | Mermiler | S-04, S-05, S-06, D-08, D-09, I-04 | — | `ItemCaught`, `ItemMissed`, `ItemBounced`, `ItemReturnedToBank`, `ItemFloated`, `ItemSank`, `ItemLost` |
| 5 | Su | W-01 … W-07 | `rng_water` | `WaveSpawned`, `WaveAbsorbed`, `DamReleased(burst)`, `WaveExited` |
| 6 | Taşlar | S-07 | — | `TempStoneVanished` |
| 7 | Derinlik | D-01, D-04, D-06, D-07 | `rng_slip` (blok) | `DonkeyDepthChanged`, `ItemDropped`, `DonkeySwept`, `LifeLost`, `DonkeyRespawned`, `GameOver(lives)` |
| 8 | Yüzen yükler | I-04, I-05 | — | `ItemCaught(floating)`, `ItemLost(drifted_off)` |
| 9 | Kıyı | I-01, I-02 | `rng_items` | `ItemArrived`, `ItemLost(bank_overflow)` |
| 10 | Teslimat | D-10 | — | `ItemDelivered` |
| 11 | Saat | S-03, D-08 | — | `DonkeyStance(NONE)` (süre doldu), `GameOver(time)` |
| 12 | Olaylar | — | — | Liste `(t, seq)` sırasıyla döndürülür |

## Adımlar

### 0. RNG blokları
- **Girdi:** `rngs`. **Çıktı:** `u_throw[2]` (normal), `u_slip[4]` (uniform).
- **Gerekçe:** R-02. Eylemden bağımsız sabit çekiliş, karşı-olgusal karşılaştırmada aynı tick'in aynı sayıları
  görmesini sağlar. `rng_water` ve `rng_items` kendi adımlarında çeker; çekiliş sayıları eylemden bağımsızdır.

### 1. Eylem doğrulama
- **Girdi:** `actions = {donkey: DonkeyAction, shrek: ShrekAction}`, durum.
- **Çıktı:** doğrulanmış eylemler; geçersiz bileşen NOOP/NONE olur.
- **Kurallar:** eşek yavaş hareketteyse (`move_remaining > 0`) eşek eylemi yok sayılır. Hedef hücrenin graf
  içinde olup olmadığı burada **değil**, adım 3'te kontrol edilir; böylece adım 2'de doğan kaya hesaba katılır.
  `burst_lock` varsa DAM no-op olur; DAM dışında bir yetenek ya da NONE gelirse kilit burada kalkar (S-08). Bu tick
  baraj tutuluyorsa (`ability = DAM` ve kilit yok, S-03) Shrek'in `move` bileşeni no-op olur. THROW ya da ROCK
  gelmesi barajı bırakır (adım 2a), reddedilmez. Cooldown > 0, kuyruk boş (THROW) ya da hedef su hücresiyken
  geçici taş sınırı dolu (ROCK) ise yetenek no-op olur. ROCK'un hedefi, bu tick'in yürüme ve nişanından sonraki
  hücredir; burada önceden hesaplanır. Yavaş hareket sürerken yalnız NOOP dışındaki eşek eylemleri reddedilir.
- **Olay:** her reddedilen bileşen için `ActionRejected(role, component, reason)`. Bu olay ödüle girmez;
  hata ayıklama ve RL tanısı içindir.
- **Gerekçe:** sonraki adımlar yalnız geçerli eylemleri görür. Böylece kural kodu savunmacı kontrollerle dolmaz.

### 2. Shrek eylemleri
Alt sıra: **(a)** baraj bırakma/başlatma → **(b)** yürüme → **(c)** nişan → **(d)** THROW / ROCK.
- (a) Baraj aktifken `ability ≠ DAM` gelirse salınım (W-05, `reason=manual`) yapılır. Bu, aynı tick'te başka
  bir yeteneğin kullanılmasına izin verir: bırak ve at. Aktif değilken DAM gelirse `DamStarted`, `c_d = col`.
- (b) S-01. (c) S-02: nişan atıştan önce uygulanır, böylece "bir satır yukarı + fırlat" tek tick'tir.
- (d) THROW: kuyruğun başı mermi olur (S-04 ya da S-06), `throw_cooldown` kurulur. ROCK: S-07 hemen uygulanır.
- **Gerekçe:** Shrek eşekten önce çözülür. Kaya aynı tick'te var olduğu için eşek aynı tick'te o taşa
  basabilir; iki oyuncunun aynı tick'e denk gelmesi ödüllendirilir (co-op ilkesi). Baraj bırakma (a)'da olduğu
  için salınan dalga adım 5'te ilerlemeye başlar.

### 3. Eşek eylemi
- Süren yavaş hareket varsa `move_remaining` azalır; 0 olunca eşek hedefe geçer (`DonkeyMoved`).
- Yeni hareket: hedef graf dışındaysa no-op ve `ActionRejected(reason=no_stone)` (D-05); geçerliyse duruş bozulur. Önce kayma kontrolü yapılır (D-03, yalnız taştan ayrılırken ve heybe doluyken; `u_slip[0]`; δ = 0 ise taraf `u_slip[1]` ile
  seçilir), sonra durum DRY ise (ya da `slow_move_ticks = 1`) anında geçiş, değilse `DonkeyMoveStarted` ve
  `move_remaining = slow_move_ticks − 1`. Süren hareketin hedefi varışta yeniden denetlenmez (D-05).
- STANCE: D-08.
- Kayan yük ayrılınan hücrede suya düşer (I-04).
- **Gerekçe:** hareket, su güncellemesinden (adım 5) **önce** gelir. Oyuncu karar anında gördüğü duruma göre
  hareket eder: ekrandaki renk, hareketin yapıldığı andaki seviyedir. Bedeli: yükselen bir dalganın önündeki
  taş bir tick boyunca güvenli görünür, adım 7'de derinlik yeni seviyeyle hesaplanır. Bu bilinçli bir seçimdir.
  Dalga göstergesi ve hata ayıklama katmanındaki tahmin bu bedeli telafi eder.

### 4. Mermiler
- Bu tick atılanlar dışındaki tüm mermilerde `ticks_left` 1 azalır; 0 olanlar S-05/S-06'ya göre, yük kimliği
  sırasıyla çözülür. Bu tick atılan mermi ilk kez sonraki tick azalır (S-04).
- Eşeğin konumu ve duruşu adım 3'ten sonraki hâlidir. Bu tick hareket eden eşeğin duruşu bozulmuş olur.
- **Gerekçe:** iniş, eşeğin bu tick'teki kararından sonra çözülür. "Bir tick önce dur" kuralı (D-08) yakalamayı
  bir öngörü işi yapar, refleks işi değil. 0,6 sn'lik tick'te bu, insan için adil bir penceredir.

### 5. Su
Alt sıra: **(a)** OU adımı → **(b)** dalgalar ilerler → **(c)** emilim (W-06) → **(d)** birikim (W-04) →
**(e)** patlama kontrolü (W-05) → **(f)** yeni dalgalar doğar (W-02) → **(g)** silme (W-03, `WaveExited`) → **(h)** L(c) (W-07).
- **Kodda:** `engine/water.py` `water_stage`; her alt adım ayrı, saf bir fonksiyondur.
- **RNG:** `rng_water`: 1 normal, 1 Poisson, N_t üstel. Çekiliş (a) ve (f)'de yapılır; baraj durumu çekiliş
  sayısını etkilemez (INV-03).
- **Gerekçe:** emilim, ilerlemeden hemen sonra yapılır; böylece c_d'yi bu tick geçen dalga yakalanır. Yeni
  doğan dalga bu tick ilerlemez; ilk konumu x = −3s'dir.

### 6. Taşlar
- Geçici taşlar (bu tick doğanlar dahil) `rock_sink_cm_per_tick` batar; kalıcı taşların `raise_h` değeri söner.
- `h < rock_vanish_h_cm` olan geçici taş silinir (`TempStoneVanished`). Üzerindeki eşek adım 7'de SWEPT olur.
- **Gerekçe:** derinlik (adım 7), bu tick'in son taş yüksekliğini ve son su seviyesini birlikte görür.

### 7. Derinlik
- Eşek nehirdeyse D-01 ile e, D-04 ile d ve durum hesaplanır. Durum değiştiyse `DonkeyDepthChanged`. Eşek taşsız
  bir nehir hücresindeyse (geçici taş kayboldu ya da yavaş hareketin hedefi kayboldu) durum SWEPT olur.
- KNEE: `u_slip[2] < knee_drop_prob` ise ağır taraftaki üst yük düşer (taraf δ = 0 ise `u_slip[3]` ile).
- SWEPT: D-07, yeniden doğuş aynı tick'te olur. Can 0'a inerse `GameOver(reason=lives)` ve kalan adımlar yine
  çalışır (olay akışı tutarlı kalsın diye), ama sonraki `step` çağrıları hata verir.
- **Gerekçe:** sürüklenme, teslimattan (adım 10) önce gelir. Adım 3'te kuzey kıyıya varan eşeğin derinliği
  yoktur ve sürüklenemez. Bu yüzden adım 7 ile 10 arasında çakışma olmaz.

### 8. Yüzen yükler
- Önce yakalama (I-05), sonra sürüklenme (`x += flow_speed`), sonra kenar kontrolü (`drifted_off`).
- Bu tick adım 3/4/7'de suya düşen yükler de dahildir.
- **Gerekçe:** yakalama sürüklenmeden önce gelir; böylece eşeğin hücresine düşen yük, eşek duruştaysa bir
  sonraki tick'i beklemeden kurtarılabilir. "Bir tick önce dur" koşulu yine geçerlidir.

### 9. Kıyı
- I-01 varışları, I-02 kapasite. Varış, atıştan (adım 2) sonra gelir; boşalan yer aynı tick doldurulabilir.

### 10. Teslimat
- D-10. Puan skora eklenir.

### 11. Saat
- Cooldown'lar 1 azalır (alt sınır 0). Cooldown `n` olan bir yetenek, kullanıldığı tick'ten `n` tick sonra
  yeniden kullanılabilir.
- Duruş süresi dolduysa (`t − stance_since ≥ stance_max_ticks`, `t` artmadan önce) duruş biter.
- `t += 1`. `t = game_length_ticks` ise `GameOver(reason=time)`.

### 12. Olaylar
- Her olay `(t, seq, type, payload)` taşır; `seq` tick içinde yayılış sırasıdır. Liste, durumla birlikte döndürülür.
- Render, log, ödül ve Uyum raporu yalnızca bu listeyi ve durumu okur (ADR-009).

## Zamanlama örnekleri

| Senaryo | Tick t | Tick t+1 | Tick t+2 |
|---|---|---|---|
| Atış + yakalama | Shrek THROW (uçuş 2) | Eşek STANCE_LEFT | Mermi iner, duruş t+1'de alındığı için geçerli → yakalama |
| Geç duruş | Shrek THROW | — | Eşek STANCE (t+2) → iniş anında `t > stance_since` sağlanmaz → kaçar |
| Kaya + adım | Shrek ROCK (r,c) ve eşek aynı tick'te (r,c)'ye hareket eder → geçerli (adım 2 < 3) | | |
| Dalga sürprizi | Eşek KURU görünen taşa geçer | Adım 5'te dalga gelir, adım 7'de DİZ | |
