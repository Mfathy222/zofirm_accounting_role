from odoo import api, models


LEGACY_ACTIVE_COMPANY_RULE_XMLIDS = (
    "rule_bookkeeper_current_company_move",
    "rule_bookkeeper_current_company_move_line",
    "rule_bookkeeper_current_company_journal",
    "rule_bookkeeper_current_company_journal_group",
    "rule_bookkeeper_current_company_account",
    "rule_bookkeeper_current_company_account_group",
    "rule_bookkeeper_current_company_tax",
    "rule_bookkeeper_current_company_tax_group",
    "rule_bookkeeper_current_company_tax_repartition",
    "rule_bookkeeper_current_company_invoice_report",
    "rule_bookkeeper_current_company_fiscal_position",
    "rule_bookkeeper_current_company_bank_statement",
    "rule_bookkeeper_current_company_bank_statement_line",
    "rule_bookkeeper_current_company_reconcile_model",
    "rule_bookkeeper_current_company_reconcile_model_line",
    "rule_bookkeeper_current_company_payment",
    "rule_bookkeeper_current_company_payment_term",
    "rule_bookkeeper_current_company_report_external_value",
    "rule_bookkeeper_current_company_analytic_account",
    "rule_bookkeeper_current_company_analytic_line",
    "rule_bookkeeper_current_company_analytic_applicability",
    "rule_bookkeeper_current_company_analytic_distribution",
)


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def zofirm_cleanup_legacy_active_company_rules(self):
        """Remove global rules created by older Zofirm Accounting Role versions.

        Versions up to 19.0.1.3.2 enforced the current company with GLOBAL
        record rules such as ``company_id in [company_id]``.  Those rules are
        stricter than Odoo's native multi-company rules and can make a Journal
        Item visible in a list yet unreadable when opening its form or a report
        drill-down.

        The new design keeps Odoo's native rules and narrows
        ``allowed_company_ids`` only inside Accounting actions.  On upgrade,
        stale global rules must be physically removed from databases that have
        used older module versions (especially staging/live databases).
        """
        imd = self.env["ir.model.data"].sudo().search([
            ("module", "=", "zofirm_accounting_role"),
            ("name", "in", list(LEGACY_ACTIVE_COMPANY_RULE_XMLIDS)),
            ("model", "=", "ir.rule"),
        ])
        for data in imd:
            rule = self.sudo().browse(data.res_id).exists()
            if rule:
                rule.unlink()
        # Remove external IDs as well so the old records cannot be resurrected
        # accidentally by a later cache/update cycle.
        imd.exists().unlink()
        self.env.registry.clear_cache()
        return True
