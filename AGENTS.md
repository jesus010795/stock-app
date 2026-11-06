# AGENTS.md

Django monorepo-less project (Python 3.10, Django ~5.2). StockApp = inventory manager. No REST API, no Docker, no CI, no requirements.txt.

## Commands

- Use the local venv: `venv/bin/python manage.py <cmd>` (activate `venv/bin/activate`). Django is installed only there — do not `pip install` globally.
- Run server: `venv/bin/python manage.py runserver`
- Run tests: `venv/bin/python manage.py test inventory products` (67 tests: MovementForm + MovementCreateView + Movement model baseline + Product stock + Recent activity selector + Low stock queryset + Dashboard low stock block + Movement service + Movement constraints + Movement indexes). `projects`, `employees`, and `warehouses` tests are still empty stubs.
- `manage.py check` passes clean.

## Movement form (completed 09-2026; plan: docs/plan_completar_movementform.md)

- `MovementForm` (`inventory/forms.py`): Spanish labels/help_texts/error_messages, design-system widget classes (`.input`/`.select`/`.textarea`), filtered querysets (active products with stock in the option label, active employees, CREATED/APPROVED projects). `warehouse` is NOT a form field — `Movement.clean()` autofills it from `product.warehouse`.
- `MovementCreateView` (`inventory/views.py`): `?producto=<pk>` prefills (garbage-safe); `form_valid` sets `created_by`, saves inside `try/except ValidationError` and re-injects errors with `form.add_error` → insufficient stock re-renders the form (no 500). The stock rule stays in `Movement.save()` only.

## Architecture

- 5 apps: `products` (Category/Unit/Product), `projects` (Project), `inventory` (Movement), `warehouses` (Warehouse), `employees` (Department/Employee).
- **`Movement` is the single source of truth for stock.** Stock is always computed by aggregation (`Movement.get_stock_for_product`, `MovementQuerySet.stock`, `MovementQuerySet.stock_by_product`, `ProductQuerySet.with_stock`) — never stored on Product. The formula lives only in `signed_quantity_expression()` and `stock_expression()` (`inventory/models.py`); `products` reuses it with the `movements__` prefix through a deferred import to avoid the `products` ↔ `inventory` cycle. Keep it that way; don't reintroduce a `current_stock` field.
- The dashboard activity feed lives in `inventory/selectors.py` (`recent_activity()`), not in `Movement`; it combines movements, projects, and employees for the view and uses `select_related("department")` to avoid the Employee.department N+1.
- `ProductQuerySet.low_stock()` filters and orders by severity in SQL (exhausted first, then by stock level) and returns a **lazy queryset**; `with_stock()` preloads `category`/`unit`/`warehouse` to avoid N+1. The dashboard went from 12 to 6 queries with identical output.
- The dashboard low-stock card asks for the total (`count()` on the unsliced queryset) and the top-6 (`list(qs[:LOW_STOCK_DISPLAY_LIMIT])`) separately; the limit lives only in `inventory/views.py` (`LOW_STOCK_DISPLAY_LIMIT = 6`) and the template receives `low_stock_count` + a materialized `low_stock_products` list (no `|length`/`|slice` on querysets). The block is 2 queries but transfers 6 rows instead of the full set.
- Business rules live in `inventory/models.py` `Movement.clean()`/`save()` (~lines 172–231): quantity > 0, no-negative stock on EXIT/AJUST-OUT, EXIT requires APPROVED project or `reason`, warehouse inherited from `product.warehouse`, employee required. `Movement` has no delete permission in admin.
- Single-row invariants are ALSO enforced by DB `CheckConstraint`s in `Movement.Meta.constraints`: `movement_quantity_positive` (quantity > 0) and `movement_adjustment_type_coherent` (AJUST ⇔ adjustment_type in IN/OUT). They protect paths that bypass Python (`bulk_create`, `update()`, raw SQL). Two gotchas when writing CheckConstraints on SQLite: SQL three-valued logic (a branch evaluating to NULL passes the CHECK — make every branch boolean with explicit `isnull` checks) and the migration rebuilds the table (SQLite has no `ADD CONSTRAINT`), so audit the data BEFORE migrating. The no-negative-stock rule is cross-row (sum of movements) and CANNOT be a CheckConstraint — it stays in `save()`.
- `Movement.Meta.indexes` keeps only `movement_type` and `created_at` (measured with `EXPLAIN QUERY PLAN`, commits 48–50): FK columns are auto-indexed by Django and `unique=True` fields get an implicit index, so never add explicit indexes for them. The same cleanup removed the duplicate indexes in `products` (category/sku/name), `projects` (code) and `warehouses` (code); remaining explicit indexes (`is_active`, `status`, `warehouse_type`) are real non-FK, non-unique columns. If a real query filters `product + movement_type` together appears, re-add the composite `(product, movement_type)` index.
- Movement writes go through `register_movement()` (`inventory/services.py`), wrapped in `transaction.atomic()`: it coordinates the use case, it does NOT re-validate. Row rules and the stock rule stay in `Movement.clean()`/`save()` so the admin write path (`save_model` → `save()`) remains protected too. `MovementCreateView.form_valid` calls the service and re-injects `ValidationError`s into the form.
- All FKs to parent records use `on_delete=PROTECT`; deletes are custom-protected across apps.

## Conventions & gotchas

- All user-facing text is **Spanish** (model `verbose_name`, admin, templates, error messages, docs). Keep new strings in Spanish.
- Docs are authoritative but **gitignored**: `docs/README.md` (spec, model tables, business rules), `docs/resumen_*.md` (change logs). `commits.txt` (also gitignored) records intended commit history and may drift from `git log`. Every new block in `commits.txt` MUST start with its commit number (`commit N (...)`); derive N from `git log --oneline | wc -l` + 1 and mark entries as executed once they appear in `git log`.
- `db.sqlite3` and `media/` are gitignored (local only); migrations are tracked. A fresh clone needs `migrate`.
- Frontend: plain Django templates in `templates/` (`base.html` = sidebar + topbar + content; `inventory/home.html` is the single view) + hand-written CSS in `static/css/` (`base.css`, `main.css`, `components.css`, `dashboard.css`). No JS framework.
- `Employee` has NO `.active()` queryset method (unlike `Product`/`Project`) — use `filter(is_active=True)`, and `select_related("department")` in any option queryset (`Employee.__str__` touches `department.name` → N+1 otherwise).