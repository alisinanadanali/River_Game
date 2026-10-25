# Görsel Dil (VISUALS)

Bu oyunda görsellik **bilgi gösterimidir**. Oyuncular kararlarını su seviyesi ile taş yüksekliği arasındaki
farktan, yaklaşan dalgadan, atış belirsizliğinden ve dengeden okur. Render katmanı yalnızca `state` ve `events`
okur, motora hiçbir şey yazmaz (ADR-005). Teknoloji: pygame-ce, 60 FPS, tick'ler arası interpolasyon (ADR-002).

## 1. Kademe ayrımı

| Kademe | Faz | Kapsam |
|---|---|---|
| **1 — İşlevsel görünüm** | Faz 1 (ilk oyun testinden önce) | §2–§7 ve §9; düz renkler, desenler, Türkçe metin; karakterler yerel resimlerle ya da soyut şekille (§9) |
| **2 — Görsel cila** | Faz 1.5 (ilk oyun testinden sonra) | §8 |

## 2. Perspektif: 3/4 eğik (oblique)

Izgara eksenleri ekranla hizalıdır: sütunlar soldan sağa (akış yönü), satırlar aşağıdan yukarıya (güneyden
kuzeye). WASD sezgisel kalır. Yükseklik dikey bir uzatma olarak gösterilir.

```
x_ekran = x0 + c · tile_w
y_ekran = y0 + (R − 1 − r) · tile_h − z · px_per_cm
```

- `tile_w = 80 px`, `tile_h = 48 px` (zemin kısalması 0,6), `px_per_cm = 1,6`. Bu değerler `render.layout`
  config'indedir.
- **z'nin referansı** motorunkiyle aynıdır: cm, OU ortalaması μ'ye göre (M-03 taş yükseklikleri ve `L` bu
  ölçektedir; z negatif olabilir). `(x0, y0)` satır R − 1'in (en kuzey nehir satırı) z = 0'daki sol üst köşesidir.
- **Dikey pay:** tahta (R nehir satırı + iki kıyı) harita alanında (§4) ortalanır; üstünde
  `layout.z_room_cm · px_per_cm` px boşluk bırakılır, en kuzey satırın yükselen taşı ve suyu ekrana sığsın diye.
  Daha yüksek z'ler üst şeridin altında kalır. Her profil için tahtanın payıyla harita alanına sığdığı test edilir.
- **Kıyılar:** kuzey ve güney kenarında tam genişlikte koyu toprak şeritleri (`palette.bank`); üst yüzleri
  `z = layout.bank_z_cm`'de, ön yüzleri z = 0'a kadar iner. Model kıyıyı her zaman kuru sayar (D-04); yükseklik
  yalnız çizim içindir.
- **Taş:** üst yüzü hücre büyüklüğünde, `z` yüksekliğinde bir dikdörtgen. Eşeğin durduğu taşta `z = e_i` (o anki
  yükle, D-01); boş kalıcı taşta `h_i + r_i`, boş geçici taşta `h(t)`. Üst yüz su seviyesinin üstündeyse ön yüzü,
  hücrenin güney kenarından su seviyesine (`z = L(c)`) inen, üst yüz renginin `layout.front_shade` katı koyu bir
  şerittir (prizma). Üst yüz suyun altındaysa ön yüz çizilmez; su, üst yüzün üstüne yarı saydam çizilir. Üst
  yüzün su çizgisine göre konumu güvenlik payını doğrudan gösterir.
- **Su:** her nehir hücresinde yarı saydam (`layout.water_alpha`) bir şerit. Yüksekliği sütun ortasında `L(c)`,
  hücrenin batı/doğu kenarında komşu sütunla ortalaması (sütunlar arası doğrusal geçiş, dalga profilini görünür
  kılar); tahtanın iki ucunda düzdür. Hücrenin üstünde bir taş varsa ve üst yüzü suyun üstündeyse o hücrede su
  görünmez (taş hücreyi doldurur). Tick'ler arasında `L` önceki ve şimdiki tick arasında doğrusal geçer.
  Hafif dalgalanma animasyonu (sinüs ofseti) Faz 1.5 cilasına bırakıldı (§8): derinlik okumayı bozmasın.
- **Çizim sırası:** kuzeyden güneye (arkadan öne) satır satır, satırda batıdan doğuya; her hücrede taş → su.
  Karakter, iki hücre arasındaysa güneydekinin satırıyla birlikte, o satırın hücrelerinden sonra çizilir; böylece
  önündeki (güneydeki) satırlar onu örter. Nişan çerçevesi ve uçan yük gölgesi en son, hücrenin görünen yüzeyinde
  (taşın üst yüzü ya da su, hangisi yüksekse; kıyıda kıyının üst yüzü) çizilir.

## 3. Renk skalası: güvenlik payı

