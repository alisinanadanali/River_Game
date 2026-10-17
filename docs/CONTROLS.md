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

## 5. Taktik mod

- Her tick, iki oyuncu da bir eylem **onaylayana** kadar bekler. Herhangi bir eylem tuşu o rolün eylemini
  seçip onaylar; "bekle" tuşları (X / `.`) NOOP/NONE'u onaylar.
- Shrek'in bileşenleri taktik modda tek basışta birleşmez. Shrek önce `move`/`aim` tuşlarıyla seçim yapar,
  seçim ekranda gösterilir, sonra bir yetenek tuşu ya da "bekle" tuşu ile onaylar. DAM taktik modda her tick
  yeniden seçilmelidir (basılı tutma yoktur).
- Taktik mod yalnızca zamanlamayı değiştirir; kurallar ve gösterilen bilgi aynıdır. Replay'e
  `tactical_mode` bayrağı yazılır ama sonucu etkilemez.

## 6. Ghosting testi (ROADMAP Faz 0 sonu)

Araç: `tools/ghosting_test.py` (pygame-ce penceresi; anlık basılı scancode'ları ve her tick oluşan iki eylemi
gösterir). Prosedür:

1. Kullanılacak her klavyede (dizüstü dahili, varsa harici) aşağıdaki kombinasyonları en az 3 saniye basılı tut.
2. Her kombinasyon için "tüm tuşlar algılandı mı?" sonucunu tabloya yaz.
3. Başarısız kombinasyon varsa `shrek_alt` düzenini aynı tabloyla test et. Kazanan düzen `default.yaml`'da
   varsayılan yapılır.

| Kombinasyon | Neden kritik | Varsayılan | Yedek |
|---|---|---|---|
| W + ↑ + Sağ Ctrl | Eşek ilerlerken Shrek nişanlayıp atıyor | ☐ | ☐ |
| D + → + Enter | Eşek kaçarken Shrek yürümeye çalışıyor / baraj tutuyor | ☐ | ☐ |
| Q + ↓ + Sağ Shift | Duruş + kaya | ☐ | ☐ |
| W + D + ← + ↑ | Dört yön birden | ☐ | ☐ |
| E + Enter (basılı) + ↑ | Baraj tutarken nişan + duruş | ☐ | ☐ |
| A + S + Sağ Ctrl + Sağ Shift | En kötü durum | ☐ | ☐ |

## 7. Gamepad (kapsam dışı, mimari hazır)

Gamepad, `controllers/gamepad.py` olarak yeni bir controller eklenerek desteklenir. Motor, render ve config
şeması değişmez; yalnızca `controls.devices` altına cihaz eşlemesi eklenir.
