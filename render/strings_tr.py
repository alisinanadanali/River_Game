"""Turkish UI strings (ADR-007), in one place. Identifiers stay English; only what the player reads is here."""

import re
import string

from engine.events import DepthState, Role, Side
from render.characters.pose import Clip


class _Turkish(string.Formatter):
    """str.format, with the fractional fields' decimal point written as a comma (VISUALS §7)."""

    def format_field(self, value, format_spec: str) -> str:
        text = super().format_field(value, format_spec)
        return text.replace(".", DECIMAL_COMMA) if FRACTION_SPEC.search(format_spec) else text


DECIMAL_COMMA = ","
FRACTION_SPEC = re.compile(r"[fFgGeE%]$")   # a format spec that can write a decimal point
_TURKISH = _Turkish()


def tr(template: str, /, **values) -> str:
    """VISUALS §7: template.format(**values) with a decimal comma in the fractional fields."""
    return _TURKISH.format(template, **values)


def decimal(x: float, digits: int) -> str:
    """VISUALS §7: one number with `digits` decimals and a decimal comma."""
    return tr("{x:.{digits}f}", x=x, digits=digits)


# Names of the game's things, shared by every interface
ROLE_NAMES = {Role.SHREK: "Shrek", Role.DONKEY: "Eşek"}
DEPTH_NAMES = {DepthState.DRY: "KURU", DepthState.ANKLE: "BİLEK", DepthState.KNEE: "DİZ", DepthState.SWEPT: "SÜRÜKLENDİ"}
SIDE_NAMES = {Side.LEFT: "sol", Side.RIGHT: "sağ", Side.NONE: "yok"}
ITEM_NAMES = {"apple_crate": "Elma kasası", "potato_sack": "Patates çuvalı", "watermelon": "Karpuz"}
GAME_OVER_REASONS = {"time": "süre doldu", "lives": "can kalmadı"}

# Turkish Q keyboard input: the I key types ı, and "İ".lower() is "i̇" (two code points)
TURKISH_I = str.maketrans({"ı": "i", "İ": "i", "I": "i"})

CLIP_NAMES = {  # VISUALS §9.2
    Clip.IDLE: "duruş (nefes)",
    Clip.SCARED: "korku (DİZ)",
    Clip.WADE: "suda yavaş adım",
    Clip.DAM: "baraj",
    Clip.HOP: "zıplama",
    Clip.THROW: "fırlatma",
    Clip.SLIP_LEFT: "sola sendeleme",
    Clip.SLIP_RIGHT: "sağa sendeleme",
    Clip.HAPPY: "sevinç",
    Clip.CHEER: "sevinç",
    Clip.RESPAWN: "yeniden doğuş",
    Clip.SWEPT: "sürüklenme",
}

# The game window's HUD panels (VISUALS §5)
HUD_BALANCE = "Denge"
HUD_SLIP = "kayma %{p:.1f}"
HUD_MOSSY = "  yosun ×{multiplier:g}"
HUD_BAGS = "Heybeler"
HUD_BAG_MASS = "{mass:g}/{mass_max:g} kg"
HUD_DEPTH = "Derinlik"
HUD_DEPTH_CM = "{name}  d = {depth:.1f} cm"
HUD_STANCE = "Duruş"
HUD_STANCE_LEFT = "{seconds:.1f} sn"
HUD_NO_STANCE = "yok"
HUD_STANCE_NONE = "{stance}: {none}"
HUD_QUEUE = "Kıyı {queued}/{capacity}"
HUD_NEXT = "Sıradaki"
HUD_NEXT_ITEM = "{name}, {mass:g} kg, {volume} hacim"
HUD_NEXT_THROW = "σ = {sigma:.2f} hücre, yakalama %{p:.0f}"
HUD_NEXT_HANDOFF = "teslim (σ = 0)"
HUD_QUEUE_EMPTY = "kuyruk boş"
HUD_COOLDOWNS = "Bekleme"
HUD_THROW = "Fırlat"
HUD_ROCK = "Kaya"
HUD_ROCKS = "geçici taş {active}/{max}"
HUD_DAM = "Baraj"
HUD_DAM_VOLUME = "Q {volume:.0f}/{q_max:g}"
HUD_DAM_WAVE = "dalga {amplitude:.0f} cm"
HUD_DAM_IDLE = "tutulmuyor"

