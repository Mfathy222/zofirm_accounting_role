from odoo import _, models
from odoo.exceptions import UserError


class AccountChangeLockDate(models.TransientModel):
    _inherit = "account.change.lock.date"

    def change_lock_date(self):
        """Allow Zofirm Accounting Manager to use Odoo's native Lock Dates.

        Odoo 19 performs the Billing/Accounting Administrator group check in
        this transient wizard *before* it writes on ``res.company``.  Granting
        access to the menu or overriding ``res.company.write`` therefore does
        not bypass that check.

        Keep the native Administrator flow untouched.  For the custom Manager,
        run the same native preparation/validation helpers and only bypass the
        final group gate.  The actual lock-date write still goes through
        ``_change_lock_date()``, which uses Odoo's native validation logic and
        writes the active company with sudo.
        """
        self.ensure_one()

        # Never alter Odoo's standard Accounting Administrator behaviour.
        if self.env.user.has_group("account.group_account_manager"):
            return super().change_lock_date()

        if not self.env.user.has_group(
            "zofirm_accounting_role.group_zofirm_account_manager"
        ):
            raise UserError(_("Only Billing Administrators are allowed to change lock dates!"))

        # The native wizard is intended for the active company only.  Keep that
        # restriction explicit for the custom Manager.
        if self.company_id != self.env.company:
            raise UserError(_("You can only change Lock Dates for the active company."))

        # Reuse Odoo 19's own helpers so Hard Lock, future-date checks, lock
        # exceptions, tax/fiscal report external values, etc. remain native.
        exception_vals_list = self._prepare_exception_values()
        changed_lock_date_values = self._prepare_lock_date_values(
            exception_vals_list=exception_vals_list
        )

        if exception_vals_list:
            # account.lock_exception is normally managed by Accounting Admin.
            # Use sudo only for the technical creation while keeping the real
            # Manager as the exception's user/reason through the values prepared
            # by Odoo above.
            self.env["account.lock_exception"].sudo().create(exception_vals_list)

        self._change_lock_date(changed_lock_date_values)
        return {"type": "ir.actions.act_window_close"}
