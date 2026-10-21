/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    async saveButtonClicked(params = {}) {
        const saved = await super.saveButtonClicked(params);
        const root = this.model?.root;
        const data = root?.data || {};
        const resModel = root?.resModel || this.props?.resModel;
        const resId = root?.resId || data.id;

        if (
            saved !== false &&
            resModel === "fiber.gis.node" &&
            resId &&
            (!data.latitude || !data.longitude)
        ) {
            const notification = this.notification || this.env?.services?.notification;
            const action = this.actionService || this.env?.services?.action;
            notification?.add(
                "El elemento no tiene coordenadas. Se abre el mapa para colocarlo manualmente.",
                { type: "warning" }
            );
            await action?.doAction({
                type: "ir.actions.client",
                tag: "fiber_gis.map_action",
                name: "Mapa de Fibra",
                target: "current",
                params: { place_node_id: resId },
            });
        }
        return saved;
    },
});
