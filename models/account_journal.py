from odoo import _, api, models
from odoo.exceptions import AccessError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _zofirm_is_plain_bookkeeper(self):
        user = self.env.user
        return (
            user.has_group("account.group_account_user")
            and not user.has_group("zofirm_accounting_role.group_zofirm_account_supervisor")
            and not user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
            and not user.has_group("account.group_account_manager")
        )


    @api.model
    def _zofirm_can_delete_journals(self):
        """Supervisor, Manager and Accounting Administrator may delete journals."""
        user = self.env.user
        return (
            user.has_group("zofirm_accounting_role.group_zofirm_account_supervisor")
            or user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
            or user.has_group("account.group_account_manager")
        )

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ("list", "form"):
            if self._zofirm_can_delete_journals():
                arch.set("delete", "1")
            elif self._zofirm_is_plain_bookkeeper():
                arch.set("delete", "0")
        return arch, view

    def unlink(self):
        # The ACLs grant delete to Supervisor/Manager/Administrator. Keep an
        # explicit backend guard so plain Bookkeeper can never bypass the UI.
        if self._zofirm_is_plain_bookkeeper():
            raise AccessError(_("Bookkeepers are not allowed to delete journals."))
        return super().unlink()

    def write(self, vals):
        if self._zofirm_is_plain_bookkeeper() and "active" in vals:
            target_active = bool(vals["active"])
            if any(bool(journal.active) != target_active for journal in self):
                raise AccessError(_("Bookkeepers are not allowed to archive or unarchive journals."))
        return super().write(vals)
