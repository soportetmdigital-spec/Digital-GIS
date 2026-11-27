"""Parcelas del Catastro desde sus servicios INSPIRE: edificios (viviendas, inmuebles) y direcciones.

Funciones sin dependencias de Odoo, para poder probarlas con respuestas reales guardadas.
"""

import urllib.error
import urllib.parse
import urllib.request

from lxml import etree

BUILDINGS_WFS_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx"
ADDRESSES_WFS_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsAD.aspx"
USER_AGENT = "FiberGIS/19.0 (Odoo 19)"
# El servicio limita el área de cada consulta; la zona se recorre en celdas de este tamaño (unos 400 m).
CELL_DEG = 0.004
MAX_AREA_DEG2 = 0.0025  # unos 25 km²

USE_LABELS = {
    "1_residential": "Residencial",
    "2_agriculture": "Agrario",
    "3_industrial": "Industrial",
    "4_1_office": "Oficinas",
    "4_2_retail": "Comercial",
    "4_3_publicServices": "Servicios públicos",
}


def _local(element):
    return etree.QName(element).localname


def _children(element, name):
    return [child for child in element if isinstance(child.tag, str) and _local(child) == name]


def _find(element, *path):
    """Primer descendiente que sigue la ruta de nombres locales indicada."""
    current = [element]
    for name in path:
        current = [
            found for item in current for found in item.iter()
            if found is not item and isinstance(found.tag, str) and _local(found) == name
        ]
        if not current:
            return None
    return current[0]


def _text(element, *path):
    found = _find(element, *path) if path else element
    return (found.text or "").strip() if found is not None and found.text else ""


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_xml(payload):
    """Analiza una respuesta XML sin resolver entidades ni acceder a la red."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=True)
    return etree.fromstring(payload, parser=parser)


def parse_buildings(payload):
    """Edificios por referencia catastral de parcela (14 caracteres)."""
    root = parse_xml(payload)
    buildings = {}
    for building in root.iter():
        if not isinstance(building.tag, str) or _local(building) != "Building":
            continue
        reference = _text(building, "inspireId", "localId")[:14]
        if len(reference) != 14:
            continue
        lower = _text(building, "Envelope", "lowerCorner").split()
        upper = _text(building, "Envelope", "upperCorner").split()
        latitude = longitude = 0.0
        if len(lower) == 2 and len(upper) == 2:
            # EPSG::4326 en GML 3.2 va como «latitud longitud».
            latitude = (float(lower[0]) + float(upper[0])) / 2
            longitude = (float(lower[1]) + float(upper[1])) / 2
        current = buildings.get(reference)
        values = {
            "reference": reference,
            "latitude": latitude,
            "longitude": longitude,
            "current_use": _text(building, "currentUse"),
            "dwellings": _int(_text(building, "numberOfDwellings")),
            "building_units": _int(_text(building, "numberOfBuildingUnits")),
            "floor_area": _int(_text(building, "officialArea", "value")),
            "catastro_url": _text(building, "informationSystem"),
        }
        if current:
            # Varias construcciones en la misma parcela: se suman viviendas, inmuebles y superficie.
            for key in ("dwellings", "building_units", "floor_area"):
                current[key] += values[key]
        else:
            buildings[reference] = values
    return buildings


def parse_addresses(payload):
    """Dirección principal por referencia catastral de parcela: calle y número, código postal y municipio."""
    root = parse_xml(payload)
    names, postcodes, municipalities = {}, {}, {}
    xlink = "{http://www.w3.org/1999/xlink}href"
    gml_id = "{http://www.opengis.net/gml/3.2}id"
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        local = _local(element)
        if local == "ThoroughfareName":
            names[element.get(gml_id)] = _text(element, "SpellingOfName", "text")
        elif local == "PostalDescriptor":
            postcodes[element.get(gml_id)] = _text(element, "postCode")
        elif local == "AdminUnitName":
            municipalities[element.get(gml_id)] = _text(element, "SpellingOfName", "text")
    addresses = {}
    for address in root.iter():
        if not isinstance(address.tag, str) or _local(address) != "Address":
            continue
        local_id = _text(address, "inspireId", "localId")
        reference = local_id.rsplit(".", 1)[-1][:14]
        if len(reference) != 14:
            continue
        number = _text(address, "locator", "designator", "designator")
        components = [component.get(xlink, "").lstrip("#") for component in _children(address, "component")]
        street = next((names[key] for key in components if key in names), "")
        postcode = next((postcodes[key] for key in components if key in postcodes), "")
        municipality = next((municipalities[key] for key in components if key in municipalities), "")
        specification = _text(address, "specification")
        entry = {
            "address": " ".join(part for part in (street, "S/N" if number == "S-N" else number) if part),
            "postcode": postcode,
            "municipality": municipality,
        }
        # Se prefiere la dirección de la entrada principal a la genérica de la parcela.
        if reference not in addresses or specification == "Entrance":
            addresses[reference] = entry
    return addresses


def bbox_cells(west, south, east, north, cell=CELL_DEG):
    """Divide un rectángulo en celdas pequeñas (oeste, sur, este, norte)."""
    cells = []
    latitude = south
    while latitude < north:
        longitude = west
        top = min(latitude + cell, north)
        while longitude < east:
            right = min(longitude + cell, east)
            cells.append((longitude, latitude, right, top))
            longitude = right
        latitude = top
    return cells


def wfs_url(base_url, typename, cell):
    west, south, east, north = cell
    return base_url + "?" + urllib.parse.urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typenames": typename,
        # WFS 2.0 con EPSG::4326: el rectángulo va como latitud, longitud.
        "bbox": f"{south:.6f},{west:.6f},{north:.6f},{east:.6f}", "srsname": "EPSG::4326",
    })


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_parcels(west, south, east, north, fetcher=fetch):
    """Parcelas de un rectángulo con sus edificios y direcciones, recorriendo la zona por celdas."""
    parcels = {}
    for cell in bbox_cells(west, south, east, north):
        buildings = parse_buildings(fetcher(wfs_url(BUILDINGS_WFS_URL, "BU:Building", cell)))
        if not buildings:
            continue
        addresses = parse_addresses(fetcher(wfs_url(ADDRESSES_WFS_URL, "AD:Address", cell)))
        for reference, values in buildings.items():
            if reference in parcels:
                continue
            parcels[reference] = dict(values, **addresses.get(reference, {}))
    return parcels
