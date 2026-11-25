"""Utilidades geométricas mínimas."""


def overlap_length(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    """Longitud de la intersección de los intervalos [start_a, end_a] y [start_b, end_b]."""
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))