# The bottom bar's event feed (VISUALS §5); reasons in the enums' order
FEED_ARRIVED = "{item} kıyıya geldi"
FEED_HANDOFF = "{item} teslim ediliyor"
FEED_CAUGHT = "Eşek {item} yakaladı ({side} heybe)"
FEED_MISSED = "{item} ıskalandı: {reason}"
FEED_BOUNCED = "{item} {side} heybeye sığmadı"
FEED_RETURNED = "{item} kıyıya döndü"
FEED_DROPPED = "{item} düştü: {reason}"
FEED_LOST = "{item} kayboldu: {reason}"
FEED_DELIVERED = "{item} teslim edildi, +{points}"
FEED_SLIPPED = "Eşek kaydı ({side})"
FEED_SWEPT = "Eşek sürüklendi!"
FEED_LIFE_LOST = "Can gitti, {lives} kaldı"
FEED_DAM_RELEASED = "Baraj bırakıldı: {amplitude:.0f} cm dalga"
FEED_DAM_BURST = "Baraj patladı: {amplitude:.0f} cm dalga"
FEED_WAVE = "Yukarıdan {amplitude:.0f} cm dalga geliyor"
FEED_STONE_VANISHED = "Geçici taş battı"
FEED_REJECTED = "{role}: {reason}"
FEED_JOIN = "  ·  "
MISS_REASONS = {"no_stance": "duruş yok", "stance_too_late": "duruş geç", "out_of_radius": "uzağa düştü",
                "donkey_on_bank": "eşek kıyıda"}
DROP_CAUSES = {"knee": "diz boyu su", "slip": "kayma", "swept": "sürüklenme"}
LOST_REASONS = {"bank_overflow": "kıyı dolu", "sank": "battı", "drifted_off": "akıntıya kapıldı",
                "off_map": "harita dışına düştü"}
REJECT_REASONS = {"cooldown": "bekleme sürüyor", "dam_active": "baraj tutulurken olmaz", "queue_empty": "kuyruk boş",
                  "rock_limit": "geçici taş sınırı dolu", "no_stone": "orada taş yok", "busy_moving": "eşek suda yürüyor",
                  "burst_lock": "baraj kilitli"}

# tools/character_preview.py (VISUALS §9.5)
PREVIEW_TITLE = "Karakter önizleme"
PREVIEW_AUTO = "otomatik"
PREVIEW_MANUAL = "elle"
PREVIEW_FALLBACK = "resim yok, soyut şekil: {files}"
PREVIEW_VALUES = "boy {height:g} px · poz {pose}: ayak ({ax:.2f}, {ay:.2f}), ölçek {scale:.2f}"
PREVIEW_WATER = "su, taşın {depth:+g} cm üstünde"
PREVIEW_HINT = (  # one string per line
    "Tab karakter · Sol/Sağ ok klip · Boşluk otomatik · PgUp/PgDn poz · +/− boy · A/D ayak x · Z/X ölçek",
    "W/S su · M yön · F1 çerçeve · P yazdır · Esc çık",
)
PREVIEW_BENCH = "{us:.0f} µs/kare (iki karakter + hayalet; {kinds}); {fps} FPS bütçesinin %{share:.1f}'i"
PREVIEW_KIND_IMAGE = "resim"
PREVIEW_KIND_SHAPE = "soyut şekil"
PREVIEW_SELECTED = "  «"  # the character the keys tune
PREVIEW_PRINTED = "config parçası terminale yazıldı"

# tools/ghosting_test.py (CONTROLS.md §6), drawn in its window
GHOSTING_TITLE = "Ghosting testi"
GHOSTING_HINT = "Tuşları çubuk dolana kadar basılı tut  ·  F2: başarısız  ·  Esc: çık"
GHOSTING_RELEASE = "Tüm tuşları bırak…"
GHOSTING_DONE = "Bitti. Sonuç tablosu terminalde."
GHOSTING_HELD = "Basılı scancode'lar:"
GHOSTING_REASONS = {  # combo id → "Neden kritik", CONTROLS.md §6 table
    "W+UP+THROW": "Eşek ilerlerken Shrek nişanlayıp atıyor",
    "D+RIGHT+DAM": "Eşek kaçarken Shrek yürümeye çalışıyor / baraj tutuyor",
    "Q+DOWN+ROCK": "Duruş + kaya",
    "W+D+LEFT+UP": "Dört yön birden",
    "E+DAM+UP": "Baraj tutarken nişan + duruş",
    "A+S+THROW+ROCK": "En kötü durum",
}

