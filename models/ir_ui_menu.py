from odoo import api, models
from odoo.fields import Command


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def zofirm_configure_native_lock_dates(self):
        """Use Odoo's native Lock Dates wizard and restrict it to Zofirm Manager/Admin.

        This method is intentionally idempotent and is called from XML on every
        module install/upgrade.  It also removes the legacy custom lock-date
        wizard records created by older versions of this module.
        """
        env = self.env

        # Remove legacy UI/access records from pre-1.1.0 versions.  The custom
        # TransientModel itself is no longer imported by this module.
        legacy_xmlids = [
            "zofirm_accounting_role.menu_zofirm_lock_dates",
            "zofirm_accounting_role.action_zofirm_lock_dates",
            "zofirm_accounting_role.view_zofirm_lock_date_wizard_form",
            "zofirm_accounting_role.access_zofirm_lock_date_wizard_manager",
            "zofirm_accounting_role.access_zofirm_lock_date_wizard_admin",
        ]
        for xmlid in legacy_xmlids:
            record = env.ref(xmlid, raise_if_not_found=False)
            if record and record.exists():
                record.sudo().unlink()

        manager = env.ref("zofirm_accounting_role.group_zofirm_account_manager")
        administrator = env.ref("account.group_account_manager")

        # Odoo Enterprise defines the native wizard as account.change.lock.date.
        actions = env["ir.actions.act_window"].sudo().search([
            ("res_model", "=", "account.change.lock.date"),
        ])

        menus = self.sudo().browse()
        if actions:
            action_refs = [f"ir.actions.act_window,{action.id}" for action in actions]
            menus = self.sudo().search([("action", "in", action_refs)])

        # Defensive fallback for databases where the action/menu was customized.
        if not menus:
            menus = self.sudo().search([("name", "=", "Lock Dates")])

        # Exactly Manager + Accounting Administrator may see the native Lock Dates menu.
        if menus:
            menus.write({
                "group_ids": [Command.set([manager.id, administrator.id])],
            })

        # If the native action or wizard view itself carries group restrictions,
        # add the custom Manager without removing Odoo's existing restrictions.
        for action in actions:
            if "group_ids" in action._fields:
                action.write({"group_ids": [Command.link(manager.id)]})
            elif "groups_id" in action._fields:
                action.write({"groups_id": [Command.link(manager.id)]})

        views = env["ir.ui.view"].sudo().search([
            ("model", "=", "account.change.lock.date"),
        ])
        for view in views:
            if "group_ids" in view._fields and view.group_ids:
                view.write({"group_ids": [Command.link(manager.id)]})

        return True
