# Kontroller (CONTROLS)

Tuşlar karakterle değil **SDL scancode** ile eşlenir (Türkçe Q ve F klavyelerde fiziksel konum aynı kalır).
Eşlemeler `config/default.yaml` → `controls.keymaps` altındadır; kod sabit tuş içermez (ADR-008).
Klavye bir `controller` uygulamasıdır; betik bot, RL politikası ve ileride gamepad aynı arayüzü uygular:
`act(observation) -> action` (ADR-005).

## 1. Varsayılan düzen

| Rol | Fiziksel tuş | SDL scancode | Eylem bileşeni |
|---|---|---|---|
| Eşek | W / A / S / D | 26 / 4 / 22 / 7 | `MOVE_N` / `MOVE_W` / `MOVE_S` / `MOVE_E` |
| | Q / E | 20 / 8 | `STANCE_LEFT` / `STANCE_RIGHT` |
| | X | 27 | `NOOP` (taktik modda "bekle ve onayla") |
| Shrek | ← / → | 80 / 79 | `move = W / E` |
| | ↑ / ↓ | 82 / 81 | `aim = UP / DOWN` |
| | Sağ Ctrl | 228 | `ability = THROW` |
| | Sağ Shift | 229 | `ability = ROCK` |
| | Enter (basılı) | 40 | `ability = DAM` |
| | `.` (Türkçe Q'da Sağ Shift'in solu; ABD'de `/`) | 56 | `NONE` (taktik modda "bekle ve onayla") |

Yön sözleşmesi: ekranda kuzey (karşı kıyı) yukarıda, akış soldan sağa. W kuzeye, yani karşı kıyıya doğru gider.
↑ nişanı Shrek'ten uzaklaştırır.

## 2. Yedek Shrek düzeni (`keymaps.shrek_alt`)

Dizüstü klavyelerde ok tuşları ile Sağ Ctrl/Shift/Enter aynı matris satırlarını paylaşır ve ghosting sık görülür.
Yedek düzen, eşekten yeterince uzakta ama ayrı matris bölgelerinde kalır:

| Tuş | Scancode | Bileşen |
|---|---|---|
| J / L | 13 / 15 | `move = W / E` |
| I / K | 12 / 14 | `aim = UP / DOWN` |
| U | 24 | `THROW` |
| O | 18 | `ROCK` |
| Boşluk (basılı) | 44 | `DAM` |
| M | 16 | `NONE` (taktik onay) |

Hangi düzenin kullanılacağı `controls.shrek_keymap: default | alt` ile seçilir.

## 3. Genel tuşlar

| Tuş | Scancode | İşlev |
|---|---|---|
| F1 | 58 | Hata ayıklama katmanı aç/kapa (her modda) |
| F2 | 59 | Gerçek zamanlı ↔ taktik mod |
| Esc | 41 | Duraklat / menü |
| F5 | 62 | Aynı seed ile yeniden başlat |

## 4. Girdi tamponu (gerçek zamanlı mod)

- Bir tick penceresi (`tick_seconds`, 0,6 sn) boyunca girdiler toplanır; tick sınırında eylem kurulur.
- **Bileşen başına son basış kazanır.** Eşeğin tek bileşeni vardır. Shrek'in üç bileşeni (`move`, `aim`,
  `ability`) bağımsızdır: aynı pencerede ↑ ve Sağ Ctrl'e basmak "nişanı bir artır, sonra fırlat" demektir
  (TICK.md adım 2c → 2d).
- **Basılı tutma tekrarı:** penceredeki son basış yoksa ve bir hareket tuşu tick sınırında basılı ise o eylem
  tekrarlanır (tutarak yürüme). Duruş tuşları (Q/E) tekrar etmez; duruş zaten süreklidir (D-08).
