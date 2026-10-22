from odoo import api, models
from odoo.fields import Command


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _zofirm_repair_default_company_access(self):
        """Repair invalid Odoo multi-company user states.

        Odoo 19's web bootstrap requires each user's default ``company_id`` to
        exist in the allowed-company relation used by ``_get_company_ids()``.
        Previous company-user edits can leave those fields inconsistent.

        Rules:
        * if the default company is active, restore only that company to the
          user's allowed companies;
        * if the default company is inactive but the user already has another
          active allowed company, move the default to the first active one;
        * never grant an unrelated company.
        """
        users = self.sudo().with_context(active_test=False).search([])
        for user in users:
            default_company = user.company_id
            if not default_company:
                continue

            all_allowed = user.with_context(active_test=False).company_ids
            active_allowed = all_allowed.filtered("active")

            if default_company.active:
                if default_company not in all_allowed:
                    user.write({
                        "company_ids": [Command.link(default_company.id)],
                    })
            elif active_allowed:
                user.write({"company_id": active_allowed[0].id})

        # _get_company_ids is orm-cached in Odoo 19.  A registry cache clear
        # makes the repaired relation visible immediately after module upgrade.
        self.env.registry.clear_cache()
        return True
