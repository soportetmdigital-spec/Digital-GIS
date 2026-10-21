/** @odoo-module **/

import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FiberGisCabinet extends Component {
    static template = "fiber_gis.FiberGisCabinet";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, saving: false, data: null, selectedEquipment: null, equipmentNameDraft: "", catalogEdit: null, draggingCatalogPort: null, query: "", selectedPort: null, confirmDeleteEquipment: null, draggingEquipmentId: null, activeFiberPortId: null, fiberQuery: "", fiberResults: [], fiberSearchLoading: false, fiberResultsTruncated: false, activeRackId: null, zoom: 1, interconnectionDraft: { targetId: "", fromPort: "1", toPort: "1", name: "", cableType: "ethernet" } });
        this.cabinetId = Number(this.props?.action?.params?.cabinet_id || 0);
        onWillStart(() => this.load());
        onMounted(() => { this.drawConnectionPaths(); this._resizeHandler = () => this.drawConnectionPaths(); window.addEventListener("resize", this._resizeHandler); });
        onPatched(() => this.drawConnectionPaths());
        onWillUnmount(() => window.removeEventListener("resize", this._resizeHandler));
    }

    async load() {
        if (!this.cabinetId) {
            this.state.loading = false;
            return;
        }
        try {
            this.state.data = await this.orm.call("fiber.gis.cabinet", "get_cabinet_editor_data", [this.cabinetId]);
            this.state.activeRackId = this.racks[0]?.id || this.cabinetId;
        } catch (error) {
            this.notification.add(error.message || "No se pudo cargar el armario.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get equipment() { return this.allEquipment; }
    get racks() { return this.state.data?.racks || []; }
    get allEquipment() { return this.racks.flatMap((rack) => rack.equipment || []); }
    get catalog() {
        const query = this.state.query.trim().toLocaleLowerCase();
        return (this.state.data?.catalog || []).filter((item) => !query || `${item.name} ${item.kind}`.toLocaleLowerCase().includes(query));
    }
    get ports() { return this.state.selectedEquipment?.ports || []; }
    get connectedCount() { return this.allEquipment.flatMap((item) => item.ports || []).filter((port) => port.fiber_id).length; }
    get filteredFibers() { return this.state.fiberResults; }

    units(rack = this.racks[0]) { return Array.from({ length: rack?.height_u || 0 }, (_, index) => (rack.height_u - index)); }
    equipmentStyle(item) {
        const height = 44 * item.height_u;
        const bottom = (item.position_u - 1) * 44;
        return `height:${height}px;bottom:${bottom}px`;
    }
    kindIcon(kind) { return ({ patch_panel: "fa fa-ellipsis-h", fhu_panel_48f: "fa fa-circle-o", odf: "fa fa-circle-o", odf_96: "fa fa-circle-o", switch: "fa fa-sitemap", switch_48: "fa fa-sitemap", mikrotik_crs326: "fa fa-sitemap", zyxel_gs1920: "fa fa-sitemap", router: "fa fa-random", firewall: "fa fa-shield", olt: "fa fa-server", server: "fa fa-server", server_1u: "fa fa-server", server_3u: "fa fa-server", nas: "fa fa-hdd-o", raid_2u: "fa fa-hdd-o", raid_3u: "fa fa-hdd-o", kvm_switch: "fa fa-keyboard-o", monitor_7u: "fa fa-desktop", monitor_8u: "fa fa-desktop", shelf: "fa fa-inbox", shelf_sliding: "fa fa-inbox", cable_manager: "fa fa-align-justify", pdu: "fa fa-bolt", power_strip: "fa fa-bolt", fan_panel: "fa fa-refresh", ups: "fa fa-battery-three-quarters", ups_managed: "fa fa-battery-three-quarters", blank: "fa fa-minus" })[kind] || "fa fa-cube"; }
    equipmentImage(item) {
        const catalogEntry = (this.state.data?.catalog || []).find((entry) => entry.kind === item.kind);
        if (catalogEntry?.image_url) return catalogEntry.image_url;
        if (this.state.catalogEdit?.kind === item.kind && this.state.catalogEdit.imagePreview) return this.state.catalogEdit.imagePreview;
        return ({
            fhu_panel_48f: "/fiber_gis/static/src/img/fs_fhu_panel_48f_sc_upc.webp",
            patch_panel: "/fiber_gis/static/src/img/cd_patch_panel.png",
            odf: "/fiber_gis/static/src/img/cd_patch_panel.png",
            odf_96: "/fiber_gis/static/src/img/cd_patch_panel.png",
            switch: "/fiber_gis/static/src/img/cd_switch_24.png",
            switch_48: "/fiber_gis/static/src/img/cd_switch_48.png",
            mikrotik_crs326: "/fiber_gis/static/src/img/cd_switch_24.png",
            zyxel_gs1920: "/fiber_gis/static/src/img/cd_switch_24.png",
            server: "/fiber_gis/static/src/img/cd_server_2u.png",
            server_1u: "/fiber_gis/static/src/img/cd_server_1u.png",
            server_3u: "/fiber_gis/static/src/img/cd_server_3u.png",
            nas: "/fiber_gis/static/src/img/cd_raid_2u.png",
            raid_2u: "/fiber_gis/static/src/img/cd_raid_2u.png",
            raid_3u: "/fiber_gis/static/src/img/cd_raid_3u.png",
            kvm_switch: "/fiber_gis/static/src/img/cd_kvm_1u.png",
            monitor_7u: "/fiber_gis/static/src/img/cd_monitor_7u.png",
            monitor_8u: "/fiber_gis/static/src/img/cd_monitor_8u.png",
            ups: "/fiber_gis/static/src/img/cd_ups_rack.png",
            ups_managed: "/fiber_gis/static/src/img/cd_ups_managed.png",
            pdu: "/fiber_gis/static/src/img/cd_power_strip.png",
            power_strip: "/fiber_gis/static/src/img/cd_power_strip.png",
        })[item.kind] || "";
    }
    equipmentPorts(item) {
        const fiberPorts = new Map((item.ports || []).map((port) => [port.number, port]));
        return Array.from({ length: item.port_count || 0 }, (_, index) => {
            const number = index + 1;
            return { number, fiberPort: fiberPorts.get(number) };
        });
    }

    equipmentInfoStyle(item) {
        const compactKinds = ["fhu_panel_48f"].includes(item.kind) ? 7 :
            ["patch_panel", "odf", "odf_96", "switch_48"].includes(item.kind) ? 12 : 17;
        return `max-width:${compactKinds}%`;
    }

    visualPortStyle(item, port) {
        const catalog = (this.state.data?.catalog || []).find((entry) => entry.kind === item.kind);
        const custom = catalog?.port_layout?.[String(port.number)];
        if (custom && Number.isFinite(Number(custom.x)) && Number.isFinite(Number(custom.y))) {
            return `left:${custom.x}%;top:${custom.y}%${port.fiberPort?.fiber_id ? `;--fiber-color:${port.fiberPort.fiber_color || "#26d3c4"}` : ""}`;
        }
        const point = this.defaultPortPoint(item, port.number);
        return `left:${point.x}%;top:${point.y}%${port.fiberPort?.fiber_id ? `;--fiber-color:${port.fiberPort.fiber_color || "#26d3c4"}` : ""}`;
    }

    defaultPortPoint(item, n) {
        let x = 0;
        let y = 50;
        if (["switch", "mikrotik_crs326", "zyxel_gs1920"].includes(item.kind)) {
            const column = (n - 1) % 12;
            const group = Math.floor(column / 6);
            x = (group ? 65.5 : 39.5) + (column % 6) * 3.35;
            y = n <= 12 ? 34 : 69;
        } else if (item.kind === "switch_48") {
            const column = (n - 1) % 24;
            const group = Math.floor(column / 8);
            x = 17.5 + group * 24.2 + (column % 8) * 2.95;
            y = n <= 24 ? 37 : 74;
        } else if (["patch_panel", "odf", "odf_96"].includes(item.kind)) {
            const column = (n - 1) % 24;
            const group = Math.floor(column / 6);
            x = 17 + group * 18.8 + (column % 6) * 2.45;
            y = n <= 24 ? 37 : 74;
        } else if (item.kind === "fhu_panel_48f") {
            x = 88 - (n - 1) * (75 / Math.max(1, item.port_count - 1));
            y = 40;
        } else {
            const columns = Math.min(8, item.port_count || 1);
            const column = (n - 1) % columns;
            x = 68 + column * (24 / Math.max(1, columns - 1));
            y = n <= columns ? 34 : 69;
        }
        return { x, y };
    }

    isInterconnectionPortOccupied(item, portNumber) {
        return (this.state.data?.interconnections || []).some((link) =>
            (link.from_equipment_id === item.id && link.from_port === portNumber) ||
            (link.to_equipment_id === item.id && link.to_port === portNumber)
        );
    }

    portTitle(item, port) {
        const state = this.isInterconnectionPortOccupied(item, port.number) ? " · ya conectada" : "";
        return `${item.name} · boca ${port.number}${state}`;
    }

    async onVisualPortClick(ev, item, port) {
        ev.preventDefault();
        ev.stopPropagation();
        if (this.state.saving) return;
        if (this.isInterconnectionPortOccupied(item, port.number)) {
            this.notification.add(`La boca ${port.number} de «${item.name}» ya tiene una interconexión.`, { type: "warning" });
            return;
        }
        const source = this.state.selectedPort;
        if (!source) {
            this.state.selectedPort = { equipmentId: item.id, equipmentName: item.name, port: port.number };
            this.state.selectedEquipment = item;
            this.state.equipmentNameDraft = item.name;
            this.notification.add(`Boca ${port.number} seleccionada. Pulsa la boca del equipo de destino.`, { type: "info" });
            return;
        }
        if (source.equipmentId === item.id) {
            if (source.port === port.number) {
                this.state.selectedPort = null;
                return;
            }
            this.notification.add("Elige una boca de otro equipo para completar la conexión.", { type: "warning" });
            return;
        }
        const sourceEquipment = this.allEquipment.find((candidate) => candidate.id === source.equipmentId);
        const usesFiber = ["patch_panel", "fhu_panel_48f", "odf", "odf_96"].includes(sourceEquipment?.kind) ||
            ["patch_panel", "fhu_panel_48f", "odf", "odf_96"].includes(item.kind);
        this.state.interconnectionDraft.cableType = usesFiber ? "fiber" : "ethernet";
        const saved = await this.mutate("create_interconnection", [
            source.equipmentId, source.port, item.id, port.number, "", this.state.interconnectionDraft.cableType,
        ]);
        if (saved) {
            this.state.selectedPort = null;
            this.notification.add(`Cable conectado: ${source.equipmentName} boca ${source.port} → ${item.name} boca ${port.number}.`, { type: "success" });
        }
    }

    async mutate(method, args) {
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("fiber.gis.cabinet", method, args);
            if (this.state.selectedEquipment) {
                this.state.selectedEquipment = this.allEquipment.find((item) => item.id === this.state.selectedEquipment.id) || null;
                this.state.equipmentNameDraft = this.state.selectedEquipment?.name || "";
            }
            return true;
        } catch (error) {
            this.notification.add(error.message || "No se pudo guardar el cambio.", { type: "danger" });
            return false;
        } finally { this.state.saving = false; }
    }

    async addEquipment(kind, rackId = this.state.activeRackId || this.cabinetId) {
        const catalogItem = this.state.data.catalog.find((entry) => entry.kind === kind);
        const position = this.findFreePosition(catalogItem?.height_u || 1, rackId);
        if (!position) {
            this.notification.add("No hay unidades U libres para este componente. Mueve o retira un equipo.", { type: "warning" });
            return;
        }
        const result = await this.mutate("action_create_equipment", [rackId, kind, position]);
        if (result) this.notification.add("Equipo añadido en el primer espacio libre.", { type: "success" });
    }

    findFreePosition(height, rackId = this.state.activeRackId) {
        const rack = this.racks.find((item) => item.id === Number(rackId));
        if (!rack) return false;
        const occupied = new Set();
        for (const item of rack.equipment) {
            for (let unit = item.position_u; unit < item.position_u + item.height_u; unit++) occupied.add(unit);
        }
        for (let position = 1; position <= rack.height_u - height + 1; position++) {
            let free = true;
            for (let unit = position; unit < position + height; unit++) if (occupied.has(unit)) free = false;
            if (free) return position;
        }
        return false;
    }

    selectEquipment(item) {
        this.state.selectedEquipment = this.state.selectedEquipment?.id === item.id ? null : item;
        this.state.equipmentNameDraft = this.state.selectedEquipment?.name || "";
        if (this.state.selectedEquipment) this.state.interconnectionDraft.targetId = String(this.allEquipment.find((candidate) => candidate.id !== item.id && candidate.port_count > 0)?.id || "");
    }
    async confirmRemoveEquipment() {
        const item = this.state.confirmDeleteEquipment;
        if (!item) return;
        if (await this.mutate("delete_equipment", [item.id])) {
            if (this.state.selectedEquipment?.id === item.id) this.state.selectedEquipment = null;
            this.state.confirmDeleteEquipment = null;
            this.notification.add("Equipo retirado del armario.", { type: "success" });
        }
    }
    connectedFibers(item) { return (item?.ports || []).filter((port) => port.fiber_id).length; }
    connectedInterconnections(item) {
        return (this.state.data?.interconnections || []).filter((link) => link.from_equipment_id === item?.id || link.to_equipment_id === item?.id).length;
    }
    rackName(rackId) { return this.racks.find((rack) => rack.id === Number(rackId))?.name || "Rack"; }

    onEquipmentKeydown(ev, item) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.selectEquipment(item);
        }
    }
    onEquipmentDragStart(ev, item) {
        this.state.draggingEquipmentId = item.id;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("application/fiber-gis-equipment", String(item.id));
    }
    onEquipmentDragEnd() { this.state.draggingEquipmentId = null; }

    async removeEquipmentFromRack(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const equipmentId = Number(ev.dataTransfer.getData("application/fiber-gis-equipment"));
        const item = this.allEquipment.find((candidate) => candidate.id === equipmentId);
        this.state.draggingEquipmentId = null;
        if (!item) return;
        if (this.connectedFibers(item) || this.connectedInterconnections(item)) {
            this.state.confirmDeleteEquipment = item;
            return;
        }
        if (await this.mutate("delete_equipment", [item.id])) {
            if (this.state.selectedEquipment?.id === item.id) this.state.selectedEquipment = null;
            this.notification.add("Equipo retirado del rack.", { type: "success" });
        }
    }

    async saveEquipmentName() {
        const item = this.state.selectedEquipment;
        const name = this.state.equipmentNameDraft;
        if (!item || !name.trim()) {
            this.notification.add("Escribe un nombre para el equipo.", { type: "warning" });
            return;
        }
        if (await this.mutate("rename_equipment", [item.id, name])) {
            this.notification.add("Nombre del equipo actualizado.", { type: "success" });
        }
    }
    onEquipmentNameInput(ev) { this.state.equipmentNameDraft = ev.target.value; }

    scrollRack(direction) {
        const scroller = this.el?.querySelector(".o_fiber_cabinet_canvas_scroll");
        scroller?.scrollBy({ top: direction * Math.max(320, scroller.clientHeight * 0.75), behavior: "smooth" });
    }

    async onRackDrop(ev) {
        ev.preventDefault();
        const kind = ev.dataTransfer.getData("application/fiber-gis-kind");
        const equipmentId = Number(ev.dataTransfer.getData("application/fiber-gis-equipment"));
        const rect = ev.currentTarget.getBoundingClientRect();
        const rackId = Number(ev.currentTarget.dataset.rackId);
        const rack = this.racks.find((item) => item.id === rackId);
        if (!rack) return;
        const position = Math.max(1, Math.min(rack.height_u, Math.floor((rect.bottom - ev.clientY) / (44 * this.state.zoom)) + 1));
        if (kind) {
            const item = this.state.data.catalog.find((entry) => entry.kind === kind);
            if (item && position + item.height_u - 1 > rack.height_u) {
                this.notification.add("El equipo no cabe en la parte superior del rack.", { type: "warning" });
                return;
            }
            const result = await this.mutate("action_create_equipment", [rackId, kind, position]);
            if (result) this.notification.add("Equipo colocado en el rack.", { type: "success" });
        } else if (equipmentId) {
            const item = this.allEquipment.find((candidate) => candidate.id === equipmentId);
            await this.mutate(item?.rack_id === rackId ? "move_equipment" : "move_equipment_to_rack", item?.rack_id === rackId ? [equipmentId, position] : [equipmentId, rackId, position]);
        }
    }

    async addRack() {
        const result = await this.mutate("add_cabinet_rack", [this.cabinetId]);
        if (result) {
            this.state.activeRackId = this.racks[this.racks.length - 1]?.id || this.cabinetId;
            this.notification.add("Rack añadido a la cabecera.", { type: "success" });
        }
    }
    selectRack(rack) { this.state.activeRackId = rack.id; }
    setZoom(ev) { this.state.zoom = Math.max(0.6, Math.min(1.4, Number(ev.target.value) || 1)); }
    onInterconnectionInput(ev, field) { this.state.interconnectionDraft[field] = ev.target.value; }
    get selectedInterconnections() {
        const id = this.state.selectedEquipment?.id;
        return (this.state.data?.interconnections || []).filter((link) => link.from_equipment_id === id || link.to_equipment_id === id);
    }
    connectionLabel(link) {
        const outgoing = link.from_equipment_id === this.state.selectedEquipment?.id;
        return outgoing ? `${link.from_equipment_name} · ${link.from_port} → ${link.to_equipment_name} · ${link.to_port}` : `${link.to_equipment_name} · ${link.to_port} ← ${link.from_equipment_name} · ${link.from_port}`;
    }
    connectionTypeLabel(type) { return ({ ethernet: "Ethernet / cobre", fiber: "Fibra óptica", dac: "DAC / twinaxial", other: "Otro" })[type] || type; }
    async createInterconnection() {
        const item = this.state.selectedEquipment;
        const draft = this.state.interconnectionDraft;
        if (!item || !draft.targetId || Number(draft.targetId) === item.id) {
            this.notification.add("Selecciona otro equipo para conectar.", { type: "warning" });
            return;
        }
        const result = await this.mutate("create_interconnection", [item.id, Number(draft.fromPort), Number(draft.targetId), Number(draft.toPort), draft.name, draft.cableType]);
        if (result) this.notification.add("Interconexión guardada.", { type: "success" });
    }
    async deleteInterconnection(link) { await this.mutate("delete_interconnection", [link.id]); }

    openCatalogEditor(item) {
        const layout = {};
        for (let n = 1; n <= item.port_count; n++) {
            const point = item.port_layout?.[String(n)] || this.defaultPortPoint(item, n);
            layout[String(n)] = { x: point.x, y: point.y };
        }
        this.state.selectedEquipment = null;
        this.state.catalogEdit = { kind: item.kind, name: item.name, height_u: item.height_u,
            port_count: item.port_count, image_url: item.image_url || this.equipmentImage(item),
            imagePreview: "", imageData: "", imageFilename: "", resetImage: false, port_layout: layout };
    }
    cancelCatalogEditor() { this.state.catalogEdit = null; this.state.draggingCatalogPort = null; }
    catalogEditPorts() {
        const edit = this.state.catalogEdit;
        return Array.from({ length: Math.max(0, Math.min(512, Number(edit?.port_count) || 0)) }, (_, index) => index + 1);
    }
    catalogEditPortStyle(number) {
        const edit = this.state.catalogEdit;
        const point = edit?.port_layout?.[String(number)] || this.defaultPortPoint({ kind: edit?.kind, port_count: Number(edit?.port_count) || 1 }, number);
        return `left:${point.x}%;top:${point.y}%`;
    }
    catalogEditPreviewStyle() {
        const units = Math.max(1, Number(this.state.catalogEdit?.height_u) || 1);
        const height = Math.min(320, 180 + (units - 1) * 40);
        return `height:${height}px`;
    }
    onCatalogEditInput(ev, field) {
        const edit = this.state.catalogEdit;
        if (!edit) return;
        edit[field] = field === "height_u" || field === "port_count" ? Number(ev.target.value) : ev.target.value;
        if (field === "port_count") {
            const count = Math.max(0, Math.min(512, Number(edit.port_count) || 0));
            for (let n = 1; n <= count; n++) if (!edit.port_layout[String(n)]) {
                edit.port_layout[String(n)] = this.defaultPortPoint({ kind: edit.kind, port_count: count }, n);
            }
            for (const key of Object.keys(edit.port_layout)) if (Number(key) > count) delete edit.port_layout[key];
        }
    }
    onCatalogImageChange(ev) {
        const file = ev.target.files?.[0];
        const edit = this.state.catalogEdit;
        if (!file || !edit) return;
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            edit.imageData = result.split(",", 2)[1] || "";
            edit.imagePreview = result;
            edit.imageFilename = file.name;
            edit.resetImage = false;
        };
        reader.readAsDataURL(file);
    }
    resetCatalogImage() {
        const edit = this.state.catalogEdit;
        if (!edit) return;
        edit.imageData = "";
        edit.imagePreview = "";
        edit.resetImage = true;
        edit.image_url = "";
    }
    startCatalogPortDrag(ev, number) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.draggingCatalogPort = number;
        ev.currentTarget.setPointerCapture?.(ev.pointerId);
        this.moveCatalogPort(ev);
    }
    moveCatalogPort(ev) {
        const number = this.state.draggingCatalogPort;
        if (!number) return;
        const preview = this.el?.querySelector(".o_fiber_cabinet_catalog_preview");
        if (!preview) return;
        const rect = preview.getBoundingClientRect();
        const edit = this.state.catalogEdit;
        edit.port_layout[String(number)] = {
            x: Math.round(Math.max(0, Math.min(100, (ev.clientX - rect.left) / rect.width * 100)) * 10) / 10,
            y: Math.round(Math.max(0, Math.min(100, (ev.clientY - rect.top) / rect.height * 100)) * 10) / 10,
        };
    }
    stopCatalogPortDrag() { this.state.draggingCatalogPort = null; }
    async saveCatalogEditor() {
        const edit = this.state.catalogEdit;
        if (!edit || !edit.name.trim()) {
            this.notification.add("Escribe un nombre para el elemento de biblioteca.", { type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            this.state.data = await this.orm.call("fiber.gis.cabinet", "save_catalog_item", [
                this.cabinetId, edit.kind, edit.name, Number(edit.height_u), Number(edit.port_count),
                edit.imageData || false, edit.imageFilename || "", edit.port_layout, edit.resetImage,
            ]);
            this.state.catalogEdit = null;
            this.notification.add("Elemento de biblioteca actualizado.", { type: "success" });
        } catch (error) {
            this.notification.add(error.message || "No se pudo actualizar el elemento.", { type: "danger" });
        } finally { this.state.saving = false; }
    }

    drawConnectionPaths() {
        const canvas = this.el?.querySelector(".o_fiber_cabinet_racks");
        const layer = this.el?.querySelector(".o_fiber_cabinet_connection_layer");
        if (!canvas || !layer) return;
        const zoom = Number(this.state.zoom) || 1;
        const canvasRect = canvas.getBoundingClientRect();
        const width = Math.max(1, canvasRect.width / zoom);
        const height = Math.max(1, canvasRect.height / zoom);
        const pixelRatio = window.devicePixelRatio || 1;
        layer.width = Math.round(width * pixelRatio);
        layer.height = Math.round(height * pixelRatio);
        const context = layer.getContext("2d");
        if (!context) return;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        context.clearRect(0, 0, width, height);
        const point = (equipmentId, portNumber) => {
            const selector = `[data-equipment-id="${equipmentId}"][data-port-number="${portNumber}"]`;
            const marker = canvas.querySelector(selector);
            const rack = marker?.closest(".o_fiber_gis_rack_position")?.querySelector(".o_fiber_cabinet_rack");
            if (!marker || !rack) return null;
            const markerRect = marker.getBoundingClientRect();
            const rackRect = rack.getBoundingClientRect();
            return {
                x: (markerRect.left + markerRect.width / 2 - canvasRect.left) / zoom,
                y: (markerRect.top + markerRect.height / 2 - canvasRect.top) / zoom,
                left: (rackRect.left - canvasRect.left) / zoom,
                right: (rackRect.right - canvasRect.left) / zoom,
                top: (rackRect.top - canvasRect.top) / zoom,
                rackId: rack.closest(".o_fiber_gis_rack_position")?.dataset.rackId,
            };
        };
        for (const link of this.state.data?.interconnections || []) {
            const a = point(link.from_equipment_id, link.from_port);
            const b = point(link.to_equipment_id, link.to_port);
            if (!a || !b) continue;
            let route;
            if (a.rackId === b.rackId) {
                const leftCost = Math.abs(a.x - a.left) + Math.abs(b.x - a.left);
                const rightCost = Math.abs(a.right - a.x) + Math.abs(b.right - b.x);
                const side = leftCost <= rightCost ? Math.min(a.left, b.left) - 10 : Math.max(a.right, b.right) + 10;
                route = [a, { x: side, y: a.y }, { x: side, y: b.y }, b];
            } else {
                const trayY = Math.max(3, Math.min(a.top, b.top) - 9);
                route = [a, { x: a.x, y: trayY }, { x: b.x, y: trayY }, b];
            }
            const drawRoute = () => {
                context.beginPath();
                context.moveTo(route[0].x, route[0].y);
                for (let index = 1; index < route.length; index++) context.lineTo(route[index].x, route[index].y);
            };
            context.save();
            context.lineCap = "round";
            context.lineJoin = "round";
            context.shadowColor = "rgba(0,0,0,.65)";
            context.shadowBlur = 4;
            context.strokeStyle = "rgba(255,255,255,.96)";
            context.lineWidth = 8;
            drawRoute();
            context.stroke();
            context.shadowBlur = 2;
            context.strokeStyle = link.color || "#138da0";
            context.lineWidth = 4;
            drawRoute();
            context.stroke();
            const previous = route[route.length - 2];
            const angle = Math.atan2(b.y - previous.y, b.x - previous.x);
            context.translate(b.x, b.y);
            context.rotate(angle);
            context.beginPath();
            context.moveTo(1, 0);
            context.lineTo(-10, -6);
            context.lineTo(-10, 6);
            context.closePath();
            context.fillStyle = link.color || "#138da0";
            context.strokeStyle = "#fff";
            context.lineWidth = 1.5;
            context.fill();
            context.stroke();
            context.restore();
        }
    }

    onCatalogDragStart(ev, item) {
        ev.dataTransfer.effectAllowed = "copy";
        ev.dataTransfer.setData("application/fiber-gis-kind", item.kind);
    }

    async assignFiber(ev, port) {
        const raw = ev.target.value;
        await this.chooseFiber(port, raw ? Number(raw) : false);
    }
    openFiberPicker(port) { this.state.activeFiberPortId = port.id; this.state.fiberQuery = ""; this.state.fiberResults = []; this.state.fiberResultsTruncated = false; }
    closeFiberPicker() { this.state.activeFiberPortId = null; this.state.fiberQuery = ""; this.state.fiberResults = []; this.state.fiberResultsTruncated = false; }
    onFiberSearch(ev) { this.state.fiberQuery = ev.target.value; this.state.fiberResults = []; this.state.fiberResultsTruncated = false; }
    async searchFibers() {
        const query = this.state.fiberQuery.trim();
        if (query.length < 2) {
            this.notification.add("Escribe al menos dos caracteres para buscar fibras.", { type: "warning" });
            return;
        }
        this.state.fiberSearchLoading = true;
        try {
            const result = await this.orm.call("fiber.gis.cable.fiber", "search_cabinet_fibers", [this.cabinetId, query]);
            this.state.fiberResults = result.fibers || [];
            this.state.fiberResultsTruncated = Boolean(result.truncated);
        } catch (error) {
            this.notification.add(error.message || "No se pudo buscar fibras.", { type: "danger" });
        } finally { this.state.fiberSearchLoading = false; }
    }
    async chooseFiber(port, fiberId) {
        if (await this.mutate("assign_patch_fiber", [port.id, fiberId || false])) this.closeFiberPicker();
    }
    async openCabinetList() { await this.action.doAction("fiber_gis.action_fiber_gis_cabinets"); }
    onSearch(ev) { this.state.query = ev.target.value; }
}

registry.category("actions").add("fiber_gis.cabinet_action", FiberGisCabinet);
