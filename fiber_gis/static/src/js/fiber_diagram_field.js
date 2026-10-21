/** @odoo-module **/

import { Component, markup, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class FiberDiagramField extends Component {
    static template = "fiber_gis.FiberDiagramField";
    static props = { ...standardFieldProps };

    setup() {
        this.root = useRef("diagram");
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ busy: false });
        this.alive = true;
        this.dialogOpen = false;
        this.confirmationOpen = false;
        this.draggedLineId = 0;
        this.suppressOpenUntil = 0;
        onWillUnmount(() => { this.alive = false; });
    }

    get value() {
        // Solo HTML calculado por nuestros modelos, que escapan los datos de usuario.
        const { resModel, data } = this.props.record;
        const allowed = (resModel === "fiber.gis.node" && this.props.name === "tray_visual_html") ||
            (resModel === "fiber.gis.splitter" && this.props.name === "diagram_html");
        return markup(allowed ? data[this.props.name] || "" : "");
    }

    find(ev, selector) {
        const element = ev.target.closest?.(selector);
        return element && this.root.el.contains(element) ? element : null;
    }

    trayLine(ev) {
        if (this.props.record.resModel !== "fiber.gis.node") {
            return null;
        }
        const line = this.find(ev, ".o_fiber_tray_line[data-line-id]");
        return Number(line?.dataset.nodeId) === Number(this.props.record.resId) ? line : null;
    }

    async refresh(record) {
        if (this.alive && this.props.record === record) {
            await record.load();
        }
    }

    async execute(model, method, args, opensDialog = true) {
        if (this.state.busy || this.dialogOpen || !this.alive) {
            return;
        }
        this.state.busy = true;
        const record = this.props.record;
        try {
            const root = record.model.root || record;
            if ((root.isNew || await root.isDirty()) && await root.save() === false) {
                return;
            }
            const result = await this.orm.call(model, method, args, { context: record.context });
            if (!this.alive || this.props.record !== record) {
                return;
            }
            if (opensDialog) {
                this.dialogOpen = true;
                await this.action.doAction(result, {
                    onClose: async () => {
                        this.dialogOpen = false;
                        try {
                            await this.refresh(record);
                        } catch (error) {
                            this.showError(error);
                        }
                    },
                });
            } else {
                await this.refresh(record);
            }
        } catch (error) {
            this.dialogOpen = false;
            this.showError(error);
        } finally {
            if (this.alive) {
                this.state.busy = false;
            }
        }
    }

    showError(error) {
        if (this.alive) {
            this.notification.add(error.data?.message || error.message || "No se ha podido completar la operaci\u00f3n.", { type: "danger" });
        }
    }

    onClick(ev) {
        const line = this.trayLine(ev);
        if (line) {
            ev.stopPropagation();
            if (this.find(ev, ".o_fiber_tray_delete")) {
                ev.preventDefault();
                this.confirmDelete(Number(line.dataset.lineId));
            }
            return;
        }
        const output = this.find(ev, ".o_fiber_splitter_output[data-output-id]");
        if (this.props.record.resModel === "fiber.gis.splitter" && output &&
            Number(output.closest("[data-splitter-id]")?.dataset.splitterId) === Number(this.props.record.resId)) {
            ev.preventDefault();
            ev.stopPropagation();
            this.execute("fiber.gis.splitter.output", "action_manage_connection", [[Number(output.dataset.outputId)]]);
        }
    }

    onDoubleClick(ev) {
        const line = this.trayLine(ev);
        if (!line || this.find(ev, ".o_fiber_tray_delete") || Date.now() < this.suppressOpenUntil) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const fiber = this.find(ev, "[data-fiber-id]");
        this.execute("fiber.gis.tray.line", "action_open_fiber", [
            [Number(line.dataset.lineId)], Number(fiber?.dataset.fiberId || 0),
        ]);
    }

    onKeyDown(ev) {
        if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches?.(".o_fiber_tray_line[tabindex]")) {
            this.onDoubleClick(ev);
        }
    }

    confirmDelete(lineId) {
        if (this.confirmationOpen || this.state.busy || this.dialogOpen) {
            return;
        }
        this.confirmationOpen = true;
        this.dialog.add(ConfirmationDialog, {
            title: "Borrar registro de bandeja",
            body: "\u00bfConfirma que desea borrar este registro? Esta acci\u00f3n no se puede deshacer.",
            confirmLabel: "Borrar", cancelLabel: "Cancelar",
            confirm: () => this.execute("fiber.gis.tray.line", "action_delete_visual_line", [lineId], false),
        }, { onClose: () => { this.confirmationOpen = false; } });
    }

    onDragStart(ev) {
        const line = this.trayLine(ev);
        if (!line || this.find(ev, "button") || this.state.busy || this.dialogOpen) {
            ev.preventDefault();
            return;
        }
        this.draggedLineId = Number(line.dataset.lineId);
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(this.draggedLineId));
        line.classList.add("is-dragging");
    }

    onDragOver(ev) {
        const tray = this.find(ev, ".o_fiber_tray_card[data-tray-id]");
        if (this.draggedLineId && tray) {
            ev.preventDefault();
            ev.dataTransfer.dropEffect = "move";
            tray.classList.add("is-drop-target");
        }
    }

    onDragLeave(ev) {
        const tray = this.find(ev, ".o_fiber_tray_card[data-tray-id]");
        if (tray && !tray.contains(ev.relatedTarget)) {
            tray.classList.remove("is-drop-target");
        }
    }

    onDragEnd() {
        if (this.draggedLineId) {
            this.suppressOpenUntil = Date.now() + 350;
        }
        this.draggedLineId = 0;
        this.root.el?.querySelectorAll(".is-dragging, .is-drop-target").forEach((item) => {
            item.classList.remove("is-dragging", "is-drop-target");
        });
    }

    onDrop(ev) {
        const tray = this.find(ev, ".o_fiber_tray_card[data-tray-id]");
        if (!this.draggedLineId || !tray) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const lineId = this.draggedLineId;
        const trayId = Number(tray.dataset.trayId);
        this.onDragEnd();
        this.execute("fiber.gis.tray.line", "action_move_to_tray", [lineId, trayId], false);
    }
}

registry.category("fields").add("fiber_diagram", {
    component: FiberDiagramField,
    supportedTypes: ["html"],
});