- **Baraj:** tick sınırında Enter basılıysa ya da pencere içinde basıldıysa `ability = DAM` olur. Bu, aynı
  penceredeki THROW/ROCK basışlarını geçersiz kılar. Enter bırakıldığında bir sonraki tick NONE olur ve baraj
  salınır.
- Tampon `controllers/keyboard.py`'de yaşar; motor yalnızca kurulmuş eylemi görür.

### 4.1 Kesin kurallar ve kenar durumları

- **Basış**, tuşun bırakılmış durumdan basılı duruma geçişidir. İşletim sisteminin otomatik tekrarı kullanılmaz;
  zaten basılı bir tuş için gelen ikinci "basıldı" olayı yeni basış sayılmaz.
- **Kısa dokunuş kaybolmaz:** pencere içinde basılıp bırakılan tuş da o pencerenin basışıdır.
- **Tekrar eden tuşlar:** eşeğin `MOVE_*` tuşları; Shrek'in `move` (← →) ve `aim` (↑ ↓) tuşları. Nişan da
  tekrarlar: ↑ basılı tutulursa nişan her tick bir satır ilerler (tutarak nişan kaydırma). Birden çok tekrar eden
  tuş basılıysa **en son basılan** kazanır. Duruş (Q/E), THROW, ROCK ve bekle tuşları tekrar etmez.
- **Bekle tuşları:** eşeğin X tuşu bir basıştır ve `NOOP` seçer; son basış kazandığı için aynı penceredeki
  önceki W'yi geri alır ve o tick tekrarı keser. Shrek'in `.` tuşu gerçek zamanlı modda yok sayılır; yalnız
  taktik onay içindir (§5).
- **Odak kaybı:** pencere odağı kaybedince basılı tuşlar unutulur (bırakma olayları kaybolur, takılı tuş
  kalmasın); penceredeki basışlar kalır. Enter da bırakılmış sayılır, baraj sonraki tick salınır.
- **Rolün tuşu olmayan scancode'lar** (öbür rolün, genel tuşlar, tanımsızlar) o rolün eylemini etkilemez. Genel
  tuşları (§3) tampon değil oyun oturumu işler.
- Shrek'in tuşları `controls.shrek_keymap` ile seçilen düzenden (`shrek_default` ya da `shrek_alt`) gelir.
- **Tampon saftır:** olaylar scancode olarak gelir (`KeyDown`, `KeyUp`, `FocusLost`); `controllers/` pygame'i
  import etmez (ADR-005). pygame olaylarını bu üç türe çevirmek oyun kabuğunun işidir.

## 5. Taktik mod

- Her tick, iki oyuncu da bir eylem **onaylayana** kadar bekler. Herhangi bir eylem tuşu o rolün eylemini
  seçip onaylar; "bekle" tuşları (X / `.`) NOOP/NONE'u onaylar.
- Shrek'in bileşenleri taktik modda tek basışta birleşmez. Shrek önce `move`/`aim` tuşlarıyla seçim yapar,
  seçim ekranda gösterilir, sonra bir yetenek tuşu ya da "bekle" tuşu ile onaylar. DAM taktik modda her tick
  yeniden seçilmelidir (basılı tutma yoktur).
- Taktik mod yalnızca zamanlamayı değiştirir; kurallar ve gösterilen bilgi aynıdır. Replay'e
  `tactical_mode` bayrağı yazılır ama sonucu etkilemez.

### 5.1 Metin taktik modu (Faz 0, `tools/tactical_cli.py`)

```
uv run python -m tools.tactical_cli --seed 42 --profile percolation_edge
```

Pencere yok; iki oyuncu aynı terminalde sırayla yazar. Çekirdek `tools/tactical.py`'dedir (saf, test edilir),
`tools/tactical_cli.py` yalnız terminali bağlar.

- **Her tick:** harita ve paneller basılır, önce eşek sonra Shrek **bir satır** yazar, Enter onaylar ve `step`
  çalışır. Ekrandaki her şey `observe(state, role)`'dan gelir (MODEL §1 O): seed ve iniş noktası görünmez.
  V0'da iki rolün gözlemi aynı olduğu için tek ekran basılır.
