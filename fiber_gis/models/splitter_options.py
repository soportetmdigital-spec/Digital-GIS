"""Opciones y cálculos compartidos para relaciones de splitters."""


SPLITTER_RATIO_SELECTION = [
    ("1:2", "1:2"),
    ("1:4", "1:4"),
    ("1:4 Casete", "1:4 Casete"),
    ("1:8", "1:8"),
    ("1:8 Casete", "1:8 Casete"),
    ("1:16", "1:16"),
    ("1:32", "1:32"),
    ("1:64", "1:64"),
]

SPLITTER_DEFAULT_LOSS_DB = {
    "1:2": 3.7,
    "1:4": 7.1,
    "1:4 Casete": 7.1,
    "1:8": 10.4,
    "1:8 Casete": 10.4,
    "1:16": 13.7,
    "1:32": 17.0,
    "1:64": 20.5,
}


def splitter_output_count(ratio):
    """Obtiene el número de salidas, incluso si el valor incluye «Casete»."""
    try:
        output_spec = (ratio or "1:0").split(":", 1)[1].split()[0]
        return int(output_spec)
    except (IndexError, TypeError, ValueError):
        return 0


def splitter_default_loss_db(ratio):
    """Devuelve la pérdida de referencia de la relación seleccionada."""
    return SPLITTER_DEFAULT_LOSS_DB.get(ratio, 0.0)
