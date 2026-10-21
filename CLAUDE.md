# Digital-GIS — guía para Claude

Repositorio del módulo Odoo `fiber_gis/` (Fiber GIS - Red de Fibra).

## Regla obligatoria

- Objetivo exclusivo: **Odoo 19 Community**. Usar **solo referencias oficiales de Odoo 19 Community**:
  - Documentación: https://www.odoo.com/documentation/19.0/
  - Código fuente: https://github.com/odoo/odoo/tree/19.0
- No usar APIs, sintaxis ni ejemplos de otras versiones de Odoo, de Odoo Enterprise ni de fuentes no oficiales.

## Antes de editar

- Leer `fiber_gis/__manifest__.py`, `fiber_gis/README.md` (manual y fuente de verdad) y
  `fiber_gis/CONTINUIDAD_CODEX_CHATGPT.md` (preferencias permanentes e historial de iteraciones).
- En cada entrega de código: incrementar la versión del manifiesto y sincronizar `models/site.py`,
  pruebas de versión, README y el archivo de continuidad.
- SCSS: no reintroducir `min()` con unidades mixtas ni `aspect-ratio` en `static/src/scss/fiber_map.scss`.

## Chequeos locales (desde `fiber_gis/`)

```
python3 -m unittest discover -s tests -p 'check_*.py'
for f in static/src/js/*.js; do node --check "$f"; done
```

Los `TransactionCase` (`tests/test_*.py`) requieren Odoo 19 Community + PostgreSQL.