Girdi `m = e − L = −d` (cm). Boş taşlar için `e`, eşeğin **o anki yüküyle** hesaplanan tahmindir (D-01):
renk "eşek şimdi buraya bassa" sorusunu yanıtlar. Okabe–Ito paleti renk körlüğüne duyarlıdır; her kademe ayrıca
bir **desenle** ayırt edilir, renk tek kanal değildir.

| Kademe | Koşul | Renk (Okabe–Ito) | Hex | Desen |
|---|---|---|---|---|
| KURU | m > 0 | Mavimsi yeşil | `#009E73` | Düz |
| BİLEK | −d₁ < m ≤ 0 | Sarı | `#F0E442` | Seyrek noktalar |
| DİZ | −d₂ < m ≤ −d₁ | Turuncu | `#E69F00` | Çapraz çizgiler |
| TEHLİKE | m ≤ −d₂ | Kırmızımsı (vermillion) | `#D55E00` | Kafes + "!" ikonu |

- Kademe sınırları D-04'ün sınıflandırmasıdır (`classify_depth(d)`, `d = −m`); tablo `depth_ankle_cm = 0` içindir.
  Eşeğin durduğu taşta `e` zaten o yükle hesaplanır, yani renk eşeğin kendi derinlik durumunu gösterir.
- Su: `#0072B2` (mavi), saydam. Kuru taşların yeşili ile çakışmaz.
- **Desenler** üst yüze, `palette.background` (koyu) mürekkeple çizilir. Desen yoğunluğu tehlikeyle artar: KURU
  boş, BİLEK seyrek noktalar, DİZ tek yönlü çapraz çizgiler, TEHLİKE iki yönlü kafes ve ortada "!" işareti
  (çizgiyle çizilir, fonttan değil).
- Yosunlu taş: üst yüzde dalgalı "≈" işareti (iki dalgalı çizgi) ve koyu kontur.
- Geçici taş: kesikli kontur ve üst yüzün güney kenarında kalan ömür çubuğu: dolu payı
  `(h − rock_vanish_h_cm) / (rock_initial_h_cm − rock_vanish_h_cm)`, [0, 1]'e kırpılır.
- **Tick'ler arasında:** renk, önceki tick'teki kademenin renginden şimdikinin rengine `u` ile doğrusal geçer;
  desen, o karede çizilen su seviyesiyle (`L` interpolasyonlu) hesaplanan kademeye göre anında değişir.
- **Doğrulama (renk körlüğü, `tests/render/test_colour.py`):** renkler Machado, Oliveira ve Fernandes (2009)
  benzetim matrisleriyle (şiddet 1,0; protanopi, döteranopi, tritanopi; doğrusal sRGB üzerinde) dönüştürülür,
  CIELAB'da (D65) CIE76 farkı ölçülür. Eşik **ΔE₇₆ ≥ 10** (bir bakışta ayırt edilir; fark edilebilirlik eşiği
  ≈ 2,3'tür). Koşullar, normal görme ve üç benzetimin her birinde:
  1. Dört kademe rengi, su üstünde, ikişer ikişer ΔE₇₆ ≥ 10. (Ölçüm 2026-10-25: en küçüğü döteranopide BİLEK–DİZ,
     ≈ 17.)
  2. Su altında renk tek başına yetmez: su (alfa 0,55) rengi maviye çeker; protanopide su üstü KURU ile su altı
     BİLEK arasında ΔE₇₆ ≈ 4,4. Bu yüzden desen taşır: her kademenin deseni farklıdır, desen yoğunluğu kademeyle
     kesin artar ve mürekkep ile zemin arasındaki fark su üstünde ve altında ΔE₇₆ ≥ 10'dur.
- **Ekran görüntüleri:** `uv run python -m tools.cvd_shots` dört kademeyi su üstünde ve altında gösteren bir
  tahtayı normal ve üç benzetimle `runs/cvd/` altına PNG olarak yazar (git'e girmez); gözle kontrol içindir.

## 4. Ekran yerleşimi (1280 × 720, ölçeklenebilir)

```
┌───────────────────────────────────────────────────────────────────────┐
│ ÜST ŞERİT (48 px): ⏱ süre  ·  ★ skor  ·  ♥♥♥ can  ·  [mod: Gerçek/Taktik] │
├──────────────┬──────────────────────────────────────────┬─────────────┤
│ EŞEK PANELİ  │  ← dalga göstergesi (batı kenarı)          │ SHREK PANELİ│
│ (240 px)     │        KUZEY KIYI (teslimat)              │ (240 px)    │
│ • Denge δ    │  ┌──┬──┬──┬──┬──┬──┬──┬──┬──┐              │ • Kıyı      │
│ • Sol heybe  │  │  │  │  │  │  │  │  │  │  │  9 × 9       │   kuyruğu   │
│ • Sağ heybe  │  ├──┼──┼──┼──┼──┼──┼──┼──┼──┤  harita      │ • Sıradaki  │
│ • Derinlik   │  │  │  │  │  │  │  │  │  │  │  (800 px)    │   yük       │
│ • Duruş      │  └──┴──┴──┴──┴──┴──┴──┴──┴──┘              │ • Fırlat cd │
│              │        GÜNEY KIYI (Shrek)                 │ • Kaya cd   │
│              │                                          │ • Baraj Q   │
├──────────────┴──────────────────────────────────────────┴─────────────┤
│ ALT ŞERİT (32 px): son olaylar akışı (Türkçe)                          │
└───────────────────────────────────────────────────────────────────────┘
```

Her rolün paneli klavyede o rolün elinin olduğu tarafta durur: Eşek solda, Shrek sağda.

### 4.1 Yürüyen iskelet (Faz 1.4) ve tahta (Faz 1.5)

Faz 1'in ilk oynanabilir penceresi; sonraki adımlar her parçayı yerine koyar (1.5 eğik izdüşüm, 1.6 renk skalası,
1.7 karakterlerin su çizgisinde kırpılması ve hayalet, 1.8 HUD). Çizim yalnız gözlem okur (`observe`, ADR-005).

