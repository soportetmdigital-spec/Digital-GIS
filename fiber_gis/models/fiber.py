"""Fibras individuales de cada cable y paleta normalizada de colores."""

from odoo import api, fields, models
from .work_log import work_employee_id


class FiberGisCableFiber(models.Model):
    _name = "fiber.gis.cable.fiber"
    _description = "Fibra individual de cable"
    _order = "cable_id, number"

    name = fields.Char(string="Nombre", required=True)
    cable_id = fields.Many2one("fiber.gis.cable", required=True, ondelete="cascade")
    number = fields.Integer(string="N\u00famero", required=True)
    color = fields.Char(string="Color")
    tube = fields.Integer(
        string="Tubo",
        help="Numero de tubo. El color del tubo sigue la misma secuencia estandar de 12 colores que las fibras.",
    )
    tube_color = fields.Char(string="Muestra color tubo")
    show_tube = fields.Boolean(
        string="Mostrar tubo",
        compute="_compute_show_tube",
        help="El tubo solo se muestra si el cable tiene más de un tubo.",
    )
    color_name = fields.Char(string="Color fibra", compute="_compute_color_names", store=True)
    tube_color_name = fields.Char(string="Nombre color tubo", compute="_compute_color_names", store=True)
    attenuation_db = fields.Float(string="Atenuaci\u00f3n (dB)")
    state = fields.Selection(
        [
            ("free", "Libre"),
            ("used", "Usada"),
            ("reserved", "Reservada"),
            ("fault", "Averiada"),
        ],
        default="free",
        required=True,
    )
    tray_input_line_ids = fields.One2many("fiber.gis.tray.line", "input_fiber_id", string="Bandejas entrada")
    tray_output_line_ids = fields.One2many("fiber.gis.tray.line", "output_fiber_id", string="Bandejas salida")
    splitter_input_ids = fields.One2many(
        "fiber.gis.splitter",
        "input_fiber_id",
        string="Entradas de splitter",
    )
    splitter_output_ids = fields.One2many(
        "fiber.gis.splitter.output",
        "output_fiber_id",
        string="Salidas de splitter",
    )
    notes = fields.Text(string="Notas")
    port_ids = fields.One2many("fiber.gis.port", "fiber_id", string="Puertos conectados")
    from_node_id = fields.Many2one(related="cable_id.from_node_id", string="Origen")
    to_node_id = fields.Many2one(related="cable_id.to_node_id", string="Destino")
    from_connection_summary = fields.Text(string="Extremo de origen", compute="_compute_endpoint_connections")
    to_connection_summary = fields.Text(string="Extremo de destino", compute="_compute_endpoint_connections")
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico de revisi\u00f3n")
    work_date = fields.Datetime(string="Fecha de revisi\u00f3n")

    @api.depends(
        "cable_id.from_node_id.name", "cable_id.from_node_id.address",
        "cable_id.to_node_id.name", "cable_id.to_node_id.address",
        "tray_input_line_ids.line_type", "tray_input_line_ids.tray_id.name", "tray_input_line_ids.node_id",
        "tray_input_line_ids.output_fiber_id.number", "tray_input_line_ids.output_fiber_id.tube",
        "tray_input_line_ids.output_fiber_id.cable_id.name", "tray_input_line_ids.employee_id.name", "tray_input_line_ids.work_date",
        "tray_output_line_ids.line_type", "tray_output_line_ids.tray_id.name", "tray_output_line_ids.node_id",
        "tray_output_line_ids.input_fiber_id.number", "tray_output_line_ids.input_fiber_id.tube",
        "tray_output_line_ids.input_fiber_id.cable_id.name", "tray_output_line_ids.employee_id.name", "tray_output_line_ids.work_date",
        "splitter_input_ids.name", "splitter_input_ids.ratio", "splitter_input_ids.tray_id.name",
        "splitter_input_ids.node_id", "splitter_input_ids.employee_id.name", "splitter_input_ids.work_date",
        "splitter_output_ids.sequence", "splitter_output_ids.splitter_id.name", "splitter_output_ids.node_id",
        "splitter_output_ids.splitter_id.tray_id.name", "splitter_output_ids.employee_id.name", "splitter_output_ids.work_date",
        "port_ids.node_id", "port_ids.name", "port_ids.status", "port_ids.employee_id.name", "port_ids.work_date",
    )
    def _compute_endpoint_connections(self):
        """Calcula y actualiza «extremo conexiones» a partir de los datos actuales y sus relaciones."""
        for fiber in self:
            fiber.from_connection_summary = fiber._endpoint_connections(fiber.cable_id.from_node_id)
            fiber.to_connection_summary = fiber._endpoint_connections(fiber.cable_id.to_node_id)

    def _operation_detail(self, record, text):
        """Describe el estado de uso de una fibra, incluida la bandeja y la conexión registrada."""
        if record.employee_id:
            text += f" - T\u00e9cnico: {record.employee_id.name}"
        if record.work_date:
            local = fields.Datetime.context_timestamp(self, record.work_date)
            text += " - " + local.strftime("%d/%m/%Y %H:%M")
        return text

    def _endpoint_connections(self, node):
        """Consulta solo conexiones de este extremo, sin confundirlo con el otro."""
        if not node:
            return "Sin elemento asignado"
        heading = node.display_name
        if node.address:
            heading += f" - {node.address}"
        details = []
        lines = (self.tray_input_line_ids | self.tray_output_line_ids).filtered(lambda line: line.node_id == node)
        for line in lines.sorted("position"):
            if line.splitter_id:
                continue
            label = {
                "free": "Fibra en punta",
                "pending_cancel": "Pendiente de anular",
                "pass": "Sangría",
                "fusion": "Fusi\u00f3n",
                "splitter": "Splitter",
            }.get(line.line_type, line.line_type)
            text = f"{label} - {line.tray_id.display_name}"
            other = line.output_fiber_id if line.input_fiber_id == self else line.input_fiber_id
            if other:
                identity = f"T{other.tube} " if other.show_tube else ""
                text += f" - {other.cable_id.display_name} {identity}F{other.number}"
                destination = node._fiber_endpoint_label(other)
                if destination:
                    text += f" - {destination}"
            details.append(self._operation_detail(line, text))
        for splitter in self.splitter_input_ids.filtered(lambda item: item.node_id == node):
            text = f"Entrada de {splitter.display_name} ({splitter.ratio}) - {splitter.tray_id.display_name}"
            details.append(self._operation_detail(splitter, text))
        for output in self.splitter_output_ids.filtered(lambda item: item.node_id == node):
            text = f"{output.splitter_id.display_name} - salida {output.sequence} - {output.splitter_id.tray_id.display_name}"
            details.append(self._operation_detail(output, text))
        for port in self.port_ids.filtered(lambda item: item.node_id == node):
            details.append(self._operation_detail(port, f"Puerto {port.display_name}"))
        return "\n".join([heading] + (details or ["Sin conexi\u00f3n registrada"]))

    def write(self, values):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        values = dict(values)
        review = not self.env.context.get("skip_fiber_work_log") and bool({"attenuation_db", "notes", "state", "employee_id"}.intersection(values))
        if review:
            values.setdefault("employee_id", work_employee_id(self.env))
            values.setdefault("work_date", fields.Datetime.now())
        result = super().write(values)
        if review:
            for fiber in self:
                nodes = fiber.cable_id.from_node_id | fiber.cable_id.to_node_id
                nodes._log_work("manual", f"Revisi\u00f3n de F{fiber.number} del cable {fiber.cable_id.display_name}.", employee_id=fiber.employee_id.id)
        return result

    _fiber_number_unique = models.Constraint(
        "UNIQUE(cable_id, number)",
        "El n\u00famero de fibra debe ser \u00fanico por cable.",
    )

    @api.model
    def fiber_color(self, number):
        """Devuelve el color normalizado de una fibra según el código de colores configurado."""
        palette = {
            1: "#0000ff",
            2: "#ffa500",
            3: "#008000",
            4: "#8b4513",
            5: "#708090",
            6: "#ffffff",
            7: "#ff0000",
            8: "#000000",
            9: "#ffff00",
            10: "#8f00ff",
            11: "#ff007f",
            12: "#00ffff",
        }
        index = ((int(number or 1) - 1) % 12) + 1
        return palette[index]

    @api.model
    def fiber_color_name(self, number):
        """Devuelve el nombre normalizado del color de una fibra para informes y etiquetas."""
        palette = {
            1: "Azul",
            2: "Naranja",
            3: "Verde",
            4: "Marr\u00f3n",
            5: "Pizarra",
            6: "Blanco",
            7: "Rojo",
            8: "Negro",
            9: "Amarillo",
            10: "Violeta",
            11: "Rosa",
            12: "Aqua",
        }
        index = ((int(number or 1) - 1) % 12) + 1
        return palette[index]

    @api.depends("tube", "cable_id.tube_count")
    def _compute_show_tube(self):
        """Indica si se muestra el tubo de la fibra: con un solo tubo no aporta información."""
        for fiber in self:
            fiber.show_tube = bool(fiber.tube) and fiber.cable_id.tube_count > 1

    @api.depends(
        "number",
        "tube",
        "cable_id.tube_count",
        "color_name",
        "tube_color_name",
        "state",
        "tray_input_line_ids.line_type",
        "tray_input_line_ids.tray_id",
        "tray_output_line_ids.line_type",
        "tray_output_line_ids.tray_id",
        "splitter_output_ids.splitter_id.name",
        "splitter_output_ids.sequence",
        "cable_id.name",
        "cable_id.from_node_id.name",
        "cable_id.from_node_id.address",
        "cable_id.to_node_id.name",
        "cable_id.to_node_id.address",
    )
    @api.depends_context("fiber_gis_node_id", "fiber_gis_show_endpoint")
    def _compute_display_name(self):
        """Calcula y actualiza «visualización nombre» a partir de los datos actuales y sus relaciones."""
        for fiber in self:
            parts = []
            if fiber.show_tube:
                parts.append(f"{fiber._color_dot(fiber.tube_color_name)} T-{fiber.tube}")
            parts.append(f"{fiber._color_dot(fiber.color_name)} F-{fiber.number}")
            if self.env.context.get("fiber_gis_show_endpoint"):
                parts.append(fiber.cable_id.display_name or "")
                node = self.env["fiber.gis.node"].browse(self.env.context.get("fiber_gis_node_id")).exists()
                if node:
                    parts.append(node._fiber_endpoint_label(fiber))
            usage = fiber._tray_usage_label()
            if usage:
                parts.append(usage)
            fiber.display_name = "  ".join(parts)

    def _tray_usage_label(self):
        """Resume la operación registrada para una fibra en su bandeja."""
        self.ensure_one()
        tray_lines = (self.tray_input_line_ids | self.tray_output_line_ids).sorted("id", reverse=True)
        node_id = self.env.context.get("fiber_gis_node_id")
        if node_id:
            tray_lines = tray_lines.filtered(lambda line: line.node_id.id == node_id)
        if tray_lines:
            line = tray_lines[:1]
            labels = {
                "free": "Fibra en punta",
                "pending_cancel": "Pendiente de anular",
                "pass": "Sangría",
                "fusion": "Fusionada",
                "splitter": "Splitter",
            }
            label = labels.get(line.line_type, line.line_type or "")
            tray = line.tray_id.display_name or ""
            return f"{label} - {tray}" if tray else label
        if node_id:
            output = self.splitter_output_ids.filtered(lambda item: item.node_id.id == node_id)[:1]
            if output:
                return f"{output.splitter_id.display_name} - salida {output.sequence}"
            return "Libre"
        state_labels = dict(self._fields["state"].selection)
        return state_labels.get(self.state, self.state or "")

    @api.model
    def _color_dot(self, color_name):
        """Genera un indicador HTML circular con el color de fibra correspondiente."""
        dots = {
            "Azul": "\U0001f535",
            "Naranja": "\U0001f7e0",
            "Verde": "\U0001f7e2",
            "Marr\u00f3n": "\U0001f7e4",
            "Pizarra": "\U0001f518",
            "Blanco": "\u26aa",
            "Rojo": "\U0001f534",
            "Negro": "\u26ab",
            "Amarillo": "\U0001f7e1",
            "Violeta": "\U0001f7e3",
            "Rosa": "\U0001f7e3",
            "Aqua": "\U0001f535",
        }
        return dots.get(color_name or "", "\u26aa")

    @api.depends("number", "tube", "cable_id.tube_count", "cable_id.fibers_per_tube")
    def _compute_color_names(self):
        """Calcula y actualiza «color nombres» a partir de los datos actuales y sus relaciones."""
        for fiber in self:
            if fiber.cable_id.tube_count:
                color_index = ((fiber.number - 1) % max(fiber.cable_id.fibers_per_tube, 1)) + 1
                fiber.color_name = self.fiber_color_name(color_index)
                fiber.tube_color_name = self.fiber_color_name(fiber.tube) if fiber.tube else ""
            else:
                fiber.color_name = self.fiber_color_name(fiber.number)
                fiber.tube_color_name = ""

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        for values in vals_list:
            if not values.get("color") and values.get("number"):
                cable = self.env["fiber.gis.cable"].browse(values.get("cable_id")).exists()
                color_index = cable._fiber_color_index(values["number"]) if cable else values["number"]
                values["color"] = self.fiber_color(color_index)
            if not values.get("tube_color") and values.get("tube"):
                values["tube_color"] = self.fiber_color(values["tube"])
        return super().create(vals_list)

    def _recompute_tray_state(self):
        """Recalcula el estado de cada fibra a partir de las fusiones, restos, pasos y splitters registrados."""
        tray_line_model = self.env["fiber.gis.tray.line"]
        for fiber in self:
            if fiber.state in ("reserved", "fault"):
                continue
            used = tray_line_model.search_count([
                "|",
                ("input_fiber_id", "=", fiber.id),
                ("output_fiber_id", "=", fiber.id),
            ])
            used += self.env["fiber.gis.splitter.output"].search_count([
                ("output_fiber_id", "=", fiber.id),
            ])
            fiber.with_context(skip_fiber_work_log=True).write({"state": "used" if used else "free"})
