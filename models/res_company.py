from markupsafe import Markup

from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.fields import Command


LOCK_DATE_FIELDS = {
    "fiscalyear_lock_date",
    "tax_lock_date",
    "sale_lock_date",
    "purchase_lock_date",
    "hard_lock_date",
}


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _zofirm_is_custom_account_manager(self):
        user = self.env.user
        return (
            not self.env.su
            and user.has_group("zofirm_accounting_role.group_zofirm_account_manager")
            and not user.has_group("account.group_account_manager")
        )

    @api.model_create_multi
    def create(self, vals_list):
        """Allow Accounting Administrator to create companies.

        Native company creation performs operations (partner creation,
        localization bootstrap, user/company linkage) which normally require
        Settings administration rights. For a Role=User who is Accounting
        Administrator, execute that native creation path as sudo, then add the
        real user to the newly created companies.
        """
        user = self.env.user
        accounting_admin_only = (
            not self.env.su
            and user.has_group("account.group_account_manager")
            and not user.has_group("base.group_erp_manager")
        )
        if not accounting_admin_only:
            return super().create(vals_list)

        companies = super(ResCompany, self.sudo()).create(vals_list)
        user.sudo().write({
            "company_ids": [Command.link(company.id) for company in companies],
        })
        return companies.with_env(self.env)

    def write(self, vals):
        """Apply Manager lock-date restriction and log company user changes.

        The Users field is visible to Accounting Administrator.  When that
        administrator adds/removes accepted users from the Company form, write
        a clear note in the company chatter.
        """
        is_account_admin = (
            not self.env.su
            and self.env.user.has_group("account.group_account_manager")
        )
        track_users = is_account_admin and "user_ids" in vals
        users_before = {company.id: company.user_ids for company in self} if track_users else {}

        is_custom_manager = self._zofirm_is_custom_account_manager()
        if is_custom_manager:
            forbidden = set(vals) - LOCK_DATE_FIELDS
            if forbidden:
                raise AccessError(_(
                    "Managers may only change accounting Lock Dates on companies."
                ))
            # The native Lock Dates wizard is for the currently active company.
            if any(company.id != self.env.company.id for company in self):
                raise AccessError(_(
                    "You can only change Lock Dates for the active company."
                ))

            # Odoo 19's native lock-date flow performs an additional Billing /
            # Accounting Administrator group check when the company lock fields
            # are written.  Our custom Manager is intentionally not a member of
            # account.group_account_manager, so a normal super().write() would
            # still raise: "Only Billing Administrators are allowed to change
            # lock dates!" even though the Manager has access to the native
            # wizard.
            #
            # We already restrict this branch to ONLY the supported lock-date
            # fields and ONLY the active company.  Execute the native company
            # write as sudo so the standard lock-date validations/constraints
            # keep running while bypassing only that group gate.
            return super(ResCompany, self.sudo()).write(vals)

        result = super().write(vals)

        if track_users:
            # Keep Odoo's multi-company invariant valid: a user's default
            # company must always be one of their allowed companies. Removing
            # that company through res.company.user_ids otherwise leaves an
            # invalid session state and can crash @web/core/user on reload.
            for company in self:
                before = users_before.get(company.id, self.env["res.users"])
                after = company.user_ids
                removed = before - after

                # Never allow the logged-in user to remove their own access
                # from the currently active company without a company switch.
                if company.id == self.env.company.id and self.env.user in removed:
                    raise AccessError(_(
                        "You cannot remove your own access from the active company. "
                        "Switch to another company first."
                    ))

                # If another user's default company is removed, move their
                # default to one of their remaining allowed companies. If no
                # company remains, reject the operation instead of creating a
                # broken user/session state.
                for removed_user in removed.sudo():
                    if removed_user.company_id != company:
                        continue
                    remaining = removed_user.company_ids - company
                    if not remaining:
                        raise AccessError(_(
                            "You cannot remove %(user)s from %(company)s because it is "
                            "their only/default company. Assign another company to the "
                            "user first.",
                            user=removed_user.display_name,
                            company=company.display_name,
                        ))
                    removed_user.sudo().write({"company_id": remaining[0].id})

            author_id = self.env.user.partner_id.id
            for company in self:
                before = users_before.get(company.id, self.env["res.users"])
                after = company.user_ids
                added = after - before
                removed = before - after
                if not (added or removed):
                    continue
                if not hasattr(company, "message_post"):
                    continue

                parts = []
                if added:
                    parts.append(
                        Markup("<b>%s</b>: %s")
                        % (_("Users Added"), ", ".join(added.mapped("display_name")))
                    )
                if removed:
                    parts.append(
                        Markup("<b>%s</b>: %s")
                        % (_("Users Removed"), ", ".join(removed.mapped("display_name")))
                    )
                body = Markup("<br/>").join(parts)
                # sudo guarantees the technical chatter write without changing
                # the visible author of the log entry.
                company.sudo().message_post(
                    body=body,
                    subtype_xmlid="mail.mt_note",
                    author_id=author_id,
                )

        return result
