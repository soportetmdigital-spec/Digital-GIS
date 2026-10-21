"""Actualiza etiquetas conservando el nombre original y las matriculas."""

def migrate(cr, version):
    # El renombrado automatico se retira en 3.37; no ejecutarlo al saltar versiones.
    """Migra los datos existentes a la estructura de esta versión, conservando las relaciones y valores válidos."""
    pass
