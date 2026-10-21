"""Fotos y cartas de empalme asociadas a elementos de red."""

import base64
import binascii
import html
import io
import zipfile

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .work_log import work_employee_id


def match_splice_node(filename_stem, nodes):
    """Busca una matrícula completa en el nombre del archivo y evita coincidencias parciales."""
    stem = (filename_stem or "").strip().casefold()
    candidates = [(node_id, (code or "").strip().casefold()) for node_id, code in nodes if code]
    exact = {node_id for node_id, code in candidates if stem == code}
    if exact:
        return (next(iter(exact)), "matched") if len(exact) == 1 else (False, "ambiguous")

    separators = " _-.()[]{}"
    matches = []
    for node_id, code in candidates:
        start = 0
        while code and (position := stem.find(code, start)) >= 0:
            end = position + len(code)
            left_ok = position == 0 or stem[position - 1] in separators
            right_ok = end == len(stem) or stem[end] in separators
            if left_ok and right_ok:
                matches.append((node_id, len(code), position))
                break
            start = position + 1
    if not matches:
        return False, "unmatched"
    longest_by_start = {}
    for _node_id, length, position in matches:
        longest_by_start[position] = max(length, longest_by_start.get(position, 0))
    best = {
        node_id
        for node_id, length, position in matches
        if length == longest_by_start[position]
    }
    return (next(iter(best)), "matched") if len(best) == 1 else (False, "ambiguous")


