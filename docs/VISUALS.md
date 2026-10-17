# Görsel Dil (VISUALS)

Bu oyunda görsellik **bilgi gösterimidir**. Oyuncular kararlarını su seviyesi ile taş yüksekliği arasındaki
farktan, yaklaşan dalgadan, atış belirsizliğinden ve dengeden okur. Render katmanı yalnızca `state` ve `events`
okur, motora hiçbir şey yazmaz (ADR-005). Teknoloji: pygame-ce, 60 FPS, tick'ler arası interpolasyon (ADR-002).

## 1. Kademe ayrımı

| Kademe | Faz | Kapsam |
|---|---|---|
| **1 — İşlevsel görünüm** | Faz 1 (ilk oyun testinden önce) | Bu belgedeki her şey; soyut şekiller, düz renkler, desenler, Türkçe metin |
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
- Taş: üst yüzü `z = e_i` (ya da boşken `h_i + r_i`) yüksekliğinde bir dikdörtgen, ön yüzü su seviyesine kadar
  uzanan daha koyu bir şerit (prizma). Üst yüzün su çizgisine göre konumu güvenlik payını doğrudan gösterir.
- Su: her sütunda `z = L(c,t)` yüksekliğinde yarı saydam (alfa ≈ 0,55) bir düzlem. Sütunlar arası doğrusal
  geçiş, dalga profilini görünür kılar. Hafif dalgalanma animasyonu yalnız Kademe 1'in sinüs ofsetidir.
- Çizim sırası: kuzeyden güneye (arkadan öne) satır satır; her hücrede taş → su → yük/eşek.
- Kıyılar: kuzey ve güney kenarında tam genişlikte koyu toprak şeritleri.

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

- Su: `#0072B2` (mavi), saydam. Kuru taşların yeşili ile çakışmaz.
- Yosunlu taş: üst yüzde dalgalı "≈" işareti ve koyu kontur.
- Geçici taş: kesikli kontur ve üst yüzde kalan ömür çubuğu (`h − rock_vanish_h_cm`).
- Kademeler arası geçişte renk, tick interpolasyonuyla yumuşak değişir; kademe sınırı geçildiğinde desen anında değişir.
- Doğrulama: Faz 1'de ekran görüntüleri deuteranopi/protanopi simülatöründen geçirilir.

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

## 5. HUD öğeleri

**Üst şerit (ortak):** kalan süre (sn ve dolum çubuğu), skor, can kalpleri, mod etiketi.

**Eşek paneli:**
- **Denge çubuğu:** −0,3 … +0,3 aralığında yatay çubuk, ortada sıfır çizgisi. Gösterge rengi bir sonraki
  hareketteki p_slip'e göre (KURU/BİLEK/DİZ/TEHLİKE skalasıyla aynı palet). Yosunlu taştayken çarpan ikonu.
- **Heybeler:** sol/sağ iki dikey kap; kütle dolumu (kg / 60) ve hacim kareleri (4 kutu). En üst yük ikonu
  belirgin (önce o düşer).
- **Derinlik:** durum adı (KURU / BİLEK / DİZ) + desenli rozet + sayısal d (cm).
- **Duruş:** sol/sağ ok ikonu ve kalan duruş süresi; "hazır" (bir tick geçti) durumunda parlak.

**Shrek paneli:**
- **Kıyı kuyruğu:** `bank_capacity` yuva; dolu yuvalar yük ikonu, doluluk %80'i geçince uyarı rengi.
- **Sıradaki yük:** tür, kg, hacim; bu yük için o anki σ ve tahmini yakalama olasılığı (MODEL A.3 formülü).
- **Cooldown'lar:** Fırlat ve Kaya at için dairesel dolum; aktif geçici taş sayısı (`n / rock_max_active`).
- **Baraj:** Q / Q_max dikey çubuğu; %80'de yanıp sönen patlama uyarısı; salınım genliği tahmini (A cm).

**Harita üstü:**
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

- Tüm arayüz metinleri Türkçe ve `render/strings_tr.py` (ya da YAML) içinde tek yerde durur.
- Font: **Noto Sans** (SIL OFL), `assets/fonts/` altında projeye dahil edilir; ğ ş ı İ ç ö ü testi Faz 1
  kabul kriteridir. Sayısal katman için Noto Sans Mono.
- Ondalık ayırıcı virgül (`0,6 sn`).

## 8. Kademe 2 — Görsel cila (Faz 1.5)

- Sanat yönü ve palet (Okabe–Ito işlev renkleri korunur; cila yalnızca doku ve ışık ekler).
- Çevre tileset'i: nehir, taşlar, kıyılar (CC0, ör. Kenney) ya da Aseprite / LibreSprite / Piskel ile piksel çizim;
  alternatif olarak kodla prosedürel çizim.
- Yük ikonları (elma kasası, patates çuvalı, karpuz).
- "Juice": su sıçrama parçacıkları, sürüklenmede kısa ekran sarsıntısı, yakalamada küçük ölçek animasyonu.
- Ses: CC0 kütüphaneleri ve sfxr türü üreteçler (atış, yakalama, sıçrama, dalga uğultusu, baraj gıcırtısı).
- Karakter sprite'ları kapsam dışıdır; Shrek ve Eşek soyut şekil kalır (Shrek: yeşil yuvarlak kare,
  Eşek: gri üçgen kulaklı daire).

Render katmanı değiştirilebilir (Python `arcade` + shader, web ya da Godot ön yüzü): olay tabanlı mimari
sayesinde motor etkilenmez.
