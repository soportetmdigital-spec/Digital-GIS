"""Ajustes propios de Fiber GIS y mantenimiento de datos auxiliares."""

import base64
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import UserError


class FiberGisSettingsWizard(models.TransientModel):
    _name = "fiber.gis.settings.wizard"
    _description = "Ajustes de Fiber GIS"

    module_version = fields.Char(
        string="Version del modulo",
        default="19.0.3.37.0",
        readonly=True,
    )
    fiber_gis_nominatim_url = fields.Char(
        string="URL del servicio Nominatim",
        default="https://nominatim.openstreetmap.org",
        help="Servicio compatible con Nominatim utilizado para obtener coordenadas y direcciones.",
    )
    fiber_gis_nominatim_email = fields.Char(
        string="Correo de contacto para Nominatim",
        help="Identifica al responsable de la aplicacion ante el proveedor de geocodificacion.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        parameters = self.env["ir.config_parameter"].sudo()
        values["fiber_gis_nominatim_url"] = parameters.get_param(
            "fiber_gis.nominatim_url",
            "https://nominatim.openstreetmap.org",
        )
        values["fiber_gis_nominatim_email"] = parameters.get_param(
            "fiber_gis.nominatim_email", ""
        )
        return values

    def action_save_settings(self):
        self.ensure_one()
        nominatim_url = (self.fiber_gis_nominatim_url or "").strip().rstrip("/")
        parsed_url = urlparse(nominatim_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise UserError("Indica una URL valida para el servicio Nominatim.")
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_param("fiber_gis.nominatim_url", nominatim_url)
        parameters.set_param(
            "fiber_gis.nominatim_email",
            (self.fiber_gis_nominatim_email or "").strip(),
        )
        parameters.set_param("fiber_gis.google_maps_api_key", "")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Ajustes guardados",
                "message": "Se han guardado los ajustes de Fiber GIS.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_update_cto_colors(self):
        updated = self.env["fiber.gis.node"].action_update_cto_colors()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Colores CTO actualizados",
                "message": f"Se han actualizado {updated} CTO: iluminadas en verde y no iluminadas en rojo.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_recompute_fiber_states(self):
        fibers = self.env["fiber.gis.cable.fiber"].search([])
        for fiber in fibers:
            cable = fiber.cable_id
            color_index = cable._fiber_color_index(fiber.number) if cable else fiber.number
            fiber.write({
                "color": fibers.fiber_color(color_index),
                "tube_color": fibers.fiber_color(fiber.tube) if fiber.tube else False,
            })
        fibers._compute_color_names()
        fibers._recompute_tray_state()
        updated = len(fibers)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Fibras actualizadas",
                "message": (
                    f"Se han revisado {updated} fibras. Se han normalizado sus colores "
                    "y las fibras sin uso en bandejas han quedado libres."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def action_create_backup(self):
        self.ensure_one()
        backup_content, backup_name = self._build_backup_zip()
        attachment = self.env["ir.attachment"].sudo().create({
            "name": backup_name,
            "type": "binary",
            "datas": base64.b64encode(backup_content).decode("ascii"),
            "mimetype": "application/zip",
            "res_model": self._name,
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _build_backup_zip(self):
        now = datetime.utcnow()
        backup_name = f"fiber_gis_backup_{now.strftime('%Y%m%d_%H%M%S')}.zip"
        buffer = io.BytesIO()
        metadata = {
            "created_utc": now.isoformat(timespec="seconds") + "Z",
            "database": self.env.cr.dbname,
            "module_version": self.module_version,
            "models": {},
        }
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            self._write_module_files(archive)
            self._write_model_data(archive, metadata)
            archive.writestr(
                "manifest.json",
                json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
            )
        return buffer.getvalue(), backup_name

    def _write_module_files(self, archive):
        module_root = Path(__file__).resolve().parents[1]
        skipped_parts = {"__pycache__"}
        skipped_suffixes = {".pyc", ".pyo", ".zip"}
        for path in sorted(module_root.rglob("*")):
            if path.is_dir():
                continue
            if skipped_parts.intersection(path.parts) or path.suffix.lower() in skipped_suffixes:
                continue
            archive.write(path, f"module/{path.relative_to(module_root).as_posix()}")

    def _write_model_data(self, archive, metadata):
        for model_name in self._backup_model_names():
            try:
                model = self.env[model_name].sudo().with_context(active_test=False)
            except KeyError:
                continue
            fields_to_export = self._backup_fields(model)
            records = model.search([]).read(fields_to_export)
            metadata["models"][model_name] = {
                "count": len(records),
                "fields": fields_to_export,
            }
            archive.writestr(
                f"data/{model_name.replace('.', '_')}.json",
                json.dumps(records, ensure_ascii=False, indent=2, default=str),
            )

    def _backup_fields(self, model):
        fields_info = model.fields_get()
        skipped_fields = {
            "__last_update",
            "activity_ids",
            "activity_exception_decoration",
            "activity_exception_icon",
            "activity_state",
            "activity_summary",
            "activity_type_icon",
            "activity_type_id",
            "activity_user_id",
            "display_name",
            "has_message",
            "message_attachment_count",
            "message_follower_ids",
            "message_has_error",
            "message_has_error_counter",
            "message_has_sms_error",
            "message_ids",
            "message_is_follower",
            "message_needaction",
            "message_needaction_counter",
            "message_partner_ids",
        }
        fields_to_export = ["id"]
        for field_name, field_info in sorted(fields_info.items()):
            if field_name in skipped_fields or field_name == "id":
                continue
            if field_info.get("type") in {"one2many", "many2many"}:
                fields_to_export.append(field_name)
                continue
            if field_info.get("store", True) or field_info.get("type") == "binary":
                fields_to_export.append(field_name)
        return fields_to_export

    def _backup_model_names(self):
        return [
            "fiber.gis.cable.profile",
            "fiber.gis.asset.type",
            "fiber.gis.node.category",
            "fiber.gis.manhole.type",
            "fiber.gis.site",
            "fiber.gis.node",
            "fiber.gis.node.photo",
            "fiber.gis.port",
            "fiber.gis.cable",
            "fiber.gis.cable.segment",
            "fiber.gis.cable.fiber",
            "fiber.gis.logical.link",
            "fiber.gis.node.work.log",
            "fiber.gis.tray",
            "fiber.gis.tray.line",
            "fiber.gis.splitter",
            "fiber.gis.splitter.output",
        ]