class FiberGisSpliceDocument(models.Model):
    """Guarda fotos y documentos de empalme con el técnico y la fecha de carga."""

    _name = "fiber.gis.splice.document"
    _description = "Foto o carta de empalme"
    _order = "uploaded_at desc, id desc"

    node_id = fields.Many2one("fiber.gis.node", string="Elemento", required=True, ondelete="cascade", index=True)
    kind = fields.Selection(
        [("photo", "Foto"), ("excel", "Carta Excel")],
        string="Tipo",
        required=True,
        default="photo",
        index=True,
    )
    name = fields.Char(string="Nombre", required=True, default="Foto de empalme")
    image_1920 = fields.Image(string="Foto", attachment=True, copy=False)
    file_data = fields.Binary(string="Archivo Excel", attachment=True, copy=False)
    file_name = fields.Char(string="Nombre del fichero")
    comment = fields.Text(string="Comentarios")
    technician_comment = fields.Text(string="Comentario del técnico")
    employee_id = fields.Many2one(
        "hr.employee.public",
        string="Técnico",
        default=lambda self: work_employee_id(self.env),
    )
    uploaded_at = fields.Datetime(string="Fecha de carga", default=fields.Datetime.now, readonly=True, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Completa el nombre y técnico por defecto antes de guardar las evidencias."""
        default_employee_id = work_employee_id(self.env)
        for values in vals_list:
            filename = values.get("file_name") or ""
            if not values.get("name") and filename:
                values["name"] = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
            values.setdefault("employee_id", default_employee_id)
        return super().create(vals_list)

    @api.constrains("node_id", "kind", "image_1920", "file_data", "file_name")
    def _check_splice_document(self):
        """Comprueba que cada elemento con bandejas tenga una foto o un Excel válido."""
        allowed_extensions = {".xls", ".xlsx", ".xlsm", ".xlsb", ".ods"}
        for document in self:
            if not document.node_id.has_trays or document.node_id.node_kind == "ont":
                raise ValidationError("Las cartas de empalme solo se pueden guardar en elementos con bandejas.")
            if document.kind == "photo" and not document.image_1920:
                raise ValidationError("Selecciona una imagen para guardar la foto de empalme.")
            if document.kind == "excel":
                extension = (document.file_name or "").rsplit(".", 1)[-1].lower()
                if not document.file_data or "." not in (document.file_name or "") or f".{extension}" not in allowed_extensions:
                    raise ValidationError("Adjunta una carta de empalme en formato Excel o LibreOffice (.xls, .xlsx, .xlsm, .xlsb u .ods).")


class FiberGisSpliceImportWizard(models.TransientModel):
    """Importa cartas desde ZIP y las asigna al equipo con la matrícula del nombre."""

    _name = "fiber.gis.splice.import.wizard"
    _description = "Importar cartas de empalme"

    archive_data = fields.Binary(string="Archivo ZIP")
    archive_name = fields.Char(string="Nombre del ZIP")
    result_html = fields.Html(string="Resultado", readonly=True, sanitize=False)
    skipped_report = fields.Binary(string="Listado TXT de archivos no importados")
    skipped_report_name = fields.Char(string="Nombre del informe")

    def action_import(self):
        """Lee las hojas de cálculo del ZIP, asigna las coincidencias seguras y devuelve un resumen."""
        self.ensure_one()
        if not self.archive_data:
            raise UserError("Selecciona un archivo ZIP con las cartas de empalme.")
        try:
            archive_data = base64.b64decode(self.archive_data, validate=True)
            if len(archive_data) > 50 * 1024 * 1024:
                raise UserError("El ZIP supera el máximo permitido de 50 MB.")
            archive = zipfile.ZipFile(io.BytesIO(archive_data))
        except (ValueError, binascii.Error, OSError, zipfile.BadZipFile):
            raise UserError("El archivo seleccionado no es un ZIP válido.") from None

        with archive:
            entries = archive.infolist()
            if len(entries) > 5000:
                raise UserError("El ZIP contiene demasiados archivos; el máximo es 5000.")
            spreadsheet_entries = [
                entry for entry in entries
                if not entry.is_dir() and entry.filename.lower().endswith((".xls", ".xlsx", ".xlsm", ".xlsb", ".ods"))
            ]
            if not spreadsheet_entries:
                raise UserError("El ZIP no contiene hojas de cálculo (.xls, .xlsx, .xlsm, .xlsb u .ods).")

            node_model = self.env["fiber.gis.node"]
            nodes = node_model.search([
                ("node_kind", "!=", "ont"),
                "|",
                ("code", "!=", False),
                ("name", "!=", False),
            ])
            node_by_id = {node.id: node for node in nodes}
            node_codes = [
                (node.id, value)
                for node in nodes
                for value in {node.code, node.name}
                if value
            ]
            document_model = self.env["fiber.gis.splice.document"]
            matched_entries = []
            report_items = []
            duplicate_items = []
            expanded_size = 0
            duplicate_count = 0

            for entry in spreadsheet_entries:
                normalized_path = entry.filename.replace("\\", "/")
                parts = normalized_path.split("/")
                if normalized_path.startswith("/") or ".." in parts:
                    report_items.append((entry.filename, "Ruta interna no válida; omitido"))
                    continue
                if entry.flag_bits & 0x1:
                    report_items.append((entry.filename, "Archivo cifrado; omitido"))
                    continue
                if entry.file_size > 20 * 1024 * 1024 or expanded_size + entry.file_size > 200 * 1024 * 1024:
                    raise UserError("El contenido descomprimido supera el límite permitido (20 MB por Excel y 200 MB total).")
                expanded_size += entry.file_size
                filename = parts[-1]
                stem = filename.rsplit(".", 1)[0]
                node_id, status = match_splice_node(stem, node_codes)
                if status != "matched":
                    reason = "Matrícula ambigua; omitido" if status == "ambiguous" else "No se encontró la matrícula; omitido"
                    report_items.append((entry.filename, reason))
                    continue

                if not node_by_id[node_id].has_trays:
                    report_items.append((
                        entry.filename,
                        "Elemento encontrado por matrícula, pero no tiene bandejas activadas; omitido",
                    ))
                    continue

                matched_entries.append((entry, normalized_path, node_id, filename, stem))

            matched_node_ids = list({node_id for _, _, node_id, _, _ in matched_entries})
            matched_filenames = list({filename for _, _, _, filename, _ in matched_entries})
            existing_documents = document_model.search([
                ("node_id", "in", matched_node_ids),
                ("kind", "=", "excel"),
                ("file_name", "in", matched_filenames),
            ]) if matched_entries else document_model
            existing_keys = {
                (document.node_id.id, (document.file_name or "").casefold())
                for document in existing_documents
            }
            seen_files = set()
            values_to_create = []
            for entry, normalized_path, node_id, filename, stem in matched_entries:
                duplicate_key = (node_id, filename.casefold())
                if duplicate_key in seen_files or duplicate_key in existing_keys:
                    duplicate_count += 1
                    duplicate_items.append((entry.filename, "Duplicado; omitido"))
                    continue
                seen_files.add(duplicate_key)
                try:
                    content = archive.read(entry)
                except (EOFError, OSError, RuntimeError, zipfile.BadZipFile):
                    report_items.append((entry.filename, "No se pudo leer; omitido"))
                    continue
                if len(content) != entry.file_size:
                    report_items.append((entry.filename, "El tamaño interno no coincide; omitido"))
                    continue
                values_to_create.append({
                    "node_id": node_id,
                    "kind": "excel",
                    "name": stem,
                    "file_data": base64.b64encode(content).decode("ascii"),
                    "file_name": filename,
                    "comment": f"Importado desde {normalized_path}",
                })

        if values_to_create:
            document_model.create(values_to_create)
        unmatched_count = len(report_items)
        skipped_items = report_items + duplicate_items
        details = "".join(
            f"<li>{html.escape(filename)}: {html.escape(reason)}</li>"
            for filename, reason in report_items[:40]
        )
        if unmatched_count > 40:
            details += f"<li>Y {unmatched_count - 40} archivo(s) más.</li>"
        summary = (
            "<section class='o_fiber_splice_import_result'>"
            f"<p><strong>Cartas importadas:</strong> {len(values_to_create)}</p>"
            f"<p><strong>Duplicados omitidos:</strong> {duplicate_count}</p>"
            f"<p><strong>Archivos sin asignar:</strong> {unmatched_count}</p>"
            f"<p><strong>Archivos no importados:</strong> {len(skipped_items)}</p>"
            f"{'<ul>' + details + '</ul>' if details else '<p>Importación finalizada.</p>'}"
            "</section>"
        )
        report_lines = [
            f"ZIP: {self.archive_name or 'sin nombre'}",
            f"Importados: {len(values_to_create)}",
            f"No importados: {len(skipped_items)}",
            "",
        ]
        report_lines.extend(
            f"{filename}\t{reason}" for filename, reason in skipped_items
        )
        if not skipped_items:
            report_lines.append("Todos los archivos de hoja de cálculo se importaron correctamente.")
        report_data = base64.b64encode("\n".join(report_lines).encode("utf-8")).decode("ascii")
        self.write({
            "result_html": summary,
            "archive_data": False,
            "archive_name": False,
            "skipped_report": report_data,
            "skipped_report_name": "archivos_no_importados.txt",
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Resultado de importación",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("fiber_gis.view_fiber_gis_splice_import_wizard_form").id,
            "target": "new",
        }
