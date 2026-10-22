from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    zofirm_active_company_name = fields.Char(
        string="Active Company",
        compute="_compute_zofirm_active_company_name",
        readonly=True,
    )

    @api.depends_context("company")
    def _compute_zofirm_active_company_name(self):
        company_name = self.env.company.display_name
        for move in self:
            move.zofirm_active_company_name = company_name

    @api.model
    def _zofirm_is_delete_restricted_bookkeeper(self):
        """Return True only for the Bookkeeper accounting level.

        Supervisor and Manager both imply the normal Odoo Bookkeeper group, so
        they must be explicitly excluded from the Bookkeeper delete restriction.
        Accounting Administrator is excluded as well.
        """
        user = self.env.user
        return (
            user.has_group("account.group_account_user")
            and not user.has_group("zofirm_accounting_role.group_zofirm_account_supervisor")
            and not user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
            and not user.has_group("account.group_account_manager")
        )

    @api.model
    def _zofirm_can_delete_journal_entries(self):
        """Supervisor, Manager and Accounting Administrator may delete journal entries."""
        user = self.env.user
        return (
            user.has_group("zofirm_accounting_role.group_zofirm_account_supervisor")
            or user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
            or user.has_group("account.group_account_manager")
        )

    @api.model
    def _zofirm_can_bulk_manage_journal_entries(self):
        """Roles allowed to use the Journal Entries bulk state actions."""
        user = self.env.user
        return (
            user.has_group("account.group_account_user")
            or user.has_group("account.group_account_manager")
        )

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)

        # account.move is also used by invoices. Hide Delete only for manual
        # Journal Entries and only for the Bookkeeper level.
        ctx = options.get("context") or self.env.context
        move_type = ctx.get("default_move_type", "entry")
        if move_type == "entry" and view_type in ("form", "list"):
            if self._zofirm_is_delete_restricted_bookkeeper():
                arch.set("delete", "0")
            elif self._zofirm_can_delete_journal_entries():
                # Make Delete available both inside the Journal Entry form and
                # from a list selection (single or multiple records).
                arch.set("delete", "1")

        return arch, view

    def unlink(self):
        if self._zofirm_is_delete_restricted_bookkeeper() and any(
            move.move_type == "entry" for move in self
        ):
            raise AccessError(
                _("Bookkeepers are not allowed to delete journal entries.")
            )
        return super().unlink()

    def action_zofirm_bulk_reset_to_draft(self):
        """Reset the selected Posted Journal Entries to Draft."""
        if not self._zofirm_can_bulk_manage_journal_entries():
            raise AccessError(
                _("You are not allowed to reset journal entries to draft.")
            )

        entries = self.filtered(lambda move: move.state == "posted")
        if not entries:
            raise UserError(_("Select at least one posted journal entry."))

        # Delegate to Odoo's native reset-to-draft logic so all standard
        # accounting safeguards (locks, hash restrictions, reconciliations,
        # etc.) remain enforced.
        return entries.button_draft()

    def action_zofirm_bulk_confirm(self):
        """Confirm/post the selected Draft manual Journal Entries."""
        if not self._zofirm_can_bulk_manage_journal_entries():
            raise AccessError(
                _("You are not allowed to confirm journal entries.")
            )

        # The Journal Entries list can contain account.move records whose
        # move_type is not strictly ``entry`` (for example invoice/vendor-bill
        # moves shown in the same accounting list).  Selection in the list is
        # therefore determined by state only.
        entries = self.filtered(lambda move: move.state == "draft")
        if not entries:
            raise UserError(_("Select at least one draft journal entry."))

        # Odoo 19's native multi-entry validation method handles future-dated
        # and hash-restricted entries by opening its normal confirmation wizard.
        return entries.action_validate_moves_with_confirmation()

    @api.ondelete(at_uninstall=False)
    def _unlink_forbid_parts_of_chain(self):
        """Give Supervisor/Manager the same sequence-gap delete privilege as Accounting Administrator.

        Other native Odoo safeguards (for example restrictive audit trail / hash
        protections) remain in force because this only bypasses this specific
        sequence-chain check.
        """
        user = self.env.user
        if (
            user.has_group("zofirm_accounting_role.group_zofirm_account_supervisor")
            or user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
        ):
            return
        return super()._unlink_forbid_parts_of_chain()
