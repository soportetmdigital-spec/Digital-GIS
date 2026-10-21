/** @odoo-module **/

import { Component, onWillUnmount } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useSpecialData } from "@web/views/fields/relational_utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class FiberColorCheckboxesField extends Component {
    static template = "fiber_gis.FiberColorCheckboxesField";
    static components = { CheckBox };
    static props = {
        ...standardFieldProps,
        domain: { type: [Array, Function], optional: true },
        context: { type: Object, optional: true },
    };

    setup() {
        this.specialData = useSpecialData((orm, props) => {
            const { relation } = props.record.fields[props.name];
            const domain = getFieldDomain(props.record, props.name, props.domain);
            return orm.call(relation, "search_read", [domain], {
                fields: ["display_name", "number", "tube", "color", "tube_color"],
                order: "tube, number, id",
                context: props.context || {},
            });
        });
        this.idsToAdd = new Set();
        this.idsToRemove = new Set();
        this.debouncedCommitChanges = debounce(this.commitChanges.bind(this), 500);
        useBus(this.props.record.model.bus, "NEED_LOCAL_CHANGES", this.commitChanges.bind(this));
        onWillUnmount(this.commitChanges.bind(this));
    }

    get items() {
        return this.specialData.data || [];
    }

    isSelected(item) {
        return this.props.record.data[this.props.name].currentIds.includes(item.id);
    }

    colorStyle(color) {
        const validColor = /^#[0-9a-f]{6}$/i.test(color || "") ? color : "#e5e7eb";
        return `background-color: ${validColor};`;
    }

    detail(item) {
        const label = item.display_name || "";
        const marker = `F-${item.number}`;
        const markerIndex = label.indexOf(marker);
        return markerIndex >= 0 ? label.slice(markerIndex + marker.length).trim() : label;
    }

    itemClass(item) {
        return (item.display_name || "").includes("Pendiente de anular") ? "is-pending-cancel" : "";
    }

    commitChanges() {
        if (!this.idsToAdd.size && !this.idsToRemove.size) {
            return;
        }
        const result = this.props.record.data[this.props.name].addAndRemove({
            add: [...this.idsToAdd],
            remove: [...this.idsToRemove],
        });
        this.idsToAdd.clear();
        this.idsToRemove.clear();
        return result;
    }

    onChange(resId, checked) {
        if (checked) {
            if (this.idsToRemove.has(resId)) {
                this.idsToRemove.delete(resId);
            } else {
                this.idsToAdd.add(resId);
            }
        } else if (this.idsToAdd.has(resId)) {
            this.idsToAdd.delete(resId);
        } else {
            this.idsToRemove.add(resId);
        }
        this.debouncedCommitChanges();
    }
}

registry.category("fields").add("fiber_color_checkboxes", {
    component: FiberColorCheckboxesField,
    displayName: _t("Fiber color checkboxes"),
    supportedTypes: ["many2many"],
    isEmpty: () => false,
    extractProps(fieldInfo, dynamicInfo) {
        return {
            domain: dynamicInfo.domain,
            context: dynamicInfo.context,
        };
    },
});
