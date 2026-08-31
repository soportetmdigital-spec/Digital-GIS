"""Conserva cables, conexiones y autores al introducir tipologias y empleados."""
import logging

from odoo import api, SUPERUSER_ID
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def original_manual_name(cable):
    parts = [cable.from_node_id.code or cable.from_node_id.name or "",
             cable.to_node_id.code or cable.to_node_id.name or "", cable.to_node_id.address or ""]
    generated = " ".join(" ".join(parts).split())
    # No sobrescribir un nombre que ya se haya corregido manualmente.
    return cable.previous_name if cable.previous_name and cable.name == generated else False


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False, "tracking_disable": True})
    profiles = env["fiber.gis.cable.profile"]
    by_counts = {(item.tube_count, item.fiber_count): item for item in profiles.search([])}
    for cable in env["fiber.gis.cable"].search([]):
        previous = original_manual_name(cable)
        if previous:
            cable.write({"name": previous})
        if cable.profile_id:
            continue
        counts = (cable.tube_count, cable.fiber_count)
        total = cable.fiber_count * (cable.tube_count or 1)
        if total <= 0 or cable.fiber_ids.filtered(lambda fiber: fiber.number > total):
            _logger.warning("Cable %s: revisar tipologia; se conservan sus fibras sin modificar.", cable.id)
            continue
        if counts not in by_counts:
            label = (f"{cable.tube_count} tubos de {cable.fiber_count} fibras"
                     if cable.tube_count else f"{cable.fiber_count} fibras")
            by_counts[counts] = profiles.create({"name": label, "tube_count": counts[0], "fiber_count": counts[1]})
        cable.write({"profile_id": by_counts[counts].id})

    # Los antiguos technician_id apuntan a usuarios, no a empleados. Nunca reutilizar sus ID.
    employees_by_user = {}
    for employee in env["hr.employee.public"].search([("user_id", "!=", False)]):
        employees_by_user.setdefault(employee.user_id.id, []).append(employee)
    for user_id, employees in employees_by_user.items():
        if len(employees) != 1:
            continue
        employee = employees[0]
        for table, legacy_field in (("fiber_gis_tray_line", "technician_id"),
                                    ("fiber_gis_splitter", "technician_id"),
                                    ("fiber_gis_node_work_log", "user_id")):
            # SQL deliberado: enlaza el autor conocido sin crear trabajos ni cambiar sus fechas.
            cr.execute(SQL("UPDATE %s SET employee_id = %s WHERE %s = %s AND employee_id IS NULL",
                           SQL.identifier(table), employee.id, SQL.identifier(legacy_field), user_id))
        cr.execute("UPDATE fiber_gis_node_work_log SET employee_name = %s WHERE employee_id = %s AND employee_name IS NULL",
                   (employee.name, employee.id))
    env.invalidate_all()
