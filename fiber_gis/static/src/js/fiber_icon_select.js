/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const ICON_PATHS = {
    diamond: "M 0 -10 L 10 0 L 0 10 L -10 0 Z",
    triangle: "M 0 -11 L 11 10 L -11 10 Z",
    star: "M 0 -12 L 3 -4 L 11 -4 L 5 1 L 7 10 L 0 5 L -7 10 L -5 1 L -11 -4 L -3 -4 Z",
    network: "M -11 -11 H 11 V 11 H -11 Z M -7 -7 V 7 H 7 V -7 Z M -2 -2 H 2 V 2 H -2 Z",
    olt: "M -12 -12 H 12 V 12 H -12 Z M -8 -8 H 8 V -5 H -8 Z M -8 -2 H 8 V 1 H -8 Z M -8 4 H 8 V 8 H -8 Z",
    odf: "M -11 -11 H 11 V 11 H -11 Z M -7 -7 H -3 V -3 H -7 Z M 3 -7 H 7 V -3 H 3 Z M -7 3 H -3 V 7 H -7 Z M 3 3 H 7 V 7 H 3 Z",
    fdh: "M -11 -12 H 11 V 12 H -11 Z M -6 -8 H 6 V -4 H -6 Z M -6 1 H 6 V 5 H -6 Z M -3 12 H 3 V 15 H -3 Z",
    cabinet: "M -9 -12 H 9 V 12 H -9 Z M -5 -8 H 5 V -5 H -5 Z M -5 -2 H 5 V 1 H -5 Z M -5 4 H 5 V 8 H -5 Z",
    cto: "M 0 -12 L 11 -5 V 7 L 0 12 L -11 7 V -5 Z M -5 -4 H 5 V 4 H -5 Z",
    terminal: "M -11 -8 H 11 V 8 H -11 Z M -6 -3 H 6 V 3 H -6 Z M -2 8 H 2 V 12 H -2 Z",
    closure: "M -12 -7 H 12 V 7 H -12 Z M -7 -3 H 7 V 3 H -7 Z M -14 -2 H -12 V 2 H -14 Z M 12 -2 H 14 V 2 H 12 Z",
    dome_closure: "M -9 10 H 9 V -2 C 9 -8 5 -12 0 -12 C -5 -12 -9 -8 -9 -2 Z M -12 10 H 12 V 14 H -12 Z",
    splice: "M -12 -3 H -4 L -1 -7 H 1 L 4 -3 H 12 V 3 H 4 L 1 7 H -1 L -4 3 H -12 Z",
    splitter: "M -11 -3 H -2 V -8 H 2 V -3 H 11 V 3 H 2 V 8 H -2 V 3 H -11 Z",
    tray: "M -12 -8 H 12 V 8 H -12 Z M -8 -4 H 8 V -1 H -8 Z M -8 2 H 8 V 5 H -8 Z",
    manhole: "M 0 -11 C 7 -11 12 -6 12 0 C 12 6 7 11 0 11 C -7 11 -12 6 -12 0 C -12 -6 -7 -11 0 -11 Z M 0 -6 C -4 -6 -7 -3 -7 0 C -7 3 -4 6 0 6 C 4 6 7 3 7 0 C 7 -3 4 -6 0 -6 Z",
    chamber: "M -12 -9 H 12 V 9 H -12 Z M -8 -5 H 8 V 5 H -8 Z M -5 -1 H 5 V 1 H -5 Z",
    handhole: "M -12 -6 C -12 -11 12 -11 12 -6 V 6 C 12 11 -12 11 -12 6 Z M -7 -2 H 7 V 2 H -7 Z",
    pole: "M -2 -12 H 2 V 12 H -2 Z M -9 -8 H 9 V -5 H -9 Z M -7 3 H 7 V 6 H -7 Z",
    aerial_strand: "M -12 -4 C -6 -10 6 2 12 -4 V 1 C 6 7 -6 -5 -12 1 Z",
    duct: "M -12 -6 H 12 V -1 H -12 Z M -12 3 H 12 V 8 H -12 Z",
    building: "M -10 -12 H 4 V 12 H -10 Z M 4 -4 H 12 V 12 H 4 Z M -6 -8 H -2 V -4 H -6 Z M -6 1 H -2 V 5 H -6 Z",
    customer: "M 0 -11 C 4 -11 7 -8 7 -4 C 7 0 4 3 0 3 C -4 3 -7 0 -7 -4 C -7 -8 -4 -11 0 -11 Z M -10 13 C -8 6 8 6 10 13 Z",
    customer_terminal: "M -13 -8 H 13 V 8 H -13 Z M -9 -4 H 5 V 0 H -9 Z M 8 -3 H 11 V 3 H 8 Z",
    ont: "M -10 -7 H 10 V 7 H -10 Z M -6 -3 H 2 V 1 H -6 Z M 5 -2 H 8 V 2 H 5 Z M -4 7 H 4 V 11 H -4 Z",
    router: "M -11 -6 H 11 V 7 H -11 Z M -6 -10 L -2 -6 M 6 -10 L 2 -6 M -5 2 H -2 M 2 2 H 5",
    drop: "M -12 -8 H -2 V -4 H 2 V -8 H 12 V -2 H 3 V 8 H -3 V -2 H -12 Z",
};

export class FiberIconSelectField extends Component {
    static template = "fiber_gis.FiberIconSelectField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({ open: false });
    }

    get value() {
        return this.props.record.data[this.props.name] || "circle";
    }

    get color() {
        return this.props.record.data.color || "#334155";
    }

    get options() {
        const field = this.props.record.fields[this.props.name];
        return (field.selection || []).map(([value, label]) => ({ value, label }));
    }

    get selectedOption() {
        return this.options.find((option) => option.value === this.value) || this.options[0] || {
            value: "circle",
            label: "Icono",
        };
    }

    openPicker() {
        if (!this.props.readonly) {
            this.state.open = true;
        }
    }

    closePicker() {
        this.state.open = false;
    }

    path(value) {
        return ICON_PATHS[value] || ICON_PATHS.network;
    }

    select(value) {
        if (this.props.readonly) {
            return;
        }
        this.props.record.update({ [this.props.name]: value });
        this.closePicker();
    }
}

registry.category("fields").add("fiber_icon_select", {
    component: FiberIconSelectField,
    supportedTypes: ["selection"],
}, { force: true });
