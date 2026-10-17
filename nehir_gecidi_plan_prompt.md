# Nehir Geçidi — Plan Modu Başlangıç Prompt'u

> Bu prompt'u Claude Code'da **plan modunda** kullan. Bu aşamada oyun kodu yazılmayacak. Amaç, oyunun tasarım belgelerini, parametrelerini ve proje iskeletini kesinleştirmek ve onaydan sonra bunları dosya olarak üretmek.

---

## 0. Senden beklediğim

Sen bu projenin yazılım mimarı ve tasarım ortağısın. Aşağıdaki bağlam, bir dizi tasarım konuşmasının özeti. Bazı kararlar **kesinleşti**, bazıları **açık**.

1. Önce bu belgenin tamamını oku. **Kod yazma.**
2. Bölüm 9'daki açık sorular için bana sorular sor. Soruları konu başlıklarına göre gruplayıp birkaç tur hâlinde sor; her soruda kendi önerini ve gerekçesini ilk seçenek olarak ver. Kesinleşmiş kararları (Bölüm 2) yeniden tartışmaya açma. Bir kararın başka bir kararla çeliştiğini fark edersen bunu açıkça söyle.
3. Bölüm 6'daki başlangıç parametreleri birer öneri. Tutarsız ya da dengesiz gördüğün değerleri gerekçesiyle işaretle (örnek: bu σ ile taşlar ortalama ne sıklıkla su altında kalır?). Gerekirse küçük hesaplarla destekle.
4. Sorular bittiğinde, Bölüm 8'deki dosya setini üretecek bir plan sun: her dosyanın amacı, başlık yapısı ve içeriğinin özeti. Ben onaylayınca dosyaları yaz.
5. Bana Türkçe yanıt ver.

---

## 1. Proje nedir?

**Nehir Geçidi**, eşimle birlikte tek bilgisayarda oynayacağımız iki kişilik bir **co-op** oyun. Aynı zamanda benim için iki şeyin öğrenme aracı:

- **Stokastik süreçler:** Ornstein–Uhlenbeck süreci, Poisson süreçleri, Markov zincirleri, perkolasyon.
- **Karar ve öğrenme algoritmaları:** değer iterasyonu, A*, MCTS, Q-learning, PPO, çok ajanlı RL (MAPPO), insan verisinden davranış klonlama ve oyun dengelemesi için sezgisel algoritmalar (tavlama benzetimi, GA).

Bu yüzden oyun motoru hem insanlar hem de RL ajanları tarafından oynanabilecek şekilde tasarlanmalı.

**Kahramanlar:** Shrek ve Eşek (oyun içi adlar). Karakter görselleri bu planın kapsamında değil; prototipte iki rol soyut şekillerle gösterilir. Buna karşılık **işlevsel görsel tasarım** (su, taş yüksekliği, denge, atış belirsizliği gibi bilgilerin okunabilir gösterimi) Faz 1'in parçasıdır; bkz. Bölüm 7.1.

**Oyunun özü:** Eşek, suyu yükselip alçalan bir nehirdeki taşların üzerinde ilerleyerek heybesindeki yükleri karşı kıyıya taşır. Shrek başlangıç kıyısında durur, eşeğe yük fırlatır ve sınırlı yetenekleriyle yolu açık tutar. İkisi de tek başına bir şey başaramaz.

**Tasarım ilkeleri (co-op):**
- Karşılıklı bağımlılık: hiçbir rol tek başına skor üretemez.
- Ortak gerilim anları: yakalama, iki oyuncunun aynı tick'e denk gelmesini gerektirir.
- "Komutan oyuncu" sorununu önlemek: zaman baskısı (V0) ve bilgi asimetrisi (V1).
- Başarısızlık kademeli ve hızlı toparlanabilir olmalı; oyunlar kısa (≈3 dakika).

---

## 2. Kesinleşmiş kararlar (ADR olarak kaydedilecek)

