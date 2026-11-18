# Takealot reselling automation

Terraform-provisioned, self-hosted n8n stack plus version-controlled workflows for a Takealot reselling business.

## What is included

| Area | Workflow | What it does |
| --- | --- | --- |
| Diagnostics | `00-api-health-check.json` | Verifies the Takealot API key and reports your offer count |
| Pricing | `01-price-monitoring.json` | Pulls your offers, reads competitor prices from Google Sheets, applies an undercut + minimum-margin rule, PATCHes prices, logs history and alerts Slack |
| Orders | `02-order-processing.json` | Imports sales orders every 15 min, upserts to Postgres, sends a Slack + email digest and creates a Xero invoice |
| Inventory | `03-inventory-sync.json` | Compares supplier stock against Takealot stock and submits offer batch updates |
| Alerts | `04-stock-depletion-alerts.json` | Finds offers at/below the reorder threshold and notifies Slack, email and optionally WhatsApp |
| Reporting | `05-sales-profit-reporting.json` | Imports daily sales, joins cost prices, calculates revenue/fees/COGS/profit, writes to Postgres, Sheets, Slack and email |
| Listings | `06-product-listing-automation.json` | Validates a Google Sheets listing queue, submits an offer batch, polls its status and logs rejects |

Infrastructure (Terraform): n8n main + optional queue-mode worker, PostgreSQL (n8n metadata + a separate `takealot` business database), Redis, Docker network and volumes. Workflow JSON is imported into n8n with the n8n CLI on `terraform apply` and re-imported whenever a file changes.

## Prerequisites

- Docker Engine / Rancher Desktop running on the host
- Terraform >= 1.3
- Python 3 (only to regenerate workflows)
- A Takealot Seller API key (Seller Portal → API Integration → Seller API)

## Quick start

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your real secrets
terraform init
terraform apply
```

Open `http://localhost:5678`, finish the owner setup, then:

1. Create credentials in n8n (exact names used by the workflows):
   - **Takealot Postgres** — host `takealot-postgres`, port `5432`, database `takealot`, user `n8n`, password = `postgres_password`
   - **Takealot Google Sheets** — OAuth2 account with access to your spreadsheets
   - **Takealot SMTP** — outgoing mail server used by the email nodes
   - **Takealot Xero** — OAuth2 app (optional; only needed for `02-order-processing.json`)
2. Attach each credential to the corresponding nodes in the imported workflows.
3. Run `00-api-health-check.json` manually to confirm API access, then activate the workflows you want.

Imported workflows are **inactive by default** so nothing runs before credentials are set.

## Google Sheets data contracts

| Spreadsheet (variable) | Tab | Columns |
| --- | --- | --- |
| `google_sheets_competitors_id` | `CompetitorPrices` | `sku`, `competitor_price` |
| `google_sheets_catalogue_id` | `Catalogue` | `sku`, `cost_price` |
| `google_sheets_catalogue_id` | `Listings` | `sku`, `barcode`, `selling_price`, `rrp`, `quantity`, `merchant_warehouse_id`, `leadtime_days` |
| `google_sheets_report_id` | `DailyReport` | created by the append node (`report_date`, `revenue`, `fees`, `cogs`, `profit`, `orders`) |

## Business database

`sql/001_schema.sql` is applied automatically on apply. Tables: `offers`, `price_history`, `orders`, `sales`, `inventory`, `profit_daily`, `listing_queue`, `automation_log`.

The inventory workflow reads `inventory.supplier_stock` and `inventory.reserved_stock`; populate those rows from your supplier/warehouse system (or a separate n8n workflow) for stock sync to have data to push.

## Configuration

All settings live in `terraform/variables.tf`. Secrets should be supplied via `terraform.tfvars` (gitignored) or `TF_VAR_*` environment variables, e.g.:

```bash
export TF_VAR_takealot_api_key="..."
export TF_VAR_postgres_password="..."
```

Values are injected into the n8n containers and read in workflows with `{{ $env.NAME }}`.

## Takealot API notes

The workflows use the Seller API style endpoints (`/v2/offers`, `/v1/sales/orders`, `/v2/sales`, `/v2/offers/batch`) with an `X-API-Key` header. Takealot exposes both a Seller API (`seller-api.takealot.com`) and a newer Marketplace API (`marketplace-api.takealot.com`) with different paths/pagination. If your account uses the other API, change `takealot_api_base_url`/`takealot_api_version` and adjust the URLs in `scripts/generate_workflows.py`, then regenerate.

## Regenerating workflows

```bash
python3 scripts/generate_workflows.py
terraform -chdir=terraform apply
```

The generator contains reusable node builders; edit it rather than the generated JSON files.

## Known limitations

- Offer/sales reads handle the first page (up to 100 offers). Add pagination around the HTTP Request nodes for larger catalogues.
- Price decisions are simple undercut + floor rules; extend `Build Price Decisions` for complex repricing strategies.
- Xero AccountCode and warehouse ID are placeholders; align them with your chart of accounts and warehouse setup.
- Email/Slack/WhatsApp nodes fail silently in the UI if their credentials/webhooks are left blank — configure them or remove those nodes.
