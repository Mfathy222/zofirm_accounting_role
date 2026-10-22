{
    "name": "Zofirm Accounting Role",
    "summary": "Accounting roles with native multi-company security and accounting-only active-company scope",
    "version": "19.0.1.3.9",
    "category": "Accounting/Accounting",
    "author": "SIJILACC",
    "contributors": [
           "Mohamed Fathy. <mohammed.fathy222@gmail.com>",
       ],
    "license": "LGPL-3",
    "depends": [
        "account_reports",
        "account_accountant",
    ],
    "data": [
        "security/zofirm_groups.xml",
        "security/ir.model.access.csv",
        "data/cleanup_legacy_active_company.xml",
        "security/zofirm_rules.xml",
        "data/repair_user_company_consistency.xml",
        "views/res_company_views.xml",
        "views/account_account_views.xml",
        "views/account_move_views.xml",
        "views/accounting_scope_actions.xml",
        "views/accounting_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zofirm_accounting_role/static/src/js/account_move_bulk_buttons.esm.js",
            "zofirm_accounting_role/static/src/js/company_user_save_no_reload.esm.js",
            "zofirm_accounting_role/static/src/xml/account_report_company_header.xml",
        ],
    },
    "installable": True,
    "application": False,
}
