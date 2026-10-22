from copy import deepcopy
import re

from odoo import models


class AccountReport(models.Model):
    _inherit = "account.report"

    def _zofirm_company_id_from_report_options(self, options=None):
        """Return the company explicitly carried by report options, if any.

        Odoo rebuilds report options during PDF/XLSX exports.  The export HTTP
        request can have a different ``env.company`` from the one used to render
        the report currently visible in the browser.  Therefore export code must
        not infer the company again from ``env.company`` when the report options
        already carry the exact company selected for that report.
        """
        options = options or {}

        company_id = options.get("zofirm_active_company_id")
        if company_id:
            return int(company_id)

        companies = options.get("companies") or []
        if companies:
            first_company = companies[0]
            if isinstance(first_company, dict) and first_company.get("id"):
                return int(first_company["id"])

        forced_companies = options.get("forced_companies") or []
        if forced_companies:
            return int(forced_companies[0])

        return False

    def _zofirm_current_company_id(self):
        """Return the browser's current company (first allowed company)."""
        allowed_company_ids = self.env.context.get("allowed_company_ids") or []
        return int(allowed_company_ids[0]) if allowed_company_ids else self.env.company.id

    def _zofirm_report_company(self, options=None, *, prefer_options=False):
        """Resolve the single company used by the Accounting report.

        Normal interactive rendering follows the browser's current company.
        Export rendering follows the company already stored in the report options,
        so the XLSX/PDF always reproduces exactly what the user sees on screen.
        """
        company_id = False
        if prefer_options:
            company_id = self._zofirm_company_id_from_report_options(options)

        if not company_id:
            company_id = self._zofirm_current_company_id()

        # Reading the company name/currency is metadata needed to build report
        # options.  Report figures themselves are still computed with the user's
        # regular accounting permissions in the scoped environment below.
        return self.env["res.company"].sudo().browse(company_id).exists()[:1]

    @staticmethod
    def _zofirm_force_company_options(options, company):
        """Mutate an options dict so every Odoo report path uses one company."""
        if not company:
            return options

        options["forced_companies"] = [company.id]
        options["companies"] = [{
            "id": company.id,
            "name": company.name,
            "currency_id": company.currency_id.id,
        }]
        options["zofirm_active_company_id"] = company.id
        options["zofirm_show_active_company_name"] = True
        return options

    def _init_options_companies(self, options, previous_options):
        """Keep the report on the active company without breaking exports.

        For the interactive UI, the first ``allowed_company_ids`` entry is Odoo's
        current company.  For print/export re-generation, however, the source of
        truth is the company already embedded in the incoming report options.
        This prevents XLSX/PDF from silently switching to the user's default
        company when Odoo rebuilds options in a separate HTTP request.
        """
        previous_options = previous_options or {}
        is_export = previous_options.get("export_mode") in {"file", "print"}
        company = self._zofirm_report_company(previous_options, prefer_options=is_export)

        safe_previous = deepcopy(previous_options)
        if company:
            safe_previous["forced_companies"] = [company.id]

        super()._init_options_companies(options, safe_previous)
        self._zofirm_force_company_options(options, company)

    def get_report_company_ids(self, options):
        """Use the company stored in report options, not a fresh env.company."""
        company_id = self._zofirm_company_id_from_report_options(options)
        return [company_id] if company_id else [self._zofirm_current_company_id()]

    def _zofirm_scoped_export_self_and_options(self, options):
        """Build the exact one-company environment used for PDF/XLSX export."""
        scoped_options = deepcopy(options or {})
        company = self._zofirm_report_company(scoped_options, prefer_options=True)
        if not company:
            company = self._zofirm_report_company()

        self._zofirm_force_company_options(scoped_options, company)

        # The export methods recompute report lines with no_format=True.  Make
        # env.company/env.companies consistent with the options during that whole
        # recomputation.  This is intentionally export-only, so Journal Items and
        # normal navigation continue to rely on Odoo's native multi-company rules.
        scoped_self = self.with_company(company).with_context(
            allowed_company_ids=[company.id],
            zofirm_accounting_scope=True,
            zofirm_active_company_id=company.id,
        )
        return scoped_self, scoped_options



    def get_default_report_filename(self, options, extension):
        """Keep Odoo's filename logic but make report dates human-readable.

        Odoo 19 removes slashes from dates when building accounting-report file
        names (e.g. ``06102026``).  A literal ``/`` cannot be used in Windows
        file names, so this customization renders those date tokens as
        ``06-10-2026`` instead.  The report name, company name, and extension
        remain exactly as generated by Odoo.
        """
        filename = super().get_default_report_filename(options, extension)

        # Only transform standalone DDMMYYYY tokens generated by Odoo's
        # accounting-report filename logic.  This also handles range reports,
        # e.g. 01012026_29122026 -> 01-01-2026_29-12-2026.
        return re.sub(
            r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)",
            r"\1-\2-\3",
            filename,
        )

    def export_to_xlsx(self, options, response=None):
        """Export the same company and figures currently displayed on screen."""
        self.ensure_one()
        scoped_self, scoped_options = self._zofirm_scoped_export_self_and_options(options)
        return super(AccountReport, scoped_self).export_to_xlsx(scoped_options, response=response)

    def export_to_pdf(self, options):
        """Keep PDF export on the exact same company as the interactive report."""
        self.ensure_one()
        scoped_self, scoped_options = self._zofirm_scoped_export_self_and_options(options)
        return super(AccountReport, scoped_self).export_to_pdf(scoped_options)
