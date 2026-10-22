/** @odoo-module **/

import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { actionService } from "@web/webclient/actions/action_service";

/*
 * Advanced Active-Company scope for Accounting
 * ---------------------------------------------
 * Security remains Odoo-native: record rules use `company_ids` from
 * `allowed_company_ids`.  We do NOT add a global rule using `company_id`.
 *
 * Instead, whenever an Accounting action is opened, only that action receives
 * `allowed_company_ids: [user.activeCompany.id]`.  The global company selector
 * and the user's allowed companies remain untouched outside Accounting.
 */

const ACCOUNTING_MODELS = new Set([
    "account.move",
    "account.move.line",
    "account.journal",
    "account.journal.group",
    "account.account",
    "account.group",
    "account.payment",
    "account.payment.term",
    "account.bank.statement",
    "account.bank.statement.line",
    "account.tax",
    "account.tax.group",
    "account.tax.repartition.line",
    "account.fiscal.position",
    "account.reconcile.model",
    "account.reconcile.model.line",
    "account.invoice.report",
    "account.change.lock.date",
    "account.lock.exception",
    "account.analytic.account",
    "account.analytic.line",
    "account.analytic.plan",
    "account.analytic.applicability",
    "account.report.external.value",
]);

function isAccountingAction(action) {
    if (!action) {
        return false;
    }
    if (action.context?.zofirm_accounting_scope) {
        return true;
    }
    if (action.type === "ir.actions.client" && action.tag === "account_report") {
        return true;
    }
    const model = action.res_model || action.model;
    return ACCOUNTING_MODELS.has(model);
}

function scopedContext(context = {}) {
    const companyId = user.activeCompany?.id;
    if (!companyId) {
        return context || {};
    }
    return {
        ...(context || {}),
        allowed_company_ids: [companyId],
        zofirm_accounting_scope: true,
    };
}

patch(actionService, {
    start(env) {
        const service = super.start(...arguments);
        const originalDoAction = service.doAction.bind(service);
        const originalLoadAction = service.loadAction.bind(service);

        service.doAction = async (actionRequest, options = {}) => {
            let accountingAction = false;

            if (typeof actionRequest === "object" && actionRequest !== null) {
                accountingAction = isAccountingAction(actionRequest);
            } else {
                // Menu actions usually arrive as an id/xmlid. Loading the action
                // here is read-only and lets us identify its model/tag before the
                // real execution. Odoo's action endpoint is cached, so the second
                // load performed by doAction is normally served from cache.
                try {
                    const preview = await originalLoadAction(
                        actionRequest,
                        options.additionalContext
                    );
                    accountingAction = isAccountingAction(preview);
                } catch {
                    // Never block normal navigation if an action cannot be
                    // previewed; let Odoo handle the original request.
                    accountingAction = false;
                }
            }

            if (accountingAction && user.activeCompany?.id) {
                options = {
                    ...options,
                    additionalContext: scopedContext(options.additionalContext),
                };
            }
            return originalDoAction(actionRequest, options);
        };

        // Some components call loadAction directly. Keep their returned action
        // context consistent too, without changing the user's global context.
        service.loadAction = async (actionRequest, context = {}) => {
            const action = await originalLoadAction(actionRequest, context);
            if (isAccountingAction(action) && user.activeCompany?.id) {
                action.context = scopedContext(action.context);
            }
            return action;
        };

        return service;
    },
});