- **İzdüşüm** (Faz 1.5'ten beri §2'nin tamamı): hücre `(r, c)`'nin z yüksekliğindeki ortası
  `x = x0 + (c + ½) · tile_w`, `y = y0 + (R − 1 − r + ½) · tile_h − z · px_per_cm`; satır −1 (güney kıyı) en
  altta, satır R (kuzey kıyı) en üstte. Tahta, payıyla birlikte, harita alanının (§4: üst/alt şerit ve iki panel
  dışında kalan alan) ortasındadır.
- **Hücreler:** kıyılar `palette.bank`, taşlar (kalıcı ve geçici) §3'ün güvenlik payı renkleri, desenleri ve
  işaretleriyle (Faz 1.6), su `palette.water`, §2'deki gibi.
- **Karakterler:** ayakları durdukları yüzeyde, hücre ortasında: kıyıda `bank_z_cm`, taşta §2'nin üst yüz z'si, taşı olmayan hücrede (ör. geçici taş
  altında kaybolunca) su yüzeyi `L(c)`.
  Shrek güney kıyı hücresinin güney kenarında (eşek de başlangıçta güney kıyıdadır, ikisi üst üste binmez).
  Konum ve ayak yüksekliği tick'ler arasında önceki ve şimdiki değer arasında doğrusal geçer
  (`u = since_tick_s / tick_seconds`, [0, 1]'e kırpılır). Klipler §9.3'teki gibi tick olaylarından.
- **Su çizgisi** (Faz 1.7, §9.1): eşek, ayaklarının `d · px_per_cm` px üstündeki çizginin altında çizilmez.
  `d`, gözlemin `donkey.depth`'idir (kıyıda `None`, 0 sayılır); tick'ler arasında önceki ve şimdiki `d` arasında
  doğrusal geçer. Kuru taşın negatif `d`'si 0'a çekilmez: böylece aynı taşta çizgi tam çizilen suyun hizasındadır
  (`d` çizilen su ile çizilen ayak yüksekliğinin farkıdır). `d ≤ 0` olunca kırpma yoktur. Shrek nehre girmez,
  kırpılmaz.
- **Sürüklenme:** canı azalmışsa (`before.donkey.lives > donkey.lives`, D-07) eşek tick'ler arasında eski
  hücresinden kıyıya kaymaz: doğrudan kıyıdadır ve `RESPAWN` ile belirir. Eski hücresinde **hayalet** oynar
  (§9.3): `SWEPT` klibi, ayakları o hücrenin çizilen taş üstünde (taş yoksa suda), çizilen su seviyesinde
  kırpılır, o hücrenin satırıyla çizilir (önündeki satırların taşları onu örter). Kırpma çizgisi `dx` kaymasıyla
  yer değiştirmez.
- **Nişan:** Shrek'in sütununda `aim_row` hücresinin çerçevesi; uçan yük hedef hücresinde küçük bir gölge (§5,
  iniş noktası gösterilmez).
- **Üst şerit:** kalan süre, skor, can, mod; duraklatmada ve oyun sonunda ortada bir satır.
- Arayüz renkleri `render.palette`'te: `background` (pencere), `bank` (kıyı), `text` (yazı, nişan çerçevesi).

## 5. HUD öğeleri

HUD (Faz 1.8) iki parçadır: saf bir model (`render/hud.py`: gözlemden, moddan ve duvar saatinden sayılar;
pygame yok) ve onu çizen `render/draw.py`. Model `game/view.py`'de kurulur ve Scene'e konur (`Scene.hud`). Her
sayı ya gözlemden ya config'den gelir, kuralı motorun fonksiyonuyla hesaplanır (ör. D-02 `balance`, S-04
`throw_sigma`); HUD kuralı kendisi yeniden yazmaz. Eşikler `render.hud`'dadır. Kesirli sayılar virgüllüdür (§7).

