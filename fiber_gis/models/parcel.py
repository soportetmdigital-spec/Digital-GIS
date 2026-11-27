"""Parcelas catastrales con viviendas e inmuebles para dimensionar despliegues."""

import logging
import time
import urllib.error

from odoo import api, fields, models
from odoo.exceptions import UserError

from .catastro_parcels import MAX_AREA_DEG2, USE_LABELS, bbox_cells, fetch, parse_addresses, parse_buildings, wfs_url
from .catastro_parcels import ADDRESSES_WFS_URL, BUILDINGS_WFS_URL

_logger = logging.getLogger(__name__)

HOUSEHOLD_SIZE_PARAM = "fiber_gis.household_size"
DEFAULT_HOUSEHOLD_SIZE = 2.5


class FiberGisParcel(models.Model):
    _name = "fiber.gis.parcel"
    _description = "Parcela catastral"
    _order = "postcode, address, name"

    name = fields.Char(string="Referencia catastral", required=True, index=True, readonly=True)
    address = fields.Char(string="Dirección", readonly=True)
    postcode = fields.Char(string="Código postal", readonly=True, index=True)
    municipality = fields.Char(string="Municipio", readonly=True, index=True)
    latitude = fields.Float(string="Latitud", digits=(10, 7), readonly=True)
    longitude = fields.Float(string="Longitud", digits=(10, 7), readonly=True)
    current_use = fields.Selection(
        [(code, label) for code, label in USE_LABELS.items()], string="Uso principal", readonly=True,
    )
    dwellings = fields.Integer(string="Viviendas", readonly=True, aggregator="sum")
    building_units = fields.Integer(string="Inmuebles", readonly=True, aggregator="sum")
    floor_area = fields.Integer(string="Superficie construida (m²)", readonly=True, aggregator="sum")
    estimated_people = fields.Float(
        string="Personas estimadas", digits=(10, 1), readonly=True, aggregator="sum",
        help="Estimación: viviendas × tamaño medio del hogar configurado en Ajustes. "
             "El Catastro no publica cuántas personas viven en cada parcela.",
    )
    catastro_url = fields.Char(string="Ficha en la Sede del Catastro", readonly=True)
    last_update = fields.Datetime(string="Actualizada", readonly=True)
    deployment_plan_ids = fields.Many2many(
        "fiber.gis.deployment.plan", "fiber_gis_plan_parcel_rel", "parcel_id", "plan_id",
        string="Planes de despliegue",
    )

    _reference_unique = models.Constraint("UNIQUE(name)", "Ya existe una parcela con esta referencia catastral.")

    @api.model
    def _household_size(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(HOUSEHOLD_SIZE_PARAM, DEFAULT_HOUSEHOLD_SIZE)
        try:
            return min(max(float(raw), 0.1), 20.0)
        except (TypeError, ValueError):
            return DEFAULT_HOUSEHOLD_SIZE

    @api.model
    def _store_from_catastro(self, data):
        """Crea o actualiza las parcelas recibidas del Catastro; devuelve los registros afectados."""
        if not data:
            return self.browse()
        household = self._household_size()
        existing = {parcel.name: parcel for parcel in self.search([("name", "in", list(data))])}
        now = fields.Datetime.now()
        to_create, parcels = [], self.browse()
        for reference, values in data.items():
            record_values = {
                "address": values.get("address") or False,
                "postcode": values.get("postcode") or False,
                "municipality": values.get("municipality") or False,
                "latitude": values.get("latitude") or 0.0,
                "longitude": values.get("longitude") or 0.0,
                "current_use": values.get("current_use") if values.get("current_use") in USE_LABELS else False,
                "dwellings": values.get("dwellings") or 0,
                "building_units": values.get("building_units") or 0,
                "floor_area": values.get("floor_area") or 0,
                "estimated_people": round((values.get("dwellings") or 0) * household, 1),
                "catastro_url": values.get("catastro_url") or False,
                "last_update": now,
            }
            if reference in existing:
                existing[reference].write(record_values)
                parcels |= existing[reference]
            else:
                to_create.append(dict(record_values, name=reference))
        return parcels | self.create(to_create)

    @api.model
    def recompute_estimated_people(self):
        """Recalcula las personas estimadas tras cambiar el tamaño medio del hogar."""
        household = self._household_size()
        for dwellings in set(self.search([]).mapped("dwellings")):
            self.search([("dwellings", "=", dwellings)]).write({"estimated_people": round(dwellings * household, 1)})

    def action_open_catastro(self):
        self.ensure_one()
        if not self.catastro_url:
            raise UserError("La parcela no tiene enlace a la Sede del Catastro.")
        return {"type": "ir.actions.act_url", "url": self.catastro_url, "target": "new"}


class FiberGisParcelImport(models.Model):
    _name = "fiber.gis.parcel.import"
    _description = "Importación de parcelas del Catastro"
    _order = "id desc"

    name = fields.Char(string="Zona", required=True)
    state = fields.Selection(
        [("pending", "Pendiente"), ("running", "En curso"), ("done", "Terminada"), ("error", "Con errores")],
        string="Estado", default="pending", required=True, readonly=True,
    )
    west = fields.Float(digits=(10, 7), required=True, readonly=True)
    south = fields.Float(digits=(10, 7), required=True, readonly=True)
    east = fields.Float(digits=(10, 7), required=True, readonly=True)
    north = fields.Float(digits=(10, 7), required=True, readonly=True)
    deployment_plan_id = fields.Many2one("fiber.gis.deployment.plan", string="Plan de despliegue", ondelete="set null", readonly=True)
    cells_total = fields.Integer(string="Celdas", readonly=True)
    cells_done = fields.Integer(string="Celdas procesadas", readonly=True)
    parcels_found = fields.Integer(string="Parcelas", readonly=True)
    dwellings_found = fields.Integer(string="Viviendas", readonly=True)
    message = fields.Text(string="Incidencias", readonly=True)
    progress = fields.Float(string="Avance (%)", compute="_compute_progress")

    @api.depends("cells_total", "cells_done")
    def _compute_progress(self):
        for job in self:
            job.progress = 100.0 * job.cells_done / job.cells_total if job.cells_total else 0.0

    @api.model
    def schedule(self, west, south, east, north, name, plan=None):
        """Programa la importación de las parcelas de un rectángulo en segundo plano."""
        west, east = sorted((float(west), float(east)))
        south, north = sorted((float(south), float(north)))
        if (east - west) * (north - south) > MAX_AREA_DEG2:
            raise UserError("La zona es demasiado grande (más de unos 25 km²). Acerca el mapa o divide el plan.")
        if east - west <= 0 or north - south <= 0:
            raise UserError("La zona no es válida.")
        job = self.sudo().create({
            "name": name, "west": west, "south": south, "east": east, "north": north,
            "deployment_plan_id": plan.id if plan else False,
            "cells_total": len(bbox_cells(west, south, east, north)),
        })
        cron = self.env.ref("fiber_gis.ir_cron_fiber_gis_parcel_import", raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
        return job

    @api.model
    def schedule_from_map(self, west, south, east, north, plan_id=False):
        plan = self.env["fiber.gis.deployment.plan"].browse(int(plan_id or 0)).exists()
        job = self.schedule(west, south, east, north, "Vista del mapa", plan or None)
        return {"id": job.id, "cells": job.cells_total}

    def _process_cell(self, cell, fetcher=fetch):
        """Descarga una celda y guarda sus parcelas; devuelve las parcelas afectadas."""
        self.ensure_one()
        buildings = parse_buildings(fetcher(wfs_url(BUILDINGS_WFS_URL, "BU:Building", cell)))
        if not buildings:
            return self.env["fiber.gis.parcel"]
        addresses = parse_addresses(fetcher(wfs_url(ADDRESSES_WFS_URL, "AD:Address", cell)))
        data = {reference: dict(values, **addresses.get(reference, {})) for reference, values in buildings.items()}
        parcels = self.env["fiber.gis.parcel"].sudo()._store_from_catastro(data)
        if self.deployment_plan_id:
            self.deployment_plan_id.sudo().write({"parcel_ids": [fields.Command.link(parcel.id) for parcel in parcels]})
        return parcels

    @api.model
    def _remaining_cells(self):
        return sum(
            max(job.cells_total - job.cells_done, 0)
            for job in self.search([("state", "in", ("pending", "running"))])
        )

    @api.model
    def _cron_run_imports(self, fetcher=fetch):
        """Procesa celda a celda las importaciones pendientes, guardando el avance tras cada una.

        Con el progreso por lotes de Odoo 19, cada llamada del cron dispone de poco tiempo: se informa
        de las celdas que quedan y Odoo vuelve a llamar hasta terminarlas.
        """
        cron = self.env["ir.cron"]
        for job in self.search([("state", "in", ("pending", "running"))], order="id"):
            cells = bbox_cells(job.west, job.south, job.east, job.north)
            job.state = "running"
            while job.cells_done < len(cells):
                cell = cells[job.cells_done]
                try:
                    parcels = job._process_cell(cell, fetcher)
                    job.write({
                        "parcels_found": job.parcels_found + len(parcels),
                        "dwellings_found": job.dwellings_found + sum(parcels.mapped("dwellings")),
                    })
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                    _logger.warning("Importación de parcelas %s: celda %s no disponible: %s", job.id, cell, error)
                    job.message = (job.message or "") + f"Celda {job.cells_done + 1}: el Catastro no ha respondido ({error}).\n"
                job.cells_done += 1
                if job.cells_done >= len(cells):
                    job.state = "error" if job.message else "done"
                if cron._commit_progress(1, remaining=self._remaining_cells()) <= 0:
                    return
            if job.state == "running":
                job.state = "error" if job.message else "done"
                cron._commit_progress(0, remaining=self._remaining_cells())