# tools/tactical.py and tools/tactical_cli.py (CONTROLS.md §5.1): printed to the terminal, no font (VISUALS §7)
TACTICAL_CLI_DESCRIPTION = "Nehir Geçidi, metin taktik modu"
TACTICAL_CLI_PROFILE_HELP = "config/profiles/<ad>.yaml; verilmezse default.yaml"
TACTICAL_CLI_ERROR = "hata: {error}\n"
TACTICAL_DONKEY_PROMPT = "Eşek  > "
TACTICAL_SHREK_PROMPT = "Shrek > "
TACTICAL_GAME_OVER = "Oyun bitti"
TACTICAL_RESULT = TACTICAL_GAME_OVER + " ({reason}). Skor: {score}"
TACTICAL_QUIT = "Çıkıldı."
TACTICAL_HELP = (
    "Eşek: w/a/s/d yürü, q/e duruş (sol/sağ), x ya da boş satır bekle.\n"
    "Shrek: j/l yürü, i/k nişan, u fırlat, o kaya, boşluk baraj; bileşen başına bir tuş (ör. 'li', 'iu'). "
    "m ya da boş satır bekle.\n"
    "Komutlar: ? yardım, :q çık, :N (eşek satırında) iki oyuncu N tick bekler."
)
TACTICAL_BAD_KEY = "! '{key}' tanımlı bir tuş değil"
TACTICAL_ONE_KEY = "! eşek tek tuşla oynar"
TACTICAL_TWO_KEYS = "! aynı bileşene iki tuş: '{a}' ve '{b}'"
TACTICAL_WAIT_ALONE = "! 'm' (bekle) tek başına yazılır"
TACTICAL_SHREK_GLYPH = "Sh"
TACTICAL_DONKEY_GLYPH = "Eş"
TACTICAL_HEADER = "t = {t} / {length}   Skor: {score}   Can: {lives}"
TACTICAL_DONKEY = "Eşek: ({row}, {col})  {depth}  ·  duruş: {stance}{moving}"
TACTICAL_READY = " (hazır)"
TACTICAL_READY_NEXT_TICK = " (bir tick sonra hazır)"
TACTICAL_MOVING = "  ·  yavaş hareket → {target}, {remaining} tick"
TACTICAL_BAGS = "  sol heybe: {left}   sağ heybe: {right}   denge δ = {balance:+.2f}"
TACTICAL_BAG = "{names} ({mass:g}/{max_kg:g} kg, {volume}/{max_volume} hacim)"
TACTICAL_BAG_EMPTY = "boş"
TACTICAL_SHREK = (
    "Shrek: sütun {col}, nişan satırı {aim_row}  ·  fırlat cd {throw_cd}"
    "  ·  kaya cd {rock_cd}  ·  geçici taş {temp}/{temp_max}"
)
TACTICAL_BANK = "  kıyı kuyruğu {queued}/{capacity}: {names}  ·  {next_item}"
TACTICAL_QUEUE_EMPTY = "kuyruk boş"
TACTICAL_NEXT_SIGMA = "sıradaki σ = {sigma:.2f} hücre"
TACTICAL_DAM_HELD = "Baraj: sütun {col}, Q = {volume:.1f} / {q_max:g} cm·sütun"
TACTICAL_DAM_IDLE = "Baraj: tutulmuyor"
TACTICAL_DAM_LOCKED = "  (patladı: DAM bırakılana kadar kilitli)"
TACTICAL_WATER = "Su: B = {base:.1f} cm; dalgalar: {waves}"
TACTICAL_WAVE = "x = {x:.1f} A = {amplitude:.1f} cm"
TACTICAL_DEPTH = " d = {depth:.1f} cm"
TACTICAL_FLOATING = "{name} ({row:.0f}, {x:.2f})"
TACTICAL_NO_WAVES = "yok"
TACTICAL_FLYING = "{name} → {target}, {ticks} tick"
TACTICAL_AIRBORNE = "Uçan: {flying}   Yüzen: {floating}"
TACTICAL_EVENTS = "Olaylar:"

# The game window (main.py, VISUALS §4.1)
CAPTION = "Nehir Geçidi · seed {seed}"
MODE_NAMES = {"realtime": "Gerçek zamanlı", "tactical": "Taktik"}  # game.session.Mode values
TOP_BAR = "Süre {seconds} sn  ·  Skor {score}  ·  Can {lives}  ·  Mod: {mode}"
PAUSED_BANNER = "Duraklatıldı  ·  Esc: sürdür"
GAME_OVER_BANNER = "Oyun bitti: {reason}  ·  Skor {score}  ·  F5: yeniden başla"
MAIN_DESCRIPTION = "Nehir Geçidi: iki oyunculu nehir geçişi (aynı klavye)"
MAIN_SEED_HELP = "harita ve olaylar için seed; verilmezse rastgele seçilir ve pencere başlığında yazar"
MAIN_PROFILE_HELP = "config profili: warmup, percolation_edge, hard"
MAIN_FRAMES_HELP = "bu kadar kare sonra çık (0: pencere kapanana kadar)"

# tools/cvd_shots.py (VISUALS §3), terminal
CVD_SHOTS_DESCRIPTION = "Örnek tahtanın normal görme ve üç renk körlüğü benzetimiyle ekran görüntüleri"
CVD_SHOTS_OUT_HELP = "PNG'lerin yazılacağı klasör"
CVD_SHOTS_WRITTEN = "{n} görüntü yazıldı: {out}"
