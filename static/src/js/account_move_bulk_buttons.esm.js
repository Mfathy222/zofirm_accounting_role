/** @odoo-module **/

import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { onWillStart, useEffect } from "@odoo/owl";

function toggleElements(elements, shouldShow) {
    for (const el of elements) {
        el.classList.toggle("d-none", !shouldShow);
    }
}

async function getZofirmAccountingRoleFlags() {
    const [isAccountingUser, isSupervisor, isManager, isAdministrator] = await Promise.all([
        user.hasGroup("account.group_account_user"),
        user.hasGroup("zofirm_accounting_role.group_zofirm_account_supervisor"),
        user.hasGroup("zofirm_accounting_role.group_zofirm_account_manager"),
        user.hasGroup("account.group_account_manager"),
    ]);
    return {
        isAccountingUser,
        isSupervisor,
        isManager,
        isAdministrator,
        isPlainBookkeeper:
            isAccountingUser && !isSupervisor && !isManager && !isAdministrator,
        isAccountDeleteRestricted:
            isAccountingUser && !isSupervisor && !isManager && !isAdministrator,
        canDeleteAccountingMasterData:
            isSupervisor || isManager || isAdministrator,
        canDeleteJournalEntries:
            isSupervisor || isManager || isAdministrator,
    };
}

function restrictZofirmStaticActions(items, resModel, roleFlags) {
    if (!roleFlags) {
        return items;
    }

    if (resModel === "account.account") {
        // Chart of Accounts:
        // - Delete: Supervisor, Manager and Accounting Administrator.
        // - Delete hidden for plain Bookkeeper.
        // - Archive / Unarchive hidden only for plain Bookkeeper.
        if (items.delete) {
            items.delete.isAvailable = () => roleFlags.canDeleteAccountingMasterData;
        }
        if (roleFlags.isPlainBookkeeper) {
            if (items.archive) {
                items.archive.isAvailable = () => false;
            }
            if (items.unarchive) {
                items.unarchive.isAvailable = () => false;
            }
        }
    } else if (resModel === "account.journal") {
        // Journals: Supervisor, Manager and Administrator can delete one or
        // multiple journals. Bookkeeper cannot delete or archive/unarchive.
        if (items.delete) {
            items.delete.isAvailable = () => roleFlags.canDeleteAccountingMasterData;
        }
        if (roleFlags.isPlainBookkeeper) {
            if (items.archive) {
                items.archive.isAvailable = () => false;
            }
            if (items.unarchive) {
                items.unarchive.isAvailable = () => false;
            }
        }
    } else if (resModel === "account.move") {
        // Journal Entries: expose the standard Delete action to Supervisor,
        // Manager and Accounting Administrator. The backend still enforces
        // Odoo's native audit/hash/business restrictions.
        if (items.delete) {
            items.delete.isAvailable = () => roleFlags.canDeleteJournalEntries;
        }
    }
    return items;
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);

        this.zofirmAccountingRoleFlags = null;
        onWillStart(async () => {
            this.zofirmAccountingRoleFlags = await getZofirmAccountingRoleFlags();
        });

        useEffect(
            () => {
                this._zofirmUpdateAccountMoveBulkButtons();
            },
            () => [
                this.model.root.selection
                    .map((record) => `${record.resId}:${record.data?.state || ""}`)
                    .join("|"),
                this.model.root.isDomainSelected,
            ]
        );
    },

    _zofirmIsAccountMoveList() {
        return this.props?.resModel === "account.move" || this.model?.root?.resModel === "account.move";
    },

    _zofirmUpdateAccountMoveBulkButtons() {
        if (!this._zofirmIsAccountMoveList() || !this.rootRef?.el) {
            return;
        }

        const selection = this.model.root.selection || [];
        let hasDraft = selection.some((record) => record.data?.state === "draft");
        let hasPosted = selection.some((record) => record.data?.state === "posted");

        if (this.model.root.isDomainSelected && !selection.length) {
            hasDraft = true;
            hasPosted = true;
        }

        toggleElements(
            this.rootRef.el.querySelectorAll(".zofirm_reset_to_draft_btn"),
            hasPosted
        );
        toggleElements(
            this.rootRef.el.querySelectorAll(".zofirm_confirm_btn"),
            hasDraft
        );
    },

    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems(...arguments);
        return restrictZofirmStaticActions(
            items,
            this.props?.resModel || this.model?.root?.resModel,
            this.zofirmAccountingRoleFlags
        );
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.zofirmAccountingRoleFlags = null;
        onWillStart(async () => {
            this.zofirmAccountingRoleFlags = await getZofirmAccountingRoleFlags();
        });
    },

    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems(...arguments);
        return restrictZofirmStaticActions(
            items,
            this.props?.resModel || this.model?.root?.resModel,
            this.zofirmAccountingRoleFlags
        );
    },
});
