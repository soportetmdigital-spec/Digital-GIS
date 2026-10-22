"""Ajustes propios de Fiber GIS y mantenimiento de datos auxiliares."""

import ast
import base64
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

BACKUP_FORMAT = 2


class FiberGisSettingsWizard(models.TransientModel):
    _name = "fiber.gis.settings.wizard"
    _description = "Ajustes de Fiber GIS"

    module_version = fields.Char(
        string="Version del modulo",
        default=lambda self: self._module_version(),
        readonly=True,
    )
    map_detail_zoom = fields.Float(
        string="Zoom para datos completos",
        default=0.67,
        digits=(3, 2),
        help="Nivel de zoom a partir del cual se muestran los iconos y nombres completos en el mapa.",
    )
    backup_file = fields.Binary(string="Archivo de backup")
    backup_filename = fields.Char(string="Nombre del backup")
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
        """Completa los valores iniciales del formulario con los valores por defecto del modelo."""
        values = super().default_get(fields_list)
        parameters = self.env["ir.config_parameter"].sudo()
        values["fiber_gis_nominatim_url"] = parameters.get_param(
            "fiber_gis.nominatim_url",
            "https://nominatim.openstreetmap.org",
        )
        values["fiber_gis_nominatim_email"] = parameters.get_param(
            "fiber_gis.nominatim_email", ""
        )
        values["module_version"] = self._module_version()
        raw_zoom = parameters.get_param("fiber_gis.map_detail_zoom", "0.67")
        try:
            values["map_detail_zoom"] = min(max(float(raw_zoom), 0.1), 10.0)
        except (TypeError, ValueError):
            values["map_detail_zoom"] = 0.67
        return values

    @api.model
    def _module_version(self):
        """Lee la versión declarada en el manifiesto del módulo."""
        manifest_path = Path(__file__).resolve().parents[1] / "__manifest__.py"
        try:
            manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            return "unknown"
        return manifest.get("version", "unknown")

    def _check_fiber_gis_manager(self):
        """Reserva los ajustes y las copias de seguridad al perfil Responsable."""
        if not self.env.user.has_group("fiber_gis.group_fiber_gis_manager"):
            raise AccessError("Solo los responsables de Fiber GIS pueden usar los ajustes y las copias de seguridad.")

    def action_save_settings(self):
        """Ejecuta la acción de usuario «guardado ajustes» y devuelve el resultado correspondiente a Odoo."""
        self._check_fiber_gis_manager()
        self.ensure_one()
        nominatim_url = (self.fiber_gis_nominatim_url or "").strip().rstrip("/")
        parsed_url = urlparse(nominatim_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise UserError("Indica una URL valida para el servicio Nominatim.")
        try:
            detail_zoom = float(self.map_detail_zoom)
        except (TypeError, ValueError):
            raise UserError("Indica un nivel de zoom valido.")
        if not 0.1 <= detail_zoom <= 10.0:
            raise UserError("El nivel de zoom debe estar entre 0,10 y 10,00.")
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_param("fiber_gis.nominatim_url", nominatim_url)
        parameters.set_param(
            "fiber_gis.nominatim_email",
            (self.fiber_gis_nominatim_email or "").strip(),
        )
        parameters.set_param("fiber_gis.google_maps_api_key", "")
        parameters.set_param("fiber_gis.map_detail_zoom", f"{detail_zoom:.2f}")
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
        """Ejecuta la acción de usuario «actualización CTO colores» y devuelve el resultado correspondiente a Odoo."""
        self._check_fiber_gis_manager()
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
        """Ejecuta la acción de usuario «recalcular fibra estados» y devuelve el resultado correspondiente a Odoo."""
        self._check_fiber_gis_manager()
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
        """Genera una copia ZIP de los datos propios del módulo y la ofrece para descargar."""
        self.ensure_one()
        self._check_fiber_gis_manager()
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

    def action_restore_backup(self):
        """Valida y restaura la copia de datos seleccionada."""
        self.ensure_one()
        self._check_fiber_gis_manager()
        if not self.backup_file:
            raise UserError("Selecciona un archivo de backup antes de restaurar.")
        try:
            backup_content = base64.b64decode(self.backup_file)
        except Exception as error:
            raise UserError("El archivo de backup no es valido.") from error
        restored_records = self._restore_backup_zip(backup_content)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Backup restaurado",
                "message": f"Se han restaurado {restored_records} registros desde la copia de seguridad.",
                "type": "success",
                "sticky": False,
            },
        }

    def _build_backup_zip(self):
        """Genera un archivo ZIP con los datos de Fiber GIS seleccionados para la copia."""
        now = datetime.utcnow()
        backup_name = f"fiber_gis_backup_{now.strftime('%Y%m%d_%H%M%S')}.zip"
        buffer = io.BytesIO()
        metadata = {
            "format": BACKUP_FORMAT,
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
        """Añade al ZIP los archivos necesarios para identificar la versión y estructura del módulo."""
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
        """Escribe en la copia los registros seleccionados, respetando las relaciones entre modelos."""
        for model_name in self._backup_model_names():
            try:
                model = self.env[model_name].sudo().with_context(active_test=False)
            except KeyError:
                continue
            fields_to_export = self._backup_fields(model)
            binary_fields = [name for name in fields_to_export if model._fields[name].type == "binary"]
            records = model.search([]).read(fields_to_export)
            for record in records:
                for field_name in binary_fields:
                    value = record.get(field_name)
                    if isinstance(value, (bytes, bytearray, memoryview)):
                        record[field_name] = bytes(value).decode("ascii")
            metadata["models"][model_name] = {
                "count": len(records),
                "fields": fields_to_export,
            }
            archive.writestr(
                f"data/{model_name.replace('.', '_')}.json",
                json.dumps(records, ensure_ascii=False, indent=2, default=str),
            )

    def _backup_fields(self, model):
        """Determina qué campos de un modelo se incluyen en la copia de seguridad."""
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
        for field_name, field in sorted(model._fields.items()):
            if field_name in skipped_fields or field_name == "id":
                continue
            if self._is_restorable_field(field):
                fields_to_export.append(field_name)
        return fields_to_export

    @api.model
    def _is_restorable_field(self, field):
        """Indica si el valor del campo se guarda en la copia y se vuelve a escribir al restaurar.

        Los campos calculados de solo lectura (incluidos los related) se recalculan solos, y las
        relaciones one2many se reconstruyen desde el many2one del modelo hijo.
        """
        if not field.store or field.type == "one2many":
            return False
        return not (field.compute and field.readonly)

    def _backup_model_names(self):
        """Devuelve los modelos de Fiber GIS que forman parte de la copia, en orden de restauración.

        Los splitters y sus salidas se restauran antes que las líneas de bandeja para que cada
        línea de splitter se cree ya enlazada a su splitter y pase las validaciones de fibras.
        """
        return [
            "fiber.gis.cable.profile",
            "fiber.gis.asset.type",
            "fiber.gis.node.category",
            "fiber.gis.manhole.type",
            "fiber.gis.site",
            "fiber.gis.deployment.plan",
            "fiber.gis.node",
            "fiber.gis.node.photo",
            "fiber.gis.splice.document",
            "fiber.gis.port",
            "fiber.gis.cable",
            "fiber.gis.cable.segment",
            "fiber.gis.cable.fiber",
            "fiber.gis.logical.link",
            "fiber.gis.tray",
            "fiber.gis.splitter",
            "fiber.gis.splitter.output",
            "fiber.gis.tray.line",
            "fiber.gis.cabinet.catalog",
            "fiber.gis.cabinet",
            "fiber.gis.cabinet.equipment",
            "fiber.gis.cabinet.port",
            "fiber.gis.cabinet.interconnection",
            "fiber.gis.node.work.log",
        ]

    def _restore_backup_zip(self, backup_content):
        """Lee la copia ZIP y restaura sus registros resolviendo de nuevo las relaciones entre modelos."""
        try:
            archive = zipfile.ZipFile(io.BytesIO(backup_content), "r")
        except zipfile.BadZipFile as error:
            raise UserError("El archivo no es una copia de seguridad valida.") from error

        with archive:
            try:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except KeyError as error:
                raise UserError("La copia no contiene el manifest de restauracion.") from error

            backup_data = {}
            for model_name in self._backup_model_names():
                data_path = f"data/{model_name.replace('.', '_')}.json"
                try:
                    backup_data[model_name] = json.loads(archive.read(data_path).decode("utf-8"))
                except KeyError:
                    continue
        if not backup_data:
            raise UserError("La copia no contiene datos de Fiber GIS.")

        env = self.with_context(
            active_test=False,
            fiber_gis_restore=True,
            skip_fiber_gis_work_log=True,
            skip_fiber_gis_auto_photo_fetch=True,
            skip_segment_sync=True,
            skip_cable_segment_json=True,
            skip_tray_line_unlink=True,
            skip_splitter_unlink=True,
            skip_fiber_gis_code_check=True,
            fiber_gis_unlink_expanded=True,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
        ).sudo().env
        self._check_restore_coverage(env, manifest, backup_data)
        self._clear_backup_models(env, backup_data)

        # Solo los modelos incluidos en la copia se resuelven por id_map; el resto conserva sus ids.
        id_map = {model_name: {} for model_name in backup_data}
        pending_updates = []
        restored_records = 0
        for model_name in self._backup_model_names():
            if model_name not in backup_data:
                continue
            model = env[model_name]
            for record in backup_data[model_name]:
                old_id = record.get("id")
                values, pending = self._prepare_restore_values(model, record, id_map)
                created = model.create(values)
                restored_records += 1
                if old_id is not None:
                    id_map[model_name][old_id] = created.id
                if pending:
                    # Conserva técnico y fecha originales: algunos write() los rellenan si faltan.
                    for work_field in ("employee_id", "work_date"):
                        if work_field in values:
                            pending.setdefault(work_field, values[work_field])
                    pending_updates.append((model_name, created.id, pending))

        for model_name, record_id, values in pending_updates:
            translated = self._translate_restore_values(env[model_name], values, id_map)
            if translated:
                env[model_name].browse(record_id).write(translated)

        return restored_records

    def _check_restore_coverage(self, env, manifest, backup_data):
        """Impide que una copia antigua borre datos actuales que no contiene."""
        if manifest.get("format", 1) >= BACKUP_FORMAT:
            return
        at_risk = []
        if "fiber.gis.node" in backup_data and "fiber.gis.splice.document" not in backup_data:
            if env["fiber.gis.splice.document"].search_count([]):
                at_risk.append("cartas de empalme")
        if "fiber.gis.cable.fiber" in backup_data and "fiber.gis.cabinet.port" not in backup_data:
            if env["fiber.gis.cabinet.port"].search_count([("fiber_id", "!=", False)]):
                at_risk.append("fibras asignadas a puertos de cabecera")
        if "fiber.gis.node" in backup_data and "fiber.gis.deployment.plan" not in backup_data:
            if env["fiber.gis.deployment.plan"].search_count([]):
                at_risk.append("elementos y cables de los planes de despliegue")
        if at_risk:
            raise UserError(
                "Esta copia es de un formato anterior y no incluye: " + ", ".join(at_risk) + ". "
                "Restaurarla borraria esos datos actuales. Crea una copia nueva desde esta version "
                "o retira esos datos antes de restaurar."
            )

    def _clear_backup_models(self, env, backup_data):
        """Elimina los datos de los modelos incluidos en la copia antes de restaurarlos."""
        for model_name in reversed(self._backup_model_names()):
            if model_name not in backup_data:
                continue
            records = env[model_name].search([])
            if records:
                records.unlink()

    def _prepare_restore_values(self, model, record, id_map):
        """Prepara «restauración valores» y aplica los valores derivados necesarios antes de persistirlos."""
        values = {}
        pending = {}
        for field_name, value in record.items():
            if field_name == "id":
                continue
            field = model._fields.get(field_name)
            if not field or not self._is_restorable_field(field):
                continue
            if field.type == "binary":
                values[field_name] = self._restore_binary_value(value)
                continue
            if field.type == "many2one":
                translated = self._translate_related_id(field, value, id_map)
                if translated is None:
                    pending[field_name] = value
                else:
                    values[field_name] = translated
                continue
            if field.type == "many2many":
                translated = self._translate_many2many(field, value, id_map, strict=True)
                if translated is None:
                    pending[field_name] = value
                else:
                    values[field_name] = translated
                continue
            values[field_name] = value
        return values, pending

    @api.model
    def _restore_binary_value(self, value):
        """Devuelve el contenido base64 de un binario de la copia.

        Las copias anteriores guardaban los bytes con su representación de Python (b'...').
        """
        if not value:
            return False
        if isinstance(value, str) and value.startswith("b'") and value.endswith("'"):
            return value[2:-1]
        return value

    def _translate_restore_values(self, model, values, id_map):
        """Adapta los valores importados a los campos y referencias existentes en esta base de datos."""
        translated = {}
        for field_name, value in values.items():
            field = model._fields.get(field_name)
            if not field:
                continue
            if field.type == "many2one":
                related = self._translate_related_id(field, value, id_map)
                if related is not None:
                    translated[field_name] = related
                continue
            if field.type == "many2many":
                translated[field_name] = self._translate_many2many(field, value, id_map)
                continue
            translated[field_name] = value
        return translated

    def _translate_related_id(self, field, value, id_map):
        """Resuelve un identificador relacionado de la copia con su registro en esta base de datos."""
        if not value:
            return False
        if isinstance(value, (list, tuple)):
            value = value[0] if value else False
        if not value:
            return False
        if field.comodel_name in id_map:
            # Un registro de Fiber GIS se resuelve solo desde la copia: su id antiguo no es válido aquí.
            return id_map[field.comodel_name].get(value)
        if self.env[field.comodel_name].sudo().browse(int(value)).exists():
            return int(value)
        return None

    def _translate_many2many(self, field, value, id_map, strict=False):
        """Convierte las relaciones múltiples de la copia a los identificadores locales de Odoo.

        Con ``strict`` devuelve None si alguna referencia de Fiber GIS aún no se ha restaurado,
        para escribir la relación cuando ya existan todos los registros.
        """
        if not value or not isinstance(value, list):
            return [fields.Command.set([])]
        target_ids = []
        for item in value:
            if isinstance(item, (list, tuple)):
                item = item[0] if item else False
            if not item:
                continue
            translated = self._translate_related_id(field, item, id_map)
            if translated:
                target_ids.append(translated)
            elif strict and field.comodel_name in id_map:
                return None
        return [fields.Command.set(target_ids)]