| # | Karar | Gerekçe |
|---|---|---|
| ADR-001 | **Tek ekran, tek cihaz, tek klavye.** Eşek sol el (WASD + yakınındaki tuşlar), Shrek sağ el (ok tuşları + yakınındaki tuşlar). | En basit V0; ağ katmanı yok. |
| ADR-002 | **Tick'li yarı gerçek zaman.** Mantık ayrık tick'lerle ilerler (insan modunda ≈0,6 sn), görüntü 60 FPS ve tick'ler arası interpolasyon. Ayrıca her tick'te iki oyuncunun hamlesini bekleyen bir **taktik mod**. | İnsan için gerilim, RL için ayrık ve hızlı motor; tek kod tabanı. |
| ADR-003 | **Sürüklenme + 3 can.** Anında game over yok. Derin suda eşek başlangıç kıyısına sürüklenir, heybe boşalır, 1 can gider. Can biterse oyun biter. | Bir çift için daha eğlenceli; RL için kademeli ödül sinyali. |
| ADR-004 | **Kaya at** (geçici basamak taşı) yeteneği, mancınık yerine seçildi. Mancınık V1 için aday olarak kalır. | Belirsiz, perkolasyon eşiğine yakın haritalarda daha değerli ve oyuna stratejik bir yön veriyor. |
| ADR-005 | **Saf çekirdek / dış kabuk mimarisi.** `step(state, actions, rng) -> (new_state, events)` saf ve deterministik. `engine/` hiçbir dış katmanı (render, controllers, envs, logs) import etmez. | İnsan oyunu ve RL eğitimi aynı kodu paylaşır; replay ve test kolaylaşır. |
| ADR-006 | **Süreç başına ayrı RNG akışı** (`numpy.random.SeedSequence.spawn`): `rng_world`, `rng_water`, `rng_items`, `rng_throw`, `rng_slip`. | Ortak rastgele sayılar: bir oyuncunun kararı diğer süreçlerin geleceğini değiştirmez; stratejiler adil karşılaştırılır. |
| ADR-007 | **Kod İngilizce, arayüz Türkçe.** Sözlük (GLOSSARY.md) iki dil arasında köprüdür. | RL ekosistemi ve akademik paylaşım için İngilizce kod; kullanıcı için Türkçe arayüz. |
| ADR-008 | **Kodda sabit sayı yok.** Tüm parametreler birimli YAML config'de, pydantic ile doğrulanır. Birimler: yükseklik **cm**, kütle **kg**, zaman **tick**. | Dengeleme ve zorluk profilleri; "bu 3 neydi?" sorununu önlemek. |
| ADR-009 | **Ödül ve metrikler olaylardan türetilir.** Motor her tick bir olay listesi yayar; render, log, RL ödülü ve Uyum raporu bu olaylardan beslenir. | Ödül tanımını değiştirmek motoru değiştirmeyi gerektirmez. |
| ADR-010 | **Replay = seed + eylem dizisi.** Ayrıca analiz için her tick olaylar JSONL'e yazılır. Log'a motor sürümü ve config hash'i eklenir. | Bit düzeyinde tekrar üretilebilirlik. |

---

## 3. Dünya modeli

