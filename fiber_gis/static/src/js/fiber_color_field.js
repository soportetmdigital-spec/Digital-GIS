/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class FiberColorField extends Component {
    static template = "fiber_gis.FiberColorField";
    static props = {
        ...standardFieldProps,
    };

    get value() {
        return this.props.record.data[this.props.name] || "#0f766e";
    }

    onInput(ev) {
        if (this.props.readonly) {
            return;
        }
        this.props.record.update({ [this.props.name]: ev.target.value });
    }
}

registry.category("fields").add("fiber_color", {
    component: FiberColorField,
    supportedTypes: ["char"],
}, { force: true });
