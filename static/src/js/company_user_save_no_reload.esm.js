/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    async save(params = {}) {
        const record = this.model?.root;
        const changes = record?._changes || {};
        const changedFields = Object.keys(changes);

        // Saving the native Accepted Users (user_ids) field on a Company normally
        // reloads the whole form record after web_save.  For a user-only change,
        // the local many2many value already contains the final state, so a reload
        // is unnecessary and causes the visible page refresh the customer wants
        // to avoid.  Keep Odoo's normal save/reload behavior if any other company
        // field is edited in the same save.
        if (
            record?.resModel === "res.company" &&
            changedFields.length === 1 &&
            changedFields[0] === "user_ids"
        ) {
            params = { ...params, reload: false };
        }

        return super.save(params);
    },
});