Yerleşim saf `render/hud_layout.py`'dedir (her öğenin dikdörtgeni; boşluklar adlandırılmış px sabitleri), çizim
`render/panels.py`'de. Test: her profilde her öğe kendi panelinin içindedir ve öğeler üst üste binmez. Renkler:
denge çubuğu kademe rengi; heybe kareleri `palette.bank`, en üst yük `palette.text` çerçeveli, karede türün baş
harfi (`ITEM_NAMES`); kütle ve süre çubukları `palette.text`; kıyı yuvaları `palette.bank`, uyarıda
`palette.danger`; bekleme kadranında **hazır olan pay** `palette.dry` (dolu daire = hazır); baraj çubuğu
`palette.water`, yanıp sönerken `palette.danger`; kalpler dolu `palette.danger`, kaybedilen yalnız çerçeve.

**Üst şerit (ortak):** kalan süre (sn, §4.1'deki gibi yukarı yuvarlanmış) ve dolum çubuğu
(`(game_length_ticks − t) / game_length_ticks`), skor, `time.lives` kalp (kalan can dolu, kaybedilen boş), mod
etiketi.

**Eşek paneli:**
- **Denge çubuğu:** δ (D-02), `−δ_max … +δ_max` aralığında yatay çubuk, ortada sıfır çizgisi.
  `δ_max = bag_max_kg_per_side / (bag_max_kg_per_side + mass_kg)`: bir heybe dolu, öteki boşken; δ bu aralığın
  dışına çıkamaz (varsayılanla ≈ 0,23). Gösterge rengi **bir sonraki hareketteki** p_slip'e göre (D-03, motorun
  `slip_risk`'i: kıyıda ve boş heybeyle 0): `hud.slip_prob_tiers = [p₁, p₂, p₃]` için p < p₁ KURU, p < p₂
  BİLEK, p < p₃ DİZ, aksi hâlde TEHLİKE rengi (§3 paleti). Altında `%p` yazılır. Yosunlu taştayken
  "yosun ×μ" (`mossy_slip_multiplier`).
- **Heybeler:** sol ve sağ iki dikey kap. Her kapta `bag_max_volume_per_side` hacim karesi alttan üste dolar:
  her yük hacmi kadar kare kaplar (D-09 yığını, alttaki ilk giren); **en üst yük** (kayınca ya da DİZ'de önce
  düşen, D-03, D-06) açık renk çerçeveyle belirgindir. Yanında kütle çubuğu
  `kütle / bag_max_kg_per_side` ve altında "kg".
- **Derinlik:** durum adı (KURU / BİLEK / DİZ, `depth_state`) + o kademenin renk ve desenli rozeti (§3) +
  sayısal `d` (cm; kıyıda yazılmaz).
- **Duruş:** sol/sağ ok (üçgen, fonttan değil: Noto Sans'ta ok yok, §7) ve kalan duruş süresi çubuğu ile
  saniyesi. Kalan tick `stance_since + stance_max_ticks + 1 − t` (D-08: t₀'da alınan duruş t₀ + 1 …
  t₀ + `stance_max_ticks` tick'lerinde yakalar; gözlemdeki `t` sıradaki tick'tir). Gözlem bir tick'ten sonra
  alındığından gösterilen her duruş sıradaki tick'te yakalar (`stance_ready`); ayrı bir "hazır" parlaklığı yoktur.

**Shrek paneli:**
- **Kıyı kuyruğu:** `bank_capacity` yuva; dolu yuvalar yükün türünün harfiyle. Doluluk payı
  `hud.warn_share`'i **aşınca** yuvalar uyarı rengindedir (`palette.danger`).
- **Sıradaki yük** (kuyruğun başı): tür adı, kg, hacim; şimdiki nişanla σ (S-04 `throw_sigma`) ve tahmini
  yakalama olasılığı `P = 1 − exp(−r²/2σ²)` (MODEL Ek A.3, `r = catch_radius_cells`; eşeğin nişan hücresinde ve
  duruşta olduğu varsayımıyla). Eşek güney kıyısında, Shrek'in sütununda ve duruştaysa atış teslim olur (S-06):
  σ = 0 ve "teslim" yazılır.
- **Bekleme süreleri:** Fırlat ve Kaya at için dairesel dolum, `kalan / *_cooldown_ticks` (süre 0 ise hep hazır);
  aktif geçici taş sayısı (`n / rock_max_active`).
- **Baraj:** `Q / q_max_cm_cols` dikey çubuğu; tutulurken payı `hud.warn_share`'e **ulaşınca** çubuk
  `hud.blink_hz` ile yanıp söner (yarım periyot açık, yarım kapalı; duvar saatiyle). Tutulurken salınım genliği
  tahmini `A = Q / (s·√(2π))` (W-05, motorun `wave_volume`'u).

**Harita üstü** (Faz 1.9, katmanlar):
- **Nişan imleci:** Shrek'in sütununda, `aim_row` hücresinde çerçeve.
- **Belirsizlik halkası:** hedefte 1σ ve 2σ çemberleri (σ sıradaki yükün kütlesiyle). Ayrıca eşeğin
  çevresinde `catch_radius` çemberi. İki halkanın örtüşmesi yakalama şansını sezgisel gösterir.
- **Uçuştaki yük:** tick'ler arası parabol yay; iniş noktasında büyüyen gölge. İniş noktası atış anında
  çekilir ama gösterilmez; gölge hedef hücrede durur (bilgi sızdırmaz).
- **Dalga göstergesi:** batı kenarının dışında, haritaya girmemiş dalgalar için yükseklikle orantılı ok/çentik;
  haritadaki dalga tepesi üstünde ince bir çizgi.
- **Baraj:** c_d sütununun batı kenarında dikey duvar; doğusunda su düzlemi `drop` kadar alçak çizilir.
- **Yüzen yükler:** su yüzeyinde yarım batık ikon, akış yönünde küçük iz.

## 6. Hata ayıklama katmanı (F1, her modda)

- Taş başına sayısal `d` (cm) ve `e` değerleri.
- Dalga tahmini: önümüzdeki 1–5 tick için `L̂(c, t+k)`; yalnızca bilinen dalgaların deterministik
  kinematiğiyle (yeni dalga ve OU gürültüsü yok, `B` sabit varsayılır). Sütun başına küçük çizgi grafiği.
- RNG bilgisi: ana seed, akış başına çekiliş sayacı, `config_hash` kısaltması, `t`, `regen_attempt`.
- Yük tablosu: tüm yüklerin durumu (INV-01'in canlı görünümü).
- `rocks_to_solve` ve 0-1 BFS yolu (yarı saydam çizgi).

## 7. Metin ve font

- Tüm arayüz metinleri Türkçe ve `render/strings_tr.py` içinde tek yerde durur (ADR-007). Buna oyun penceresi,
  metin taktik modu (`tools/tactical.py`, terminal), ghosting testi ve karakter önizleme dahildir. Türkçe Q
  klavyenin `ı`/`İ` girdi çevirisi (`TURKISH_I`) de dile ait veridir, aynı modüldedir.
- **Kural ve testi:** Türkçe harf (ç ğ ı İ ö ş ü, büyükleriyle) içeren her string sabiti yalnız bu modülde
  bulunur. `tests/render/test_strings.py` `engine/`, `render/`, `controllers/`, `game/`, `envs/`, `logs/`,
  `tools/` ve `main.py`'nin sözdizim ağacını tarar; docstring'ler sayılmaz. Testin sınırı: Türkçe harf içermeyen
  Türkçe metin ("Oyun bitti") yakalanamaz, gözden geçirmede bakılır.
- **İstisnalar** (geliştirici raporları, arayüz değil): `tools/bench.py` (hız raporu) ve `tools/design_calcs.py`
  (MODEL.md Ek A'dan alıntılarla eşleşir; alıntı, denetlediği satırın yanında kalmalı).
- Font: **Noto Sans** (SIL OFL 1.1) arayüz metni, **Noto Sans Mono** sayısal katman (F1) için. `assets/fonts/`
  altında projeye dahildir; lisans `assets/fonts/OFL.txt`. Dosyalar notofonts.github.io deposunun `d3abdda`
  commit'indeki `fonts/<Aile>/hinted/ttf/` klasöründen, lisans latin-greek-cyrillic deposunun `0ef9480`
  commit'inden indirildi (2026-10-25). Config: `render.font`, `render.font_mono`.

  | Dosya | Rol | SHA-256 |
  |---|---|---|
  | `NotoSans-Regular.ttf` | arayüz | `478c558ea716033cd60c03438f628dfa75694dcf6b5f6d505a2f05fd2b4f3823` |
  | `NotoSansMono-Regular.ttf` | sayısal | `65b5e2b2c4a1fba9ae8be1f026cb35b03dcb8886d9b2a4147054fde12f7e767d` |
  | `OFL.txt` | lisans | `cee9892f9f0cc8fe882c9e9537ee6a89621d86ee7ceaf70b02e2b2b1c25c061a` |

- **Glif testi** (`tests/render/test_fonts.py`, Faz 1 kabul kriteri): ğ Ğ ş Ş ı İ ç Ç ö Ö ü Ü iki fontta da
  vardır ve `ı`≠`i`, `İ`≠`I` farklı çizilir. Pencerede çizilen her stringin her karakteri Noto Sans'ta vardır.
  Kontrol `pygame.freetype` ile yapılır, çünkü `pygame.font` eksik glif yerine sessizce kutu çizer. Noto Sans'ta
  ok (← →) ve `≥` yoktur; arayüz metninde kullanılmaz. Terminale yazılan taktik mod metinleri (`TACTICAL_`
  önekli) font kullanmadığından bu kontrolün dışındadır.
- Ondalık ayırıcı virgül (`0,6 sn`), yüzde işareti sayının önünde (`%1,5`). Kesirli sayı yazan her şablon
  `strings_tr.tr(şablon, …)` ile doldurulur (`str.format` gibi, ama kesirli alanlarda nokta yerine virgül); tek
  sayı için `strings_tr.decimal(x, basamak)`. **Test** (`tests/render/test_strings.py`): taranan dosyalarda
  kesirli biçim (`f`, `g`, `e`, `%`) içeren bir f-string alanı ya da böyle bir şablona `.format(` çağrısı yoktur.
  İstisna yalnız `tools/design_calcs.py`'dir (MODEL.md'den alıntılarla eşleşir); hız raporu (`tools/bench.py`)
  da virgül kullanır. Terminale basılan config parçası (önizlemede P) YAML olduğu için noktalıdır; o bir şablon
  değil, `yaml` çıktısıdır.

## 8. Kademe 2 — Görsel cila (Faz 1.5)

- Sanat yönü ve palet (Okabe–Ito işlev renkleri korunur; cila yalnızca doku ve ışık ekler).
- Çevre tileset'i: nehir, taşlar, kıyılar (CC0, ör. Kenney) ya da Aseprite / LibreSprite / Piskel ile piksel çizim;
  alternatif olarak kodla prosedürel çizim.
- Yük ikonları (elma kasası, patates çuvalı, karpuz).
- Suyun hafif dalgalanması (sinüs ofseti; §2'den buraya alındı).
- "Juice": su sıçrama parçacıkları, sürüklenmede kısa ekran sarsıntısı, yakalamada küçük ölçek animasyonu.
- Ses: CC0 kütüphaneleri ve sfxr türü üreteçler (atış, yakalama, sıçrama, dalga uğultusu, baraj gıcırtısı).
- Karakterler bu kademenin işi değildir: §9'da, Kademe 1'de çizilirler. Cila karakterlere yalnız "juice"
  ekler (ör. sıçrama parçacıkları); kukla dönüşümleri §9'dadır.

Render katmanı değiştirilebilir (Python `arcade` + shader, web ya da Godot ön yüzü): olay tabanlı mimari
sayesinde motor etkilenmez.

## 9. Karakterler: yerel resimler ve kukla animasyonu (ADR-012)

Shrek ve Eşek, oyuncunun kendi bilgisayarındaki orijinal görüntülerle çizilir. Resimler `assets/private/`
altındadır, git'e **asla** girmez (`.gitignore`; kaynaklar `assets/private/SOURCES.txt`) ve oyun yalnız yerelde
oynanır. Resim yoksa (ör. depoyu yeni klonlayan biri) karakter **soyut şekle** düşer (§9.4). İki durumda da oyun
aynı bilgiyi gösterir: karakter görseli bilgi taşımaz, bilgi renk skalasında, desenlerde ve HUD'dadır.

Kod `render/characters/`'dadır: `pose.py` ve `animator.py` saftır (pygame import etmez, pencere açmadan test
edilir), `sprites.py` resimleri yükler ve çizer (pygame). Konum interpolasyonu `render/interpolation.py`'dadır.

### 9.1 Yöntem: kesik görüntü + kukla dönüşümleri

Her pozun tek bir resmi vardır. Hareket, resme her karede uygulanan bir **dönüşümle** (`Transform`) verilir:

| Alan | Birim | Anlamı |
|---|---|---|
| `image` | — | Hangi poz resmi: Shrek `idle`, `throw`, `dam`; Eşek `idle`, `happy` |
| `dx_px`, `dy_px` | px | Ayak noktasının kayması; ekran ekseni, `dy < 0` yukarı |
| `scale_x`, `scale_y` | oran | Ezilip uzama. Kliplerde alan korunur: `scale_x · scale_y = 1` |
| `angle_deg` | derece | Ayak noktası çevresinde dönme; pozitif saat yönünün tersi (pygame) |
| `alpha` | [0, 1] | Saydamlık; 1 tam görünür |

Bunlara karakter düzeyinde iki şey eklenir:

- **Yön (aynalama):** her resmin baktığı yön config'dedir (`faces: left | right`). Karakter son yatay
  hareketinin yönüne bakar (eşek için `to_cell − from_cell` sütun farkı, Shrek için `to_col − from_col`);
  bakış ile resmin yönü farklıysa resim yatayda aynalanır. Dikey hareket yönü değiştirmez. Oyun başında iki
  karakter de doğuya, akış yönüne bakar.
- **Su çizgisinde kırpma:** eşek nehirde bir taşta dururken su çizgisi ayaklarının `max(0, d) · px_per_cm` px
  üstündedir (§2'deki eğik izdüşümle aynı ölçek, `d` = `donkey.depth`). Bu çizginin altı çizilmez; BİLEK ve DİZ
  derinliği karakterin üstünde de görünür. Kırpma çizgisi zıplamayla (`dy`) birlikte kalkmaz: su yerinde kalır.

**Ayak noktası (`anchor`)** resmin genişlik ve yüksekliğine oranla `(x, y) ∈ [0, 1]²`'dir. Karakter bu noktayla
taşın üst yüzüne (`z = e`) ya da kıyıya oturur; dönme bu nokta çevresindedir. **Ölçek:** resim ekranda
`height_px · scale` px yüksekliğinde çizilir (`height_px` karakter başına, `scale` poz başına çarpan).

**Gerçek zaman ve interpolasyon.** Dönüşümler duvar saatiyle (saniye, 60 FPS) hesaplanır, motorun tick'iyle
değil; motor değişmez (ADR-005). Karakterin konumu tick'ler arasında önceki ve yeni hücre arasında doğrusal
interpolasyonla ilerler: `u = (şimdi − tick_başı) / tick_seconds`, `[0, 1]`'e kırpılır; konum
`önceki + u · (yeni − önceki)`. Klipler konumu taşımaz, yalnız bu konumun üstüne dönüşüm eklerler: aynı tick'te
hareket, kayma ve yakalama olduğunda hangi klip oynarsa oynasın karakter doğru yere gider.

### 9.2 Klipler

Klip, bir pozun zamana bağlı dönüşümüdür: `pose(klip, geçen_süre_s, config) -> Transform`. **Döngü klipleri**
sonsuz sürer; **tek seferlik klipler** süreleri dolunca biter ve karakter döngü klibine döner. `t` klibin
başından geçen süre (s), `u = t / süre` (`[0, 1]`'e kırpılır). Parametreler `render.animation`'dadır.

| Klip | Rol | Resim | Tür | Dönüşüm | Süre |
|---|---|---|---|---|---|
| `IDLE` | ikisi | idle | döngü | nefes: `scale_y = 1 + a·sin(2πt/T)`, `scale_x = 1/scale_y` | — |
| `SCARED` | Eşek | idle | döngü | `IDLE` nefesi + titreme `dx = A·sin(2πft)` | — |
| `WADE` | Eşek | idle | döngü | suda yavaş adım: `dy = −A·\|sin(πt/T)\|` | — |
| `DAM` | Shrek | dam | döngü | zorlanma titremesi `dx = A·sin(2πft)` | — |
| `HOP` | ikisi | idle | tek | uçuş (`t < tick_seconds`, `v = t / tick_seconds`): `dy = −4h·v(1−v)`; iniş (sonraki `land_s`, `w` iniş payı): `scale_y = 1 − q·sin(πw)` | `tick_seconds + land_s` |
| `THROW` | Shrek | throw | tek | kurulma (ilk `r` payı, `w = u/r`): `scale_y = 1 − q·sin(πw/2)`; bırakma (`w = (u−r)/(1−r)`): `scale_y = 1 − q·cos(πw)·(1−w)` (ezik → uzamış → 1) | `throw_s` |
| `SLIP_LEFT`, `SLIP_RIGHT` | Eşek | idle | tek | sendeleme: `angle = ±φ·(1−u)·cos(2πft)`; sola kayışta `+` (saat yönünün tersi) | `slip_s` |
| `HAPPY` | Eşek | happy | tek | zıplama: `dy = −b·\|sin(nπu)\|` | `happy_s` |
| `CHEER` | Shrek | idle | tek | `HAPPY`'nin hareketi | `happy_s` |
| `RESPAWN` | Eşek | idle | tek | belirme: `alpha = u` | `respawn_s` |
| `SWEPT` | Eşek (hayalet) | idle | tek | akışla kayıp solma: `dx = L·u`, `angle = −ψ·u` (akış yönüne devrilir), `alpha = 1 − u` | `swept_s` |

Bütün kliplerde `alpha ∈ [0, 1]`, ölçekler pozitif, değerler sonlu. Tek seferlik bir klip bittiğinde (`u = 1`)
dönüşüm kayma, dönme ve ezilme bakımından nötrdür; yalnız `SWEPT` kaymış ve görünmez biter.

### 9.3 Olay → animasyon

**Döngü klibi durumdan seçilir** (her tick'te `observe` gözleminden; ilk tutan satır):

| Koşul | Eşek | Shrek |
|---|---|---|
| Eşek yavaş harekette (`move_remaining > 0`, D-05) | `WADE` | |
| Eşek DİZ'de (`depth_state = KNEE`, D-04) | `SCARED` | |
| Aksi | `IDLE` | |
| Baraj tutuluyor (`dam.active`, S-08) | | `DAM` |
| Aksi | | `IDLE` |

Döngü durumdan okunur, olaylardan değil: sürüklenen eşek kıyıda yeni bir durumla doğar ve bunun için
`DonkeyDepthChanged` yayılmaz (D-07); durum ise her zaman doğrudur. Döngü klibinin zamanı, döngü klibinin
değiştiği andan sayılır.

**Tek seferlik klip olaylardan seçilir** (EVENTS.md). Bir tick'in olaylarından her karakter için en yüksek
öncelikli klip alınır:

| Olay | Eşek | Shrek | Öncelik | Yön |
|---|---|---|---|---|
| `DonkeyRespawned` | `RESPAWN` | | 4 | |
| `DonkeySlipped(side)` | `SLIP_<side>` | | 3 | |
| `ItemThrown`, `TempStoneSpawned`, `TempStoneRaised` | | `THROW` | 3 | |
| `DonkeyMoved` | `HOP` | | 2 | `to_cell − from_cell` |
| `DonkeyMoveStarted` | (döngü `WADE` olur) | | — | `to_cell − from_cell` |
| `ShrekMoved` | | `HOP` | 2 | `to_col − from_col` |
| `ItemCaught`, `ItemDelivered` | `HAPPY` | `CHEER` | 1 | |
| `DonkeySwept(row, col)` | hayalet `SWEPT` | | ayrı katman | |

- **Kesme:** yeni tick'in klibi oynayan klibi, önceliği **eşit ya da yüksekse** keser; düşükse yok sayılır.
  Kuyruk yoktur, böylece ekran oyunun gerisinde kalmaz. Oynayan klip bitmişse her yeni klip başlar.
- **Hayalet:** sürüklenmede motor eşeği aynı tick'te güney kıyısında yeniden doğurur (D-07). Ekranda ikisi birlikte
  oynar: sürüklendiği hücrede (`DonkeySwept` `row`, `col`) bir hayalet `SWEPT` ile akış yönünde kayıp solar,
  gerçek eşek kıyıda `RESPAWN` ile belirir. Hayaleti hiçbir olay kesmez; yeni bir sürüklenme yenisini başlatır.
  Son can kaybında `DonkeyRespawned` yoktur; yalnız hayalet oynar.

### 9.4 Resim yoksa: soyut şekil

Bir karakterin poz dosyalarından **biri bile** okunamazsa o karakterin bütün pozları soyut şekle düşer (yarı
resim yarı şekil karışımı olmaz); eksik dosyalar listelenir (önizleme aracı, Faz 1'de oyun açılışı). Soyut şekil
`fallback_size_px` boyutunda, ayak noktası alt ortada, doğuya bakan bir yüzeydir; aynı dönüşümler ona da
uygulanır. Shrek: `fallback_color` renginde yuvarlak köşeli kare. Eşek: `fallback_color` renginde daire ve iki
üçgen kulak. İkisinde de doğu tarafında koyu bir göz vardır; simetrik şekilde aynalama (yön) ancak onunla
görünür. Biçim oranları `render/characters/sprites.py`'de adlandırılmış sabitlerdir.

### 9.5 Önizleme aracı

```
uv run python -m tools.character_preview                 # pencere
uv run python -m tools.character_preview --bench         # çizim süresi, karede µs
```

İki karakteri birer taşın üstünde, bir su bandıyla yan yana gösterir ve bütün klipleri sırayla oynatır.
Ölçek ve ayak noktasını ayarlamak içindir; değerleri terminale `default.yaml`'a yapıştırılacak biçimde basar.
Çekirdek `tools/character_preview.py`'nin saf kısmıdır (tuş → ayar, YAML parçası); pencere aynı dosyadadır.

| Tuş | İş |
|---|---|
| Tab | seçili karakter (Shrek / Eşek) |
| ← → | önceki / sonraki klip (otomatik oynatma durur); Boşluk otomatiğe döner |
| PgUp PgDn | seçili poz (`idle`, `throw`, …): ayak noktası ve ölçek bu poza uygulanır |
| + − | `height_px` ±2 |
| A D | ayak noktası x ±0,01 |
| Z X | poz ölçeği (`scale`) ±0,02 |
| W S | su seviyesi ±2 cm (kırpmayı görmek için; derinlik = su − taş üstü) |
| M | iki karakterin yönünü çevir (aynalanmış resmin ayak noktasını görmek için) |
| F1 | ayak noktası artısı ve resim çerçevesi |
| P | seçili karakterin config parçasını terminale bas |
| Esc | çık |

### 9.6 Hız

Bir karede iki karakter ve bir hayalet çizilir. Bütçe: kare başına 16,7 ms'nin (60 FPS) küçük bir parçası,
≤ 1 ms. Ölçüm `uv run python -m tools.character_preview --bench`: 600 kare boyunca bütün klipler sırayla, eşek
ve hayalet su çizgisinde kırpılarak, 5 tekrarın en iyisi.

| Tarih | Görünüm | Kare başına | Bütçenin payı |
|---|---|---|---|
| 2026-10-25 | resimler (Shrek 120 px, Eşek 88 px) | ≈ 240 µs | %1,4 |
| 2026-10-25 | soyut şekiller | ≈ 50 µs | %0,3 |

Maliyetin çoğu her karede yeniden yapılan ölçek (`smoothscale`) ve dönmedir (`rotozoom`); bütçe aşılırsa ilk
aday, dönüşümü nicemleyip (ör. 1° ve %1 adımlar) sonucu önbelleğe almaktır.