- **Tuşlar config'den türer.** Harfler `controls.keymaps` scancode'larından okunur (USB HID: scancode 4 … 29 =
  a … z, 44 = boşluk); kod sabit tuş içermez. Eşek `keymaps.donkey`'yi kullanır. Shrek her zaman
  `keymaps.shrek_alt`'ı kullanır, çünkü ok tuşları, Ctrl ve Shift bir satıra yazılamaz.

| Rol | Satır | Anlamı |
|---|---|---|
| Eşek | `w` `a` `s` `d` | `MOVE_N` / `MOVE_W` / `MOVE_S` / `MOVE_E` |
| | `q` `e` | `STANCE_LEFT` / `STANCE_RIGHT` |
| | `x` ya da boş satır | `NOOP` |
| Shrek | `j` `l` | `move = W / E` |
| | `i` `k` | `aim = UP / DOWN` |
| | `u` `o` boşluk | `ability = THROW / ROCK / DAM` |
| | `m` ya da boş satır | hepsi `NONE` |

- **Shrek'in satırı bileşenleri birleştirir:** bileşen başına en çok bir tuş, sıra önemsiz. Örnek: `li` doğuya
  yürü ve nişanı bir artır; `iu` nişanı artır ve fırlat; tek boşluk barajı tutar (§5'teki gibi her tick yeniden
  seçilir). Aynı bileşene iki tuş (`jl`, `uo`) ya da tanımsız bir harf hatadır: satır yeniden sorulur, tick
  ilerlemez.
- Büyük-küçük harf fark etmez. Türkçe Q klavyede I tuşu `ı` yazar; `ı`, `I` ve `İ` de `i` sayılır.
- **Komutlar** (her iki satırda): `?` yardım, `:q` çık (Ctrl+Z / Ctrl+D da çıkar). Eşek satırında `:N` (ör. `:5`)
  iki oyuncu için N tick bekler; bu, N kez iki boş satır yazmakla aynıdır, arada harita basılmaz, yalnız olaylar.
- **Harita:** kuzey (teslimat) üstte, güney kıyısı altta; su soldan sağa akar. Hücre dört karakterdir:

| Gösterim | Anlamı |
|---|---|
| `~~` | su |
| `..` | kıyı |
| `#K` `mK` `oK` | kalıcı taş / yosunlu taş / geçici taş; ikinci harf eşeğin **o anki yüküyle** basarsa olacağı derinlik (VISUALS §3): `K` KURU, `B` BİLEK, `D` DİZ, `!` sürüklenir |
| `Eş` | eşek |
| `Sh` | Shrek (güney kıyısı); eşekle aynı hücredeyse `Eş` görünür, Shrek'in sütunu panelde |
| `**` | yüzen yük |
| `[  ]` | Shrek'in nişan hücresi |
| `(  )` | uçan bir yükün hedef hücresi (gölge; iniş noktası gizli) |

  Haritanın altındaki satır sütun başına su seviyesi L(c)'dir (cm, W-07). Panellerde süre, skor, can, eşeğin
  derinliği, duruşu, heybeleri ve dengesi, Shrek'in nişanı, cooldown'ları, kıyı kuyruğu, baraj, dalgalar, uçan
  ve yüzen yükler ve son tick'in olayları (EVENTS.md adlarıyla) yazar.
- Oyun `game_over` olunca son durum ve skor basılır, program 0 ile çıkar.

### 5.2 Pencerede taktik onay (Faz 1, `controllers/tactical.py`)

Gerçek zamanlı tampon (§4) yerine çalışır; tuşlar aynı düzendir (`controls.shrek_keymap`). Yalnız basışlar
(§4.1) sayılır: basılı tutma, bırakma ve odak kaybı taktik modda bir şey yapmaz.

