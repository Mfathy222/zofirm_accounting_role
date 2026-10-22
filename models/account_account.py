from odoo import _, api, models, Command
from odoo.exceptions import AccessError


class AccountAccount(models.Model):
    _inherit = "account.account"

    @api.model
    def _zofirm_is_accounting_role(self):
        user = self.env.user
        return (
            not self.env.su
            and (
                user.has_group("account.group_account_user")
                or user.has_group("account.group_account_manager")
            )
        )

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
    def _zofirm_can_delete_accounts(self):
        """Supervisor, Manager and Accounting Administrator may delete COA accounts.

        This applies to both a single account and a multi-record selection.
        Odoo's native business constraints still apply (for example, accounts
        that cannot legally be removed because they are already in use).
        """
        user = self.env.user
        return (
            user.has_group("zofirm_accounting_role.group_zofirm_account_supervisor")
            or user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
            or user.has_group("account.group_account_manager")
        )

    @api.model
    def _zofirm_is_account_delete_restricted(self):
        """Plain Bookkeeper cannot delete COA accounts."""
        return not self._zofirm_can_delete_accounts()

    @api.model_create_multi
    def create(self, vals_list):
        """Create new COA accounts for the Accounting action company only.

        The action context is narrowed to one allowed company, while Odoo's native record rules remain untouched.  Keep new accounts assigned to that
        company and ignore stale multi-company mapping payloads.
        """
        if self._zofirm_is_accounting_role():
            active_company_id = self.env.company.id
            vals_list = [dict(vals) for vals in vals_list]
            for vals in vals_list:
                vals["company_ids"] = [Command.set([active_company_id])]
                # The custom view removes code_mapping_ids, but discard stale
                # client payloads too (e.g. an old browser tab/assets cache).
                vals.pop("code_mapping_ids", None)
        return super().create(vals_list)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ("list", "form"):
            if self._zofirm_can_delete_accounts():
                # Explicitly enable the standard Odoo Delete action for Supervisor,
                # Manager and Accounting Administrator, including multi-selection
                # in the Chart of Accounts list view.
                arch.set("delete", "1")
            else:
                arch.set("delete", "0")
        return arch, view

    def write(self, vals):
        vals = dict(vals)

        # Active-company-only Accounting: don't allow a normal UI write to
        # reassign an account to another selected company.  This also makes
        # old/stale forms deterministic after upgrading the module.
        if self._zofirm_is_accounting_role():
            if "company_ids" in vals:
                vals["company_ids"] = [Command.set([self.env.company.id])]
            # Do not process Odoo's multi-company code-mapping payload.  The
            # standard `code` inverse already writes the active company's
            # company-dependent code.
            vals.pop("code_mapping_ids", None)

        # Archive / Unarchive is specifically blocked for plain Bookkeeper.
        if self._zofirm_is_plain_bookkeeper() and "active" in vals:
            target_active = bool(vals["active"])
            if any(bool(account.active) != target_active for account in self):
                raise AccessError(
                    _("Bookkeepers are not allowed to archive or unarchive accounts.")
                )

        return super().write(vals)

    def unlink(self):
        # `unlink()` works on recordsets, so this covers both deleting one
        # account and deleting a selected group of accounts in one action.
        if not self._zofirm_can_delete_accounts():
            raise AccessError(
                _("Bookkeepers are not allowed to delete accounts.")
            )
        return super().unlink()
