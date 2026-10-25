"""VISUALS §3: the safety-margin palette and the colour science that checks it. Pure: numpy, no pygame.

Colours are sRGB in [0, 1] (numpy arrays, a single colour or an image of shape (..., 3)). Colour-blindness is
simulated with Machado, Oliveira & Fernandes (2009), "A Physiologically-based Model for Simulation of Color Vision
Deficiency", IEEE TVCG 15(6), matrices for severity 1.0, applied to linear sRGB. Differences are CIE76 in CIELAB
(D65 white).
"""

from enum import StrEnum

import numpy as np

from engine.config import PaletteConfig
from engine.events import DepthState


class Vision(StrEnum):
    NORMAL = "normal"
    PROTAN = "protan"       # protanopia
    DEUTAN = "deutan"       # deuteranopia
    TRITAN = "tritan"       # tritanopia


MACHADO_2009 = {  # severity 1.0, as published with the paper (dichromacy)
    Vision.PROTAN: np.array([[0.152286, 1.052583, -0.204868],
                             [0.114503, 0.786281, 0.099216],
                             [-0.003882, -0.048116, 1.051998]]),
    Vision.DEUTAN: np.array([[0.367322, 0.860646, -0.227968],
                             [0.280085, 0.672501, 0.047413],
                             [-0.011820, 0.042940, 0.968881]]),
    Vision.TRITAN: np.array([[1.255528, -0.076749, -0.178779],
                             [-0.078411, 0.930809, 0.147602],
                             [0.004733, 0.691367, 0.303900]]),
}
MIN_DELTA_E = 10.0           # VISUALS §3: told apart at a glance (CIE76; the just-noticeable difference is ≈ 2.3)

TIERS = (DepthState.DRY, DepthState.ANKLE, DepthState.KNEE, DepthState.SWEPT)   # §3 table order: by danger
TIER_PALETTE = {DepthState.DRY: "dry", DepthState.ANKLE: "ankle", DepthState.KNEE: "knee", DepthState.SWEPT: "danger"}

# sRGB (IEC 61966-2-1) and CIELAB constants
SRGB_KNEE, SRGB_SLOPE, SRGB_OFFSET, SRGB_GAMMA = 0.04045, 12.92, 0.055, 2.4
LINEAR_KNEE = 0.0031308
SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                        [0.2126729, 0.7151522, 0.0721750],
                        [0.0193339, 0.1191920, 0.9503041]])
D65_WHITE = np.array([0.95047, 1.0, 1.08883])
LAB_EPSILON = (6 / 29) ** 3
LAB_KAPPA = 3 * (6 / 29) ** 2
HEX_DIGITS = 255


def rgb(hex_colour: str) -> np.ndarray:
    """'#RRGGBB' → sRGB in [0, 1]."""
    return np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]) / HEX_DIGITS


def to_linear(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    return np.where(c <= SRGB_KNEE, c / SRGB_SLOPE, ((c + SRGB_OFFSET) / (1 + SRGB_OFFSET)) ** SRGB_GAMMA)


def to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    return np.where(c <= LINEAR_KNEE, c * SRGB_SLOPE,
                    (1 + SRGB_OFFSET) * np.power(np.maximum(c, LINEAR_KNEE), 1 / SRGB_GAMMA) - SRGB_OFFSET)


def simulate(c: np.ndarray, vision: Vision) -> np.ndarray:
    """What a dichromat sees: Machado 2009 on linear sRGB, clipped to the gamut. NORMAL changes nothing."""
    c = np.asarray(c, dtype=float)
    if vision is Vision.NORMAL:
        return c
    linear = to_linear(c) @ MACHADO_2009[vision].T
    return to_srgb(np.clip(linear, 0.0, 1.0))


def lab(c: np.ndarray) -> np.ndarray:
    """sRGB → CIELAB (D65)."""
    t = (to_linear(c) @ SRGB_TO_XYZ.T) / D65_WHITE
    f = np.where(t > LAB_EPSILON, np.cbrt(t), t / LAB_KAPPA + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e(a: np.ndarray, b: np.ndarray) -> float:
    """CIE76: the distance in CIELAB."""
    return float(np.linalg.norm(lab(a) - lab(b)))


def blend(top: np.ndarray, below: np.ndarray, alpha: float) -> np.ndarray:
    """`top` drawn over `below` with opacity alpha (the water over a stone)."""
    return alpha * np.asarray(top) + (1 - alpha) * np.asarray(below)


def tier_colour(palette: PaletteConfig, tier: DepthState) -> str:
    return getattr(palette, TIER_PALETTE[tier])