### 3.1 Harita
- Nehir akış yönünde **C sütun** (batıdan doğuya akar), karşıya geçiş yönünde **R satır**. Güneyde başlangıç kıyısı (Shrek burada), kuzeyde karşı kıyı (teslimat).
- Her hücre ya bir **taş** ya da yalnızca **su**. Eşeğin hareket uzayı taşların oluşturduğu **graf** (4 komşuluk).
- **Harita üretimi: site perkolasyonu.** Her hücreye p olasılığıyla taş konur. Kare ızgarada 4 komşuluklu site perkolasyonunun kritik eşiği p_c ≈ 0,593. Zorluk ayarı bu parametre:
  - p ≈ 0,70: yol neredeyse her zaman var (ısınma),
  - p ≈ 0,58: yol bazen var, Kaya at kritik (co-op'un tatlı noktası),
  - p ≈ 0,50: Shrek olmadan geçiş imkânsız.
- Taş özellikleri: `base_h` (cm, taban yüksekliği), `stiffness` k (kg/cm), `mossy` (bool; düşük k ve yüksek kayma çarpanı).
- Üretimden sonra yol kontrolü (BFS) yapılır; profile göre "yol garantili" ya da "yol garantisiz" olabilir.
- Her harita bir seed'den üretilir; aynı seed aynı dünyayı verir.

### 3.2 Su (üç katman)
- **W-01 Taban seviyesi, Ornstein–Uhlenbeck (AR(1)):** `B(t+1) = B(t) + θ(μ − B(t)) + σ·ε`, ε ~ N(0,1).
- **W-02 Taşkın dalgası varışı:** Yukarı akıştan (sütun 0) her tick Poisson(λ) sayıda dalga doğar; genlik A ~ Üstel(ortalama ā).
- **W-03 Yürüyen dalga profili:** `W(c,t) = Σ_k A_k · exp(−(c − v·(t − t_k))² / 2s²)`. Yukarıda görülen dalga aşağıya birkaç tick sonra ulaşır; gelecek kısmen tahmin edilebilir.
- **W-04 Baraj birikimi:** Shrek c_d sütununda barajı tuttuğu sürece c > c_d sütunlarında su seviyesi düşer; yukarıda Q hacmi birikir: `Q(t+1) = Q(t) + q_in`.
- **W-05 Baraj salınımı:** Baraj bırakıldığında c_d'den genliği α·Q olan bir dalga salınır (kütlenin korunumu). Barajı uzun tutmak bedava değildir.
- Sütun c'deki su seviyesi: `L(c,t) = B(t) + W(c,t) − baraj_etkisi(c,t)`.
- (V1 adayı) Gizli rejimler (sakin / kabaran / taşkın) bir Markov zinciriyle değişir; oyun bir HMM'ye dönüşür.

### 3.3 Eşek
- **D-01 Etkin taş yüksekliği:** `e_i = h_i + r_i(t) − (m_eşek + M_heybe) / k_i` (eşek taşın üzerindeyken). r_i, Shrek etkisiyle oluşan geçici yükselti (Kaya at taşları için kendi yüksekliği).
- **Derinlik:** `d = L(c_i, t) − e_i`.
- **Kademeli derinlik durumu:**

  | Derinlik | Durum | Sonuç |
  |---|---|---|
  | d < 0 | KURU (`DRY`) | Normal hareket |
  | 0 ≤ d < d₁ | BİLEK (`ANKLE`) | Hareket 2 tick sürer |
  | d₁ ≤ d < d₂ | DİZ (`KNEE`) | Her tick p_drop olasılıkla heybenin üstündeki yük suya düşer |
  | d ≥ d₂ | SÜRÜKLENME (`SWEPT`) | Başlangıç kıyısına dönüş, heybe boşalır, 1 can gider |

- **İki heybe (sol/sağ):** her birinin ağırlık ve hacim kapasitesi var.
- **D-02 Denge:** `δ = (m_sağ − m_sol) / (m_sağ + m_sol + m_eşek)`.
- **D-03 Kayma (yalnızca hareket anında):** `p_kayma = p₀ + κ·δ²·yosun_çarpanı`. Kayınca ağır taraftaki üst yük suya düşer.
- Yakalama sırasında oyuncu sol ya da sağ heybeyi seçer; denge, kapasite ve hacim birlikte düşünülür (çevrimiçi sırt çantası problemi).
- Karşı kıyıya ulaşınca heybe otomatik boşalır ve teslimat puanı alınır.

### 3.4 Shrek
- Başlangıç kıyısı boyunca **tek boyutlu** yürür (sütun değiştirir).
- **Nişan:** kendi sütununda, ↑↓ ile seçtiği satıra atar. Bu yüzden konumu önemlidir.
- **Yük varışları:** Kıyıya yükler Poisson(λ_items) sürecine göre gelir. Kıyı kapasitesi sınırlı; dolunca yeni gelen yük kaybolur (kuyruk sistemi).
- **Üç yetenek (V0); aynı anda yalnızca biri:**
  1. **Fırlat (yük):** Kıyıdaki sıradaki yükü nişanlanan hücreye atar. Uçuş süresi 1–2 tick. İniş noktası gürültülü: `σ = σ₀ + σ₁·mesafe + σ₂·ağırlık`. Eşek **iniş anında** yakalama duruşundaysa (bir önceki tick'te durup "yakala-sol" ya da "yakala-sağ" seçmişse) ve yük yakalama yarıçapına düşerse yük heybeye girer. Kaçırılan yük suya düşer: yüzen yükler akıntıyla aşağı sürüklenir ve tekrar yakalanabilir, ağır olanlar hemen batar. Cooldown var.
  2. **Kaya at:** Nişanlanan boş su hücresine geçici bir taş atar. Taş zamanla doğrusal olarak batar ve sonunda yok olur. Perkolasyon eşiğinin altındaki haritalarda yol açar. Cooldown var.
  3. **Baraj:** Kanalize yetenek. Tuş basılı tutulduğu sürece aktif; bu sırada Shrek yürüyemez, atış yapamaz. Bırakınca biriken su dalga olarak salınır (W-04, W-05).

### 3.5 Yükler (V0)

| Yük | Kod | Ağırlık | Hacim | Puan | Suda |
|---|---|---|---|---|---|
| Elma kasası | `apple_crate` | 10 kg | 1 | 1 | Yüzer |
| Patates çuvalı | `potato_sack` | 30 kg | 2 | 3 | Batar |
| Karpuz | `watermelon` | 50 kg | 3 | 6 | Yüzer |

**Yükün yaşam döngüsü (durum makinesi):**
`ON_BANK → IN_FLIGHT → IN_BAG → DELIVERED`; yan dallar: kıyı kapasitesi taşarsa `LOST`; kaçarsa yüzenler `FLOATING` (tekrar yakalanabilir → `IN_BAG`, haritadan çıkarsa `LOST`), batanlar `LOST`; diz derinliği / kayma / sürüklenmede `IN_BAG`'den `FLOATING` veya `LOST`.

**Eşeğin durum makinesi:** `DRY ⇄ ANKLE ⇄ KNEE → SWEPT → (kıyıda yeniden doğuş) DRY`; can 0 olursa `GAME_OVER`.

### 3.6 Amaç ve ölçüm
- **Takım skoru:** süre (T tick) sonunda teslim edilen toplam puan.
- **Uyum raporu** (oyun sonu, olaylardan hesaplanır): yakalama başarı oranı; eşeğin yakalama duruşu ile Shrek'in atışı arasındaki ortalama gecikme; barajın dalga gelmeden önce mi (öngörü) yoksa sonra mı (tepki) kullanıldığı; kurtarılan kritik anlar; kaybedilen yüklerin nedenlere göre dağılımı.

---

## 4. Tick boru hattı (çözüm sırası)

Sıra oyunun anlamını belirler; TICK.md'de bu sıra ve gerekçeleri yazılacak.

1. **Eylem doğrulama:** cooldown, baraj kanalı, geçersiz hamle → no-op.
2. **Shrek eylemleri:** yürü / nişan / fırlat (mermi doğar) / kaya at / baraj aç-kapa.
3. **Eşek eylemi:** hareket (kayma kontrolü) / yakalama duruşu.
4. **Mermiler:** uçuştaki yükler ilerler; inen yük için yakalama çözümü.
5. **Su:** OU adımı, dalgalar ilerler, baraj birikimi / salınımı.
6. **Taşlar:** geçici taşlar batar; yük altında etkin yükseklik.
7. **Derinlik:** eşeğin derinlik durumu; diz kayıpları, sürüklenme.
8. **Yüzen yükler:** akıntıyla sürüklenir; batanlar kaybolur.
9. **Kıyı:** Poisson yük varışı; kapasite taşması.
10. **Teslimat:** eşek karşı kıyıdaysa heybe boşalır.
11. **Saat:** cooldown'lar azalır, süre, bitiş kontrolü.
12. **Olaylar:** tick'in olay listesi yayılır.

Hareket, su güncellemesinden önce gelir: oyuncu karar anında gördüğü duruma göre hareket eder. Bedeli: yükselen bir dalganın ortasındaki taş bir tick boyunca güvenli görünür. Bu bilinçli bir seçim.

---

## 5. Kontroller (öneri; config'de, scancode ile)

Tuş atamaları karakter değil **scancode** ile yapılır (Türkçe Q klavyede düzenden bağımsız olsun diye) ve config'de durur.

| Rol | Tuş | Eylem |
|---|---|---|
| Eşek | W A S D | Hareket |
| | Q / E | Sol / sağ heybeye yakalama duruşu |
| Shrek | ← → | Kıyı boyunca yürü |
| | ↑ ↓ | Nişan mesafesi (satır) |
| | Sağ Ctrl | Fırlat |
| | Sağ Shift | Kaya at |
| | Enter (basılı tut) | Baraj |

- Girdi tamponu: bir tick penceresinde her oyuncunun **son** girdiği eylem geçerli; baraj basılı tutmayla çalışır.
- **Ghosting riski:** aynı klavyede iki oyuncu birden fazla tuşa aynı anda basacak. Planda bir "klavye ghosting testi" adımı olsun. Gamepad desteği ileride yalnızca yeni bir controller olarak eklenebilmeli.

---

## 6. Başlangıç parametreleri (öneri — tutarlılığını kontrol et)

```yaml
time:
  tick_seconds: 0.6
  game_length_ticks: 300       # ≈3 dk
  lives: 3

map:
  rows: 9                      # karşıya geçiş yönü
  cols: 9                      # akış yönü
  stone_density: 0.62          # profile göre değişir
  stone_base_h_cm: [5, 25]     # uniform aralık, μ=0 su referansına göre
  stiffness_kg_per_cm: 50
  mossy_prob: 0.15
  mossy_stiffness_kg_per_cm: 25
  mossy_slip_multiplier: 3.0

water:
  ou_theta: 0.08               # 1/tick
  ou_mu_cm: 0.0
  ou_sigma_cm: 1.5
  wave_rate: 0.02              # dalga/tick
  wave_amp_mean_cm: 12
  wave_speed_cols_per_tick: 0.5
  wave_width_cols: 1.5         # s
  dam_inflow_per_tick: 1.0     # q_in
  dam_downstream_drop_cm: 10
  dam_release_alpha: 1.0
  flow_speed_cols_per_tick: 0.5  # yüzen yüklerin sürüklenme hızı

donkey:
  mass_kg: 200
  bag_max_kg_per_side: 60
  bag_max_volume_per_side: 4
  depth_ankle_cm: 0            # d ≥ 0 → BİLEK
  depth_knee_cm: 8             # d₁
  depth_swept_cm: 20           # d₂
  knee_drop_prob: 0.15
  slip_base_prob: 0.01         # p₀
  slip_kappa: 2.0

shrek:
  throw_cooldown_ticks: 3
  throw_flight_ticks: 2
  throw_sigma0_cells: 0.2
  throw_sigma_per_row: 0.1
  throw_sigma_per_kg: 0.004
  catch_radius_cells: 0.5
  rock_cooldown_ticks: 20
  rock_initial_h_cm: 25
  rock_sink_cm_per_tick: 1.0

items:
  arrival_rate_per_tick: 0.1
  bank_capacity: 5
  type_probs: {apple_crate: 0.5, potato_sack: 0.3, watermelon: 0.2}
```

Kontrol etmeni istediğim örnek sorular: Bu σ ve dalga parametreleriyle ortalama bir taş tick'lerin yüzde kaçında su altında kalır? 200 kg'lık eşek + 60 kg yük ile 50 kg/cm sertlikte taş kaç cm iner ve bu derinlik eşikleriyle anlamlı mı? Yük varış hızı, eşeğin bir tur süresiyle uyumlu mu, yoksa kıyı sürekli mi taşar?

---

## 7. Mimari ve teknoloji

```
nehir_gecidi/
├── CLAUDE.md
├── docs/            # Bölüm 8
├── config/          # default.yaml + zorluk profilleri
├── engine/          # saf Python + numpy; render/klavye bilmez
│   ├── world.py     # harita üretimi (perkolasyon + yol kontrolü)
│   ├── water.py     # OU + Poisson dalgalar + baraj
│   ├── donkey.py, shrek.py, items.py
│   ├── step.py      # tick boru hattı
│   └── observe.py   # rol başına gözlem (V0 tam, V1 kısmi)
├── controllers/     # klavye, betik bot, RL politikası — ortak arayüz: act(observation) -> action
├── render/          # pygame-ce
├── logs/            # replay (seed + eylemler) + olay JSONL
├── envs/            # Gymnasium (tek ajan) + PettingZoo (iki ajan) sarmalayıcıları
└── tests/
    ├── rules/       # kural kimlikli testler: test_W04_dam_mass_conservation …
    └── invariants/  # hypothesis ile değişmezler
```

- **Yığın:** Python 3.12, numpy, pygame-ce, pyyaml + pydantic v2, pytest + hypothesis, uv. Sonra: gymnasium, pettingzoo, stable-baselines3.
- **Durum nesnesi:** önce değişmez/kopyalanan durum (doğruluk ve replay kolaylığı); darboğaz ölçülürse yerinde güncellemeye geçilir.
- **Gözlem fonksiyonu** V0'da tam gözlem döndürür ama rol bazlı tasarlanır, böylece V1'deki kısmi gözlem (Shrek yukarıyı görür, eşek taş sertliğini ve dengesini görür) arayüzü değiştirmeden eklenir.

**Değişmezler (tests/invariants):**
- Yük korunumu: doğan yük = kıyıda + havada + heybede + yüzen + teslim + kayıp (her tick, her seed).
- Determinizm: aynı seed + aynı eylem dizisi → bit düzeyinde aynı sonuç.
- Akış bağımsızlığı: atış eylemlerini değiştirmek su geçmişini değiştirmez.
- Baraj korunumu: salınan hacim = biriken hacim.
- Kapasite: heybe ağırlık/hacim sınırı hiçbir zaman aşılmaz.
- Can: yalnızca `DonkeySwept` olayında ve yalnızca bir azalır.

**Olay kataloğu (taslak):**
`ItemArrived · ItemThrown · ItemCaught(side) · ItemMissed · ItemFloated · ItemSank · ItemLost(reason) · ItemDelivered(points) · DonkeyMoved · DonkeySlipped · DonkeyDepthChanged(level) · DonkeySwept · LifeLost · TempStoneSpawned · TempStoneVanished · DamStarted · DamReleased(Q) · WaveSpawned · GameOver(reason)`

### 7.1 Görsel katman

Bu oyunda görsellik süs değil, **bilgi gösterimidir**: oyuncular kararlarını su seviyesi ile taş yüksekliği arasındaki farkı, yaklaşan dalgayı ve dengeyi ekrandan okuyarak verir. Bu yüzden görsel katman iki kademede ele alınır:

**Kademe 1 — İşlevsel görünüm (Faz 1, oyun testinden önce):**
- **Perspektif:** 3/4 eğik (oblique) görünüm önerisi: ızgara eksenleri ekranla hizalı kalır (WASD sezgisel), taşlar yükseklikleri kadar dikey uzatılmış sütunlar olarak çizilir, su yarı saydam bir düzlemdir. Böylece oyunun ana değişkeni olan yükseklik doğrudan görünür. İzometrik görünüm, WASD'yi çapraz hissettirdiği için önerilmez. Alternatif: üstten görünüm + yan kesit paneli. Bu kararı bana sor.
- **Taş rengi = güvenlik payı** (e_i − L): kuru / bilek / diz / tehlike için renk körlüğüne duyarlı bir renk skalası; renge ek olarak desen veya ikon.
- Su: hafif dalgalanma animasyonu; yukarı akış kenarında yaklaşan dalgaların göstergesi.
- Shrek: nişan imleci; atış hedefinde **σ'yı gösteren belirsizlik halkası** (atış gürültüsü görünür olsun); uçuşta yay ve iniş gölgesi.
- Eşek: denge çubuğu (δ), heybe doluluğu (sol/sağ), derinlik durumu.
- Arayüz: canlar, süre, skor, yetenek cooldown çubukları, baraj birikim göstergesi (Q). Tüm metinler Türkçe; font Türkçe karakterleri (ğ ş ı İ ç ö ü) desteklemeli (ör. Noto Sans).
- **Hata ayıklama katmanı** (tuşla aç/kapa): taş başına sayısal derinlik, dalga tahmini, RNG akışı bilgisi.
- Render yalnızca `state` ve `events` okur; motora hiçbir şey yazmaz.

**Kademe 2 — Görsel cila (Faz 1.5, ilk oyun testinden sonra):**
- Sanat yönü ve renk paleti, çevre tileset'i (nehir, taşlar, kıyılar), yük ikonları, animasyon ve "juice" (sıçrama parçacıkları, sürüklenmede ekran sarsıntısı), ses efektleri.
- Kaynak önerileri: CC0 asset paketleri (ör. Kenney), Aseprite / LibreSprite / Piskel ile piksel çizim, kodla prosedürel çizim, CC0 ses kütüphaneleri ve sfxr türü ses üreteçleri.
- Karakter sprite'ları kapsam dışı; roller soyut şekillerle kalır.

**Teknoloji:** pygame-ce (2D için yeterli, tek dil). Daha gelişmiş görsellik istenirse olay tabanlı mimari sayesinde render katmanı değiştirilebilir (ör. Python `arcade` ile shader desteği ya da ayrı bir web/Godot ön yüzü). Bu, motoru etkilemez.

---

## 8. Plan sonunda üretilecek dosyalar (bu aşamada kod yok)

| Dosya | İçerik |
|---|---|
| `CLAUDE.md` | Proje amacı, bağımlılık kuralı (ADR-005) ilk satırda, birim sistemi, iş akışı (belge → kural kimlikli test → kod), belge haritası, kodlama kuralları |
| `docs/GLOSSARY.md` | Türkçe (arayüz) ↔ İngilizce (kod) ↔ tanım tablosu |
| `docs/ENTITIES.md` | Varlıklar, alanları, birimleri; yük ve eşek durum makineleri (Mermaid) |
| `docs/MODEL.md` | Biçimsel model: Markov oyunu (S, A_donkey, A_shrek, T, R, O); kural kimlikli formüller (W-xx su, D-xx eşek, S-xx Shrek, I-xx yük, M-xx harita) |
| `docs/TICK.md` | Boru hattı sırası, her adımın girdisi/çıktısı ve sıralama gerekçeleri |
| `docs/EVENTS.md` | Olay kataloğu: alanlar, hangi adımda yayıldığı, kim tüketir |
| `docs/CONTROLS.md` | Tuş düzeni (scancode), girdi tamponu, taktik mod |
| `docs/METRICS.md` | Takım skoru ve Uyum raporu göstergelerinin olaylardan hesaplanışı |
| `docs/VISUALS.md` | Görsel dil: perspektif, renk skalası (renk körlüğü dahil), ekran yerleşimi, HUD öğeleri, hata ayıklama katmanı, Kademe 1/2 ayrımı |
| `docs/ROADMAP.md` | Fazlar ve her fazın kabul kriterleri |
| `docs/adr/ADR-001 … ADR-010.md` | Bölüm 2'deki kararlar (bağlam, karar, sonuçlar, değerlendirilen alternatifler) |
| `config/default.yaml` | Kesinleşen parametreler, birim ve aralık yorumlarıyla |
| `config/profiles/*.yaml` | Zorluk profilleri (ör. `warmup`, `percolation_edge`, `hard`) |

**Yol haritası (ROADMAP.md için):**
- **Faz 0:** Motor + testler; seed'den harita, su süreci, `step`; taktik modda metin tabanlı oynatma.
- **Faz 1:** V0 oynanabilir: pygame-ce, tek ekran, iki oyuncu aynı klavye, üç yetenek, 3 dakikalık oyunlar; Kademe 1 işlevsel görünüm; ilk oyun testi ve parametre ayarı.
- **Faz 1.5:** Kademe 2 görsel cila ve ses; ikinci oyun testi.
- **Faz 2:** Replay, olay logları, Uyum raporu.
- **Faz 3:** Betik botlar (A* eşek, kural tabanlı Shrek), küçük haritada değer iterasyonu.
- **Faz 4:** RL: tablolu Q-learning (mini harita), betik Shrek ile PPO eşek, MAPPO.
- **Faz 5 (V1):** Bilgi asimetrisi (iki görünüm), gizli su rejimleri (HMM), mancınık adayı, insan verisiyle davranış klonlanmış yapay partner, tavlama/GA ile oyun dengeleme.

**Kapsam dışı (şimdilik):** ağ / iki cihaz, karakter sprite'ları, gamepad, menü sistemi süslemeleri.

---

## 9. Açık sorular (bana sor)

Gruplar hâlinde, her soruda önerinle birlikte:

1. **Belge dili:** Belgeler Türkçe mi (kod tanımlayıcıları İngilizce, backtick içinde), İngilizce mi? CLAUDE.md için ayrı bir tercih gerekir mi?
2. **Harita ve parametreler:** Bölüm 6'daki değerler; harita boyutu; varsayılan zorluk profili; yol garantisi her profilde mi olmalı?
3. **Teslimat ve kıyı etkileşimi:** Eşek başlangıç kıyısındayken Shrek'ten yükü doğrudan (atışsız, risksiz) alabilir mi? (Alabilirse nehrin ortasına atış, zaman kazandıran ama riskli bir strateji olur.) Karşı kıyıda boşaltma otomatik mi, tuşla mı?
4. **Yakalama kuralları:** Yakalama duruşu kaç tick sürebilir? Duruştayken eşek hareket edemez mi? Yakalama yarıçapı ve heybe doluysa ne olur?
5. **Kaya at ayrıntıları:** Menzil (yalnızca nişan hücresi mi?), eşek üzerindeyken geçici taş batmaya devam eder mi, aynı anda kaç geçici taş olabilir, mevcut bir taşın üzerine atılırsa ne olur?
6. **Baraj ayrıntıları:** Barajın etkili olduğu sütun Shrek'in sütunu mu? Maksimum tutma süresi ya da Q üst sınırı olmalı mı? Baraj sırasında yukarıdaki sütunlarda su yükselir mi?
7. **Yüzen yükler:** Haritadan çıkmadan önce kaç tick yüzer? Eşek yüzen yükü yalnızca bulunduğu hücrede mi yakalayabilir?
8. **Sürüklenme sonrası:** Yeniden doğuş gecikmesi, kısa dokunulmazlık süresi olsun mu?
9. **Skor ve bitiş:** Yalnızca süre mi, yoksa hedef puan / tüm canların bitmesi de bitiş koşulu mu? Kalan can skora eklenir mi?
10. **Taktik mod ve hata ayıklama:** Taktik modda ekstra bilgi katmanları (taş derinlikleri, dalga tahmini) gösterilsin mi?
10b. **Görsel katman:** Perspektif (3/4 eğik mi, üstten + yan kesit mi), pencere çözünürlüğü, renk skalası, ekran yerleşimi (HUD nerede, her oyuncunun bilgisi ekranın kendi tarafında mı).
11. **Bu belgede gözden kaçan, çelişen ya da eksik bulduğun her şey.**
