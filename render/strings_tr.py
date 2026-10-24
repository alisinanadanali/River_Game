"""Turkish UI strings (ADR-007), in one place. Identifiers stay English; only what the player reads is here."""

from engine.events import Role
from render.characters.pose import Clip

ROLE_NAMES = {Role.SHREK: "Shrek", Role.DONKEY: "Eşek"}

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

# tools/character_preview.py (VISUALS §9.5)
PREVIEW_TITLE = "Karakter önizleme"
PREVIEW_AUTO = "otomatik"
PREVIEW_MANUAL = "elle"
PREVIEW_FALLBACK = "resim yok, soyut şekil: {files}"
PREVIEW_VALUES = "boy {height:g} px · poz {pose}: ayak ({ax:.2f}, {ay:.2f}), ölçek {scale:.2f}"
PREVIEW_WATER = "su, taşın {depth:+g} cm üstünde"
PREVIEW_HINT = (
    "Tab karakter · Sol/Sağ ok klip · Boşluk otomatik · PgUp/PgDn poz · +/− boy · A/D ayak x · Z/X ölçek · "
    "W/S su · M yön · F1 çerçeve · P yazdır · Esc çık"
)
PREVIEW_BENCH = "{us:.0f} µs/kare (iki karakter + hayalet; {kinds}); {fps} FPS bütçesinin %{share:.1f}'i"
PREVIEW_KIND_IMAGE = "resim"
PREVIEW_KIND_SHAPE = "soyut şekil"
PREVIEW_SELECTED = "  «"  # the character the keys tune
PREVIEW_PRINTED = "config parçası terminale yazıldı"
