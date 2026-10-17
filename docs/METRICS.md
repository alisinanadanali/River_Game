# Metrikler (METRICS)

Bütün metrikler olay akışından (EVENTS.md) ve config'den hesaplanır; motor durumuna doğrudan erişmez (ADR-009).
Hesaplayıcı `logs/` katmanında yaşar ve aynı JSONL dosyasından hem canlı oyun sonunda hem de sonradan çalışır.

## 1. Takım skoru

`score = Σ ItemDelivered.points`. Kalan can ve süre skora eklenmez. Oyun sonu ekranında ayrıca gösterilir:
teslim edilen yük sayısı (türlere göre), kalan can, bitiş nedeni (`GameOver.reason`).

## 2. Uyum raporu (oyun sonu)

| # | Gösterge | Tanım (olaylardan) |
|---|---|---|
| U-01 | **Yakalama başarı oranı** | `#ItemCaught(source=flight) / #ItemThrown(kind=THROW)`; türlere ve uzaklığa (`target.row + 1`) göre kırılım. Beklenen değer (MODEL Ek A.3) ile karşılaştırılır: oran / beklenen > 1 → oyuncular gürültünün üstünde koordine. |
| U-02 | **Duruş–atış gecikmesi** | Her `ItemThrown(kind=THROW)` için `lag = t_throw − t_stance`, `t_stance` = aynı uçuş penceresinde (`[t_throw − 4, t_throw + flight]`) son `DonkeyStance(set)` tick'i. Negatif lag: eşek önce durdu (Shrek'i bekledi); pozitif: Shrek önce attı (eşek tepki verdi). Ortalama, medyan ve histogram. |
| U-03 | **Baraj kullanımı: öngörü / tepki / boşa** | Her baraj bölümü (`DamStarted` → `DamReleased`) için: **öngörü**: bölümde ≥ 1 `WaveAbsorbed` var ve `t_absorb − t_start ≥ 2`. **Tepki**: başlangıç anında eşek `c > c_d` sütununda nehirde ve durumu KNEE ya da daha kötüyse, ya da merkezi `[c_d, c_D]` aralığında olan bir dalga varsa (konum `WaveSpawned` kinematiğinden). **Boşa**: ikisi de değil. Ayrıca patlama sayısı (`reason=burst`). |
| U-04 | **Kurtarılan kritik anlar** | Bkz. §3. |
| U-05 | **Kayıp nedenleri** | `ItemLost.reason` dağılımı ile `ItemDropped.cause` → sonradan LOST olanların zinciri. Kategoriler: kıyı taşması, kaçırılan atış (batan / sürüklenip kaybolan), diz, kayma, sürüklenme, sekme (heybe dolu). |
| U-06 | **Tur istatistikleri** | Tur = güney kıyısından ayrılıştan kuzey kıyıya varışa (`DonkeyMoved`). Tur süresi, tur başına teslim puanı, tur başına yakalama. |
| U-07 | **Rol yükü** | Shrek'in yetenek kullanım dağılımı (THROW / ROCK / DAM / boş tick) ve eşeğin durum zamanı (DRY/ANKLE/KNEE oranı). "Komutan oyuncu" belirtisi için ileride tuş girdisi zamanlamasıyla birlikte (Faz 2). |

## 3. Kritik an (U-04)

**Tanım:** Shrek'in bir müdahalesi (ROCK, DAM başlatma ya da sürdürme) yapılmasaydı sonraki H tick içinde
eşeğin sürükleneceği an. Varsayılan H = 3.

**Kesin yöntem (karşı-olgusal, Faz 2):** Gerçek oyunun replay'i, her aday müdahale tick'i τ için çatallanır:
τ'daki Shrek bileşeni NONE yapılır, eşeğin eylemleri aynı bırakılır ve τ … τ + H simüle edilir. Ortak rastgele
sayılar (R-01, R-02) sayesinde su, yük varışı ve kayma çekilişleri iki dalda aynıdır. Karşı-olgusal dalda
`DonkeySwept` varsa ve gerçek dalda yoksa τ **kurtarılan kritik an** sayılır.
Aday tick'ler: `TempStoneSpawned`/`TempStoneRaised` olan tick'ler, `DamStarted` olan tick'ler ve aktif baraj
tick'leri (barajın her tick'i ayrı ayrı değil, bölümün başından itibaren bırakılmış varsayılarak bir kez).

**Yaklaşık yöntem (yalnız olaylardan, canlı ekran için):** müdahale tick'inde ya da sonraki H tick'te eşek KNEE
durumundaysa ya da büyük bir dalga (A ≥ d₂) eşeğin sütununa ≤ H tick uzaktaysa ve H tick içinde `DonkeySwept`
yoksa "olası kurtarış" sayılır. Raporda iki sayı ayrı gösterilir.

## 4. RL ödül şablonları

Ödül fonksiyonu bir olay → sayı eşlemesidir; ağırlıklar `config/*.yaml` içindeki `rewards:` bölümündedir.
Motoru değiştirmeden değiştirilebilir.

| Olay | Anahtar | Varsayılan | Not |
|---|---|---|---|
| `ItemDelivered` | `rewards.delivered_points` | 1,0 × points | Takım skoru ile aynı |
| `ItemCaught` | `rewards.caught` | 0,0 | Şekillendirme: erken eğitimde 0,1 × points |
| `ItemLost` | `rewards.lost` | 0,0 | Ceza: −0,1 × points |
| `LifeLost` | `rewards.life_lost` | 0,0 | Ceza: −2 |
| `ActionRejected` | `rewards.rejected` | 0,0 | Küçük ceza geçersiz eylemleri azaltır |

Varsayılan ödül, takım skorunun ta kendisidir. Şekillendirme kullanılan deneylerde sonuçlar her zaman
şekillendirilmemiş skorla da raporlanır. Potansiyel tabanlı şekillendirme (ör. heybedeki puan × kuzeye
yakınlık) `rewards.potential` ile ayrıca tanımlanabilir (Faz 4).
Çok ajanlı ortamda (PettingZoo) iki ajan aynı takım ödülünü alır. Rol bazlı ödül V1 deneyidir.

## 5. Oturum metrikleri (dengeleme için)

Profil ve parametre ayarı için oyun başına kaydedilir: skor, kalan can, sürüklenme sayısı, kıyı taşması,
ortalama tur süresi, Kaya at kullanımı, harita `rocks_to_solve`. Faz 5'te tavlama benzetimi / GA bu vektör
üzerinde bir hedef (ör. "skor varyansı düşük, ortalama can kaybı ≈ 1") optimize eder.
