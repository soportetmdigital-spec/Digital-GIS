"""Geometría de recorridos de cable: elementos atravesados y división en tramos.

Funciones puras, sin dependencias de Odoo, para poder probarlas de forma aislada.
"""

import json
import math

# Distancia máxima, en metros, para localizar sobre la ruta un elemento que el usuario ya ha confirmado.
PASS_NODE_LOCATE_MAX_M = 50.0
GRID_CELL_DEG = 0.001


def local_xy(latitude, longitude, reference_latitude):
    """Proyecta una coordenada a metros en un plano local, suficiente para distancias cortas."""
    return (
        longitude * 111320.0 * math.cos(math.radians(reference_latitude)),
        latitude * 110540.0,
    )


def point_segment_distance(point, start, end, reference_latitude):
    """Devuelve la distancia en metros del punto al segmento y la posición relativa (0-1) sobre él."""
    px, py = local_xy(point[0], point[1], reference_latitude)
    ax, ay = local_xy(start[0], start[1], reference_latitude)
    bx, by = local_xy(end[0], end[1], reference_latitude)
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if not length_sq else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), t


def route_candidates(points, node_points, tolerance_m):
    """Elementos a menos de ``tolerance_m`` del recorrido, ordenados a lo largo de la ruta.

    ``points`` es la lista de vértices (lat, lon) y ``node_points`` un iterable de (clave, lat, lon).
    Devuelve dicts con la clave, el segmento, la posición en el segmento y la distancia.
    """
    if len(points) < 2:
        return []
    reference_latitude = sum(point[0] for point in points) / len(points)
    best = {}
    for key, latitude, longitude in node_points:
        for index, (start, end) in enumerate(zip(points, points[1:])):
            distance, t = point_segment_distance((latitude, longitude), start, end, reference_latitude)
            if distance <= tolerance_m and (key not in best or distance < best[key]["distance"]):
                best[key] = {"key": key, "segment": index, "t": t, "distance": distance, "point": (latitude, longitude)}
    return sorted(best.values(), key=lambda item: (item["segment"], item["t"]))


def split_route(points, kinds, passes):
    """Parte el recorrido en los elementos de paso y devuelve [(vértices, tipos de tramo)] por cable.

    ``passes`` son resultados de :func:`route_candidates` ya ordenados. Cada tramo termina en la
    coordenada del elemento y el siguiente empieza en ella.
    """
    by_segment = {}
    for item in passes:
        by_segment.setdefault(item["segment"], []).append(item)
    pieces = []
    current_points, current_kinds = [tuple(points[0])], []

    def add(point, kind):
        if tuple(point) == current_points[-1]:
            return
        current_points.append(tuple(point))
        current_kinds.append(kind)

    for index in range(len(points) - 1):
        kind = kinds[index] if index < len(kinds) else (kinds[-1] if kinds else "underground")
        for item in sorted(by_segment.get(index, []), key=lambda value: value["t"]):
            add(item["point"], kind)
            pieces.append((current_points, current_kinds))
            current_points, current_kinds = [tuple(item["point"])], []
        add(points[index + 1], kind)
    pieces.append((current_points, current_kinds))
    return pieces


def geometry_json(points):
    """GeoJSON LineString con los vértices (lat, lon) recibidos."""
    return json.dumps({
        "type": "LineString",
        "coordinates": [[round(point[1], 7), round(point[0], 7)] for point in points],
    })