- **Eşek:** herhangi bir eşek tuşu (W A S D Q E) o eylemi seçer ve **onaylar**; X `NOOP`'u onaylar.
- **Shrek seçimi:** `move` (← →) ve `aim` (↑ ↓) tuşları onaylamadan seçer; seçim ekranda gösterilir. Bileşen
  başına son basış kazanır (← sonra → = doğu). Seçili tuşa **yeniden basmak seçimi kaldırır** (← ← = yürüme
  yok); onaylamadan önce seçimi geri almanın tek yolu budur.
- **Shrek onayı:** bir yetenek tuşu (THROW, ROCK, DAM) seçimi o yetenekle onaylar; bekle tuşu (`.`) seçimi
  `ability = NONE` ile onaylar. Seçim yoksa `.` "bekle" demektir. Örnekler: `→ ↑ Sağ Ctrl` = doğuya yürü,
  nişanı artır, fırlat; `← .` = yalnız batıya yürü; `.` = bekle.
- **Onay kesindir:** onaylayan rolün o tick'teki sonraki basışları yok sayılır. Hangi rolün önce onayladığı
  önemsizdir.
- İki rol de onaylayınca tick ilerler (`step`); sonraki tick boş başlar: seçimler taşınmaz, DAM her tick
  yeniden seçilir (basılı tutma yoktur).
- Rolün tuşu olmayan scancode'lar (öbür rol, genel tuşlar, tanımsız) o rolü etkilemez; genel tuşları (§3,
  F2 dahil) oyun oturumu işler.
- Pencerede seçim ve onay, metin taktik modundaki tek satırla aynı eylemi verir (§5.1: `li` ↔ L, I, M).

## 6. Ghosting testi (ROADMAP Faz 0 sonu)

Araç: `tools/ghosting_test.py` (pygame-ce penceresi; anlık basılı scancode'ları ve her tick oluşan iki eylemi
gösterir). Prosedür:

1. Kullanılacak her klavyede (dizüstü dahili, varsa harici) aşağıdaki kombinasyonları en az 3 saniye basılı tut.
2. Her kombinasyon için "tüm tuşlar algılandı mı?" sonucunu tabloya yaz.
3. Başarısız kombinasyon varsa `shrek_alt` düzenini aynı tabloyla test et. Kazanan düzen `default.yaml`'da
   varsayılan yapılır.

| Kombinasyon | Neden kritik | Varsayılan | Yedek |
|---|---|---|---|
| W + ↑ + Sağ Ctrl | Eşek ilerlerken Shrek nişanlayıp atıyor | ☑ | — |
| D + → + Enter | Eşek kaçarken Shrek yürümeye çalışıyor / baraj tutuyor | ☑ | — |
| Q + ↓ + Sağ Shift | Duruş + kaya | ☑ | — |
| W + D + ← + ↑ | Dört yön birden | ☑ | — |
| E + Enter (basılı) + ↑ | Baraj tutarken nişan + duruş | ☑ | — |
| A + S + Sağ Ctrl + Sağ Shift | En kötü durum | ☑ | — |

**Sonuç (2026-10-18):** Dizüstü dahili klavye (tek klavye; harici yok). Altı kombinasyonun altısı varsayılan
düzende 3 s kesintisiz algılandı. Yedek düzen testi gerekmedi (— = test edilmedi). Kazanan: `shrek_default`;
`default.yaml` değişmedi. Not: araç şimdilik yalnızca basılı scancode'ları gösteriyor; "her tick oluşan iki
eylem" gösterimi motor ve controller'lar hazır olunca (Adım 4 sonrası) eklenecek.

## 7. Gamepad (kapsam dışı, mimari hazır)

Gamepad, `controllers/gamepad.py` olarak yeni bir controller eklenerek desteklenir. Motor, render ve config
şeması değişmez; yalnızca `controls.devices` altına cihaz eşlemesi eklenir.
