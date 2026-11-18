#!/usr/bin/env python3
"""Generate n8n workflow JSON files from reusable node builders."""

import hashlib
import json
import os

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workflows"))


def uid(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


def uuid_id(*parts):
    h = hashlib.md5("|".join(parts).encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])


class Builder:
    def __init__(self, name):
        self.name = name
        self.nodes = []
        self.edges = []

    def node(self, name, node_type, params, pos, type_version=1, credentials=None):
        item = {
            "parameters": params,
            "id": uid(self.name, name),
            "name": name,
            "type": node_type,
            "typeVersion": type_version,
            "position": list(pos),
        }
        if credentials:
            item["credentials"] = credentials
        self.nodes.append(item)
        return name

    def connect(self, source, target, source_index=0, target_index=0):
        self.edges.append((source, target, source_index, target_index))

    def build(self, slug):
        connections = {}
        for source, target, si, ti in self.edges:
            main = connections.setdefault(source, {}).setdefault("main", [])
            while len(main) <= si:
                main.append([])
            main[si].append({"node": target, "type": "main", "index": ti})
        return {
            "name": self.name,
            "nodes": self.nodes,
            "connections": connections,
            "active": False,
            "settings": {"executionOrder": "v1"},
            "versionId": uuid_id("version", slug),
            "meta": {},
            "id": uid("workflow", slug),
            "tags": [],
            "pinData": {},
        }


def schedule(b, name, cron, pos):
    return b.node(
        name,
        "n8n-nodes-base.scheduleTrigger",
        {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}},
        pos,
        1.2,
    )


def manual(b, name, pos):
    return b.node(name, "n8n-nodes-base.manualTrigger", {}, pos, 1)


def code(b, name, js, pos, mode="runOnceForAllItems"):
    return b.node(
        name,
        "n8n-nodes-base.code",
        {"jsCode": js.strip(), "mode": mode},
        pos,
        2,
    )


def http(
    b,
    name,
    method,
    url,
    pos,
    query=None,
    headers=None,
    json_body=None,
    options=None,
    authentication=None,
):
    params = {"method": method, "url": url, "options": options or {}}
    if headers:
        params["sendHeaders"] = True
        params["headerParameters"] = {
            "parameters": [{"name": k, "value": v} for k, v in headers.items()]
        }
    if query:
        params["sendQueryParameters"] = True
        params["queryParameters"] = {
            "parameters": [{"name": k, "value": v} for k, v in query.items()]
        }
    if json_body is not None:
        params["sendBody"] = True
        params["contentType"] = "json"
        params["jsonBody"] = json_body
    if authentication:
        params["authentication"] = authentication
    return b.node(name, "n8n-nodes-base.httpRequest", params, pos, 4.2)


def takealot_headers():
    return {"X-API-Key": "={{ $env.TAKEALOT_API_KEY }}"}


def pg(b, name, query, pos):
    return b.node(
        name,
        "n8n-nodes-base.postgres",
        {"operation": "executeQuery", "query": query.strip(), "options": {}},
        pos,
        2.5,
    )


def gs(b, name, operation, doc_env, sheet, pos):
    params = {
        "operation": operation,
        "documentId": {
            "__rl": True,
            "value": "={{ $env.%s }}" % doc_env,
            "mode": "id",
        },
        "sheetName": {"__rl": True, "value": sheet, "mode": "name"},
        "options": {},
    }
    if operation == "read":
        params["dataLocationOnSheet"] = {"rangeDefinition": "detectAutomatically"}
    if operation == "append":
        params["columns"] = {"mappingMode": "autoMapInputData", "value": {}}
    return b.node(name, "n8n-nodes-base.googleSheets", params, pos, 4.5)


def if_node(b, name, left, operator, right, pos, value_type="string"):
    conditions = {
        "options": {
            "caseSensitive": True,
            "leftValue": "",
            "typeValidation": "strict",
            "version": 2,
        },
        "conditions": [
            {
                "id": "rule-1",
                "leftValue": left,
                "rightValue": right,
                "operator": {
                    "type": value_type,
                    "operation": operator,
                    "singleValue": True,
                },
            }
        ],
        "combinator": "and",
    }
    return b.node(name, "n8n-nodes-base.if", {"conditions": conditions, "options": {}}, pos, 2.2)


def slack(b, name, text_expr, pos):
    return http(
        b,
        name,
        "POST",
        "={{ $env.SLACK_WEBHOOK_URL }}",
        pos,
        json_body="={{ JSON.stringify({ text: %s }) }}" % text_expr,
    )


def email(b, name, subject, html, pos):
    return b.node(
        name,
        "n8n-nodes-base.emailSend",
        {
            "fromEmail": "={{ $env.SMTP_FROM_EMAIL }}",
            "toEmail": "={{ $env.ALERT_EMAIL }}",
            "subject": subject,
            "emailFormat": "html",
            "html": html,
            "options": {},
        },
        pos,
        2.1,
    )


def wait(b, name, seconds, pos):
    return b.node(
        name,
        "n8n-nodes-base.wait",
        {"amount": seconds, "unit": "seconds"},
        pos,
        1.1,
    )


def noop(b, name, pos):
    return b.node(name, "n8n-nodes-base.noOp", {}, pos, 1)


def write(b, slug):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, slug + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(b.build(slug), fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote", os.path.relpath(path, os.path.dirname(OUT_DIR)))


API = "={{ $env.TAKEALOT_API_BASE_URL }}/{{ $env.TAKEALOT_API_VERSION }}"


# ---------------------------------------------------------------------------
# 00 - API health check
# ---------------------------------------------------------------------------
def health_check():
    b = Builder("00 - Takealot API Health Check")
    manual(b, "Run Health Check", (0, 0))
    http(
        b,
        "Check Offers Count",
        "GET",
        API + "/offers/count",
        (220, 0),
        headers=takealot_headers(),
    )
    code(
        b,
        "Summarise Result",
        """
        const body = $input.first().json;
        return [{ json: {
          ok: true,
          offer_count: body.count ?? body.total ?? 0,
          raw: JSON.stringify(body).slice(0, 500)
        }}];
        """,
        (440, 0),
    )
    slack(
        b,
        "Notify Health Check",
        "'Takealot API health check OK. Offers: ' + $json.offer_count",
        (660, 0),
    )
    b.connect("Run Health Check", "Check Offers Count")
    b.connect("Check Offers Count", "Summarise Result")
    b.connect("Summarise Result", "Notify Health Check")
    write(b, "00-api-health-check")


# ---------------------------------------------------------------------------
# 01 - Price and competitor monitoring
# ---------------------------------------------------------------------------
def price_monitoring():
    b = Builder("01 - Price & Competitor Monitoring")
    schedule(b, "Daily 06:00", "0 6 * * *", (0, 0))
    http(
        b,
        "Fetch My Offers",
        "GET",
        API + "/offers",
        (220, 0),
        query={"page_number": "1", "page_size": "100"},
        headers=takealot_headers(),
    )
    code(
        b,
        "Normalize Offers",
        """
        const body = $input.first().json;
        const offers = body.offers || body.data?.offers || body.results || [];
        return offers.map(o => ({ json: {
          offer_id: Number(o.offer_id || o.id || 0),
          sku: String(o.sku || o.merchant_sku || '').trim(),
          product_title: String(o.title || o.product_title || ''),
          selling_price: Number(o.selling_price || 0),
          rrp: Number(o.rrp || 0),
          cost_price: Number(o.cost_price || 0),
          stock_total: Number(o.stock_total ?? o.seller_stock ?? 0)
        }}));
        """,
        (440, 0),
    )
    pg(
        b,
        "Upsert Offers",
        """
        INSERT INTO offers (offer_id, sku, product_title, selling_price, rrp, stock_total, updated_at)
        VALUES (
          {{ $json.offer_id }},
          '{{ $json.sku }}',
          '{{ $json.product_title.replace(/'/g, "''") }}',
          {{ $json.selling_price }},
          {{ $json.rrp }},
          {{ $json.stock_total }},
          now()
        )
        ON CONFLICT (sku) DO UPDATE SET
          offer_id = EXCLUDED.offer_id,
          product_title = EXCLUDED.product_title,
          selling_price = EXCLUDED.selling_price,
          rrp = EXCLUDED.rrp,
          stock_total = EXCLUDED.stock_total,
          updated_at = now()
        """,
        (660, 0),
    )
    gs(b, "Competitor Prices", "read", "GOOGLE_SHEETS_COMPETITORS_ID", "CompetitorPrices", (880, 0))
    code(
        b,
        "Build Price Decisions",
        """
        const offers = $('Normalize Offers').all().map(i => i.json);
        const comps = $input.all().map(i => i.json);
        const bySku = {};
        for (const c of comps) {
          const sku = String(c.sku || '').trim();
          if (sku) bySku[sku] = Number(c.competitor_price || c.price || 0);
        }
        const undercut = Number($env.PRICE_UNDERCUT_CENTS || 100) / 100;
        const margin = Number($env.PRICE_MIN_MARGIN_PERCENT || 15) / 100;
        const round2 = n => Math.round(n * 100) / 100;
        const out = [];
        for (const o of offers) {
          const cp = bySku[o.sku];
          if (!cp) continue;
          const target = round2(Math.max(1, cp - undercut));
          const floor = round2(o.cost_price * (1 + margin));
          const recommended = Math.max(target, floor);
          const action = recommended < o.selling_price ? 'lower'
            : recommended > o.selling_price ? 'raise' : 'hold';
          out.push({ json: {
            offer_id: o.offer_id,
            sku: o.sku,
            current_price: o.selling_price,
            competitor_price: cp,
            cost_price: o.cost_price,
            recommended_price: recommended,
            action
          }});
        }
        return out;
        """,
        (1100, 0),
    )
    if_node(b, "Needs Reprice?", '={{ $json.action }}', "notEquals", "hold", (1320, 0))
    http(
        b,
        "Patch Offer Price",
        "PATCH",
        API + "/offers/SKU{{ $json.sku }}",
        (1540, -120),
        headers=takealot_headers(),
        json_body="={{ JSON.stringify({ offer: { selling_price: $json.recommended_price } }) }}",
    )
    pg(
        b,
        "Log Price History",
        """
        INSERT INTO price_history (sku, offer_id, selling_price, competitor_price, recommended_price, action)
        VALUES ('{{ $json.sku }}', {{ $json.offer_id }}, {{ $json.current_price }},
                {{ $json.competitor_price }}, {{ $json.recommended_price }}, '{{ $json.action }}')
        """,
        (1760, -120),
    )
    slack(
        b,
        "Alert Reprices",
        "'Repriced ' + $json.sku + ': R' + $json.current_price + ' -> R' + $json.recommended_price + ' (' + $json.action + ')",
        (1980, -120),
    )
    noop(b, "No Reprice Needed", (1540, 180))
    b.connect("Daily 06:00", "Fetch My Offers")
    b.connect("Fetch My Offers", "Normalize Offers")
    b.connect("Normalize Offers", "Upsert Offers")
    b.connect("Upsert Offers", "Competitor Prices")
    b.connect("Competitor Prices", "Build Price Decisions")
    b.connect("Build Price Decisions", "Needs Reprice?")
    b.connect("Needs Reprice?", "Patch Offer Price", 0)
    b.connect("Needs Reprice?", "No Reprice Needed", 1)
    b.connect("Patch Offer Price", "Log Price History")
    b.connect("Log Price History", "Alert Reprices")
    write(b, "01-price-monitoring")


# ---------------------------------------------------------------------------
# 02 - Order processing
# ---------------------------------------------------------------------------
def order_processing():
    b = Builder("02 - Order Processing")
    schedule(b, "Every 15 Minutes", "*/15 * * * *", (0, 0))
    code(
        b,
        "Date Window",
        """
        const now = new Date();
        const since = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
        return [{ json: {
          start_date: since.toISOString().slice(0, 10),
          end_date: now.toISOString().slice(0, 10),
          report_date: now.toISOString().slice(0, 10)
        }}];
        """,
        (220, 0),
    )
    http(
        b,
        "Fetch Sales Orders",
        "GET",
        "={{ $env.TAKEALOT_API_BASE_URL }}/v1/sales/orders",
        (440, 0),
        query={"start_date": "={{ $json.start_date }}", "end_date": "={{ $json.end_date }}"},
        headers=takealot_headers(),
    )
    code(
        b,
        "Normalize Orders",
        """
        const body = $input.first().json;
        const orders = body.orders || body.data?.orders || body.sales_orders || [];
        const rows = [];
        for (const o of orders) {
          const items = o.order_items || o.items || o.line_items || [o];
          for (const it of items) {
            rows.push({ json: {
              order_id: Number(o.order_id || o.id || 0),
              order_item_id: Number(it.order_item_id || it.id || 0),
              sku: String(it.sku || it.merchant_sku || ''),
              product_title: String(it.product_title || it.title || o.product_title || ''),
              quantity: Number(it.quantity || 1),
              item_price: Number(it.item_price || it.price || 0),
              status: String(o.order_status || o.status || ''),
              created_at: o.created_at || o.order_date || new Date().toISOString(),
              raw: JSON.stringify(o).slice(0, 8000).replace(/'/g, "''")
            }});
          }
        }
        return rows;
        """,
        (660, 0),
    )
    pg(
        b,
        "Upsert Orders",
        """
        INSERT INTO orders (order_id, order_item_id, sku, product_title, quantity, item_price, status, created_at, raw)
        VALUES ({{ $json.order_id }}, {{ $json.order_item_id }}, '{{ $json.sku }}',
                '{{ $json.product_title.replace(/'/g, "''") }}', {{ $json.quantity }},
                {{ $json.item_price }}, '{{ $json.status }}', '{{ $json.created_at }}',
                '{{ $json.raw }}'::jsonb)
        ON CONFLICT (order_id, order_item_id) DO UPDATE SET
          quantity = EXCLUDED.quantity,
          item_price = EXCLUDED.item_price,
          status = EXCLUDED.status,
          raw = EXCLUDED.raw,
          imported_at = now()
        """,
        (880, 0),
    )
    code(
        b,
        "Order Summary",
        """
        const rows = $('Normalize Orders').all().map(i => i.json);
        const revenue = rows.reduce((s, r) => s + r.item_price * r.quantity, 0);
        return [{ json: {
          count: rows.length,
          revenue: Math.round(revenue * 100) / 100,
          rows: rows.slice(0, 25),
          date: new Date().toISOString().slice(0, 10)
        }}];
        """,
        (1100, 0),
    )
    if_node(b, "Any New Orders?", '={{ $json.count }}', "gt", 0, (1320, 0), "number")
    slack(
        b,
        "Notify New Orders",
        "'New Takealot orders: ' + $json.count + ' | Revenue: R' + $json.revenue",
        (1540, -120),
    )
    email(
        b,
        "Email Order Digest",
        "={{ 'Takealot order digest - ' + $json.date }}",
        "={{ '<h2>' + $json.count + ' new orders</h2><table border=1 cellpadding=4><tr><th>Order</th><th>SKU</th><th>Qty</th><th>Price</th></tr>' + $json.rows.map(r => '<tr><td>' + r.order_id + '</td><td>' + r.sku + '</td><td>' + r.quantity + '</td><td>R' + r.item_price + '</td></tr>').join('') + '</table>' }}",
        (1760, -120),
    )
    http(
        b,
        "Xero Create Invoice",
        "POST",
        "https://api.xero.com/api.xro/2.0/Invoices",
        (1980, -120),
        headers={
            "Xero-tenant-id": "={{ $env.XERO_TENANT_ID }}",
            "Content-Type": "application/json",
        },
        json_body="""
        ={{ JSON.stringify({
          Type: 'ACCREC',
          Contact: { Name: 'Takealot Marketplace' },
          Date: $json.date,
          DueDate: $json.date,
          Reference: 'TAKEALOT-' + $json.date,
          LineItems: $json.rows.map(r => ({
            Description: (r.sku || '') + ' - ' + (r.product_title || ''),
            Quantity: r.quantity,
            UnitAmount: r.item_price,
            AccountCode: '400'
          }))
        }) }}
        """.strip(),
        authentication="oAuth2",
    )
    noop(b, "No New Orders", (1540, 180))
    b.connect("Every 15 Minutes", "Date Window")
    b.connect("Date Window", "Fetch Sales Orders")
    b.connect("Fetch Sales Orders", "Normalize Orders")
    b.connect("Normalize Orders", "Upsert Orders")
    b.connect("Upsert Orders", "Order Summary")
    b.connect("Order Summary", "Any New Orders?")
    b.connect("Any New Orders?", "Notify New Orders", 0)
    b.connect("Any New Orders?", "No New Orders", 1)
    b.connect("Notify New Orders", "Email Order Digest")
    b.connect("Email Order Digest", "Xero Create Invoice")
    write(b, "02-order-processing")


# ---------------------------------------------------------------------------
# 03 - Inventory sync
# ---------------------------------------------------------------------------
def inventory_sync():
    b = Builder("03 - Inventory Sync")
    schedule(b, "Hourly", "0 * * * *", (0, 0))
    pg(
        b,
        "Read Stock Table",
        "SELECT sku, supplier_stock, takealot_stock, reserved_stock FROM inventory",
        (220, 0),
    )
    http(
        b,
        "Fetch Takealot Offers",
        "GET",
        API + "/offers",
        (440, 0),
        query={"page_number": "1", "page_size": "100"},
        headers=takealot_headers(),
    )
    code(
        b,
        "Reconcile Stock",
        """
        const local = $('Read Stock Table').all().map(i => i.json);
        const body = $input.first().json;
        const offers = body.offers || body.data?.offers || [];
        const remote = {};
        for (const o of offers) {
          const sku = String(o.sku || o.merchant_sku || '').trim();
          if (sku) remote[sku] = o;
        }
        const out = [];
        for (const l of local) {
          const o = remote[l.sku];
          if (!o) continue;
          const available = Math.max(0, Number(l.supplier_stock || 0) - Number(l.reserved_stock || 0));
          const current = Number(o.seller_stock ?? o.stock_total ?? 0);
          if (available !== current) {
            out.push({ json: {
              sku: l.sku,
              offer_id: Number(o.offer_id || o.id || 0),
              quantity: available,
              remote_stock: current
            }});
          }
        }
        return out;
        """,
        (660, 0),
    )
    code(
        b,
        "Count Updates",
        """
        const updates = $input.all().map(i => i.json);
        return [{ json: { count: updates.length, updates } }];
        """,
        (880, 0),
    )
    if_node(b, "Stock Differences?", '={{ $json.count }}', "gt", 0, (1100, 0), "number")
    http(
        b,
        "Batch Update Stock",
        "POST",
        API + "/offers/batch",
        (1320, -120),
        headers=takealot_headers(),
        json_body="""
        ={{ JSON.stringify({ offers: $('Count Updates').first().json.updates.map(u => ({
          sku: u.sku,
          leadtime_stock: [{
            merchant_warehouse_id: Number($env.TAKEALOT_WAREHOUSE_ID || 1),
            quantity: u.quantity
          }]
        })) }) }}
        """.strip(),
    )
    code(
        b,
        "Flatten Updates",
        "return $('Count Updates').first().json.updates;",
        (1540, -120),
    )
    pg(
        b,
        "Save Local Stock",
        """
        UPDATE inventory
        SET takealot_stock = {{ $json.quantity }}, updated_at = now()
        WHERE sku = '{{ $json.sku }}'
        """,
        (1760, -120),
    )
    pg(
        b,
        "Log Sync",
        """
        INSERT INTO automation_log (workflow, level, message, details)
        VALUES ('inventory-sync', 'info', 'Stock sync completed',
                '{{ JSON.stringify($(\"Count Updates\").first().json.updates).replace(/'/g, "''") }}'::jsonb)
        """,
        (1980, -120),
    )
    slack(
        b,
        "Notify Stock Sync",
        "'Stock sync: ' + $('Count Updates').first().json.count + ' offers updated'",
        (2200, -120),
    )
    noop(b, "Stock In Sync", (1320, 180))
    b.connect("Hourly", "Read Stock Table")
    b.connect("Read Stock Table", "Fetch Takealot Offers")
    b.connect("Fetch Takealot Offers", "Reconcile Stock")
    b.connect("Reconcile Stock", "Count Updates")
    b.connect("Count Updates", "Stock Differences?")
    b.connect("Stock Differences?", "Batch Update Stock", 0)
    b.connect("Stock Differences?", "Stock In Sync", 1)
    b.connect("Batch Update Stock", "Flatten Updates")
    b.connect("Flatten Updates", "Save Local Stock")
    b.connect("Save Local Stock", "Log Sync")
    b.connect("Log Sync", "Notify Stock Sync")
    write(b, "03-inventory-sync")


# ---------------------------------------------------------------------------
# 04 - Stock depletion alerts
# ---------------------------------------------------------------------------
def stock_alerts():
    b = Builder("04 - Stock Depletion Alerts")
    schedule(b, "Every 2 Hours", "0 */2 * * *", (0, 0))
    pg(
        b,
        "Low Stock Query",
        """
        SELECT sku, product_title, stock_total, selling_price, cost_price
        FROM offers
        WHERE stock_total <= {{ $env.LOW_STOCK_THRESHOLD }}
        ORDER BY stock_total ASC
        LIMIT 100
        """,
        (220, 0),
    )
    code(
        b,
        "Format Low Stock",
        """
        const rows = $input.all().map(i => i.json);
        const lines = rows.map(r => '• ' + r.sku + ' - ' + (r.product_title || '') + ': ' + r.stock_total + ' left');
        return [{ json: {
          count: rows.length,
          rows,
          text: 'Takealot low stock alert\\n' + lines.join('\\n'),
          html: '<h2>Low stock (' + rows.length + ')</h2><ul>' + lines.map(l => '<li>' + l + '</li>').join('') + '</ul>'
        }}];
        """,
        (440, 0),
    )
    if_node(b, "Any Low Stock?", '={{ $json.count }}', "gt", 0, (660, 0), "number")
    slack(b, "Slack Low Stock", "$json.text", (880, -120))
    email(
        b,
        "Email Low Stock",
        "={{ 'Low stock alert - ' + $json.count + ' offers' }}",
        "={{ $json.html }}",
        (1100, -120),
    )
    if_node(
        b,
        "WhatsApp Configured?",
        "={{ $env.WHATSAPP_TOKEN }}",
        "notEmpty",
        "",
        (1320, -120),
    )
    http(
        b,
        "WhatsApp Low Stock",
        "POST",
        "=https://graph.facebook.com/v19.0/{{ $env.WHATSAPP_PHONE_NUMBER_ID }}/messages",
        (1540, -240),
        headers={
            "Authorization": "=Bearer {{ $env.WHATSAPP_TOKEN }}",
            "Content-Type": "application/json",
        },
        json_body="={{ JSON.stringify({ messaging_product: 'whatsapp', to: $env.WHATSAPP_RECIPIENT, type: 'text', text: { body: $('Format Low Stock').first().json.text.slice(0, 4000) } }) }}",
    )
    noop(b, "WhatsApp Skipped", (1540, 0))
    noop(b, "Stock Levels Healthy", (880, 240))
    b.connect("Every 2 Hours", "Low Stock Query")
    b.connect("Low Stock Query", "Format Low Stock")
    b.connect("Format Low Stock", "Any Low Stock?")
    b.connect("Any Low Stock?", "Slack Low Stock", 0)
    b.connect("Any Low Stock?", "Stock Levels Healthy", 1)
    b.connect("Slack Low Stock", "Email Low Stock")
    b.connect("Email Low Stock", "WhatsApp Configured?")
    b.connect("WhatsApp Configured?", "WhatsApp Low Stock", 0)
    b.connect("WhatsApp Configured?", "WhatsApp Skipped", 1)
    write(b, "04-stock-depletion-alerts")


# ---------------------------------------------------------------------------
# 05 - Sales and profit reporting
# ---------------------------------------------------------------------------
def profit_reporting():
    b = Builder("05 - Sales & Profit Reporting")
    schedule(b, "Daily 07:00", "0 7 * * *", (0, 0))
    code(
        b,
        "Yesterday Range",
        """
        const now = new Date();
        const y = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        return [{ json: {
          start_date: y.toISOString().slice(0, 10),
          end_date: y.toISOString().slice(0, 10),
          report_date: y.toISOString().slice(0, 10)
        }}];
        """,
        (220, 0),
    )
    http(
        b,
        "Fetch Sales",
        "GET",
        API + "/sales",
        (440, 0),
        query={"start_date": "={{ $json.start_date }}", "end_date": "={{ $json.end_date }}"},
        headers=takealot_headers(),
    )
    code(
        b,
        "Normalize Sales",
        """
        const body = $input.first().json;
        const sales = body.sales || body.data?.sales || body.results || [];
        return sales.map(s => ({ json: {
          sale_id: Number(s.sale_id || s.id || 0),
          sku: String(s.sku || s.merchant_sku || ''),
          offer_id: Number(s.offer_id || 0),
          quantity: Number(s.quantity || s.units || 0),
          revenue: Number(s.revenue || s.total || s.item_price || 0),
          fees: Number(s.fees || s.commission || 0),
          sale_date: String(s.sale_date || s.date || $('Yesterday Range').first().json.report_date).slice(0, 10),
          raw: JSON.stringify(s).slice(0, 8000).replace(/'/g, "''")
        }}));
        """,
        (660, 0),
    )
    pg(
        b,
        "Upsert Sales",
        """
        INSERT INTO sales (sale_id, sku, offer_id, quantity, revenue, fees, sale_date, raw)
        VALUES ({{ $json.sale_id }}, '{{ $json.sku }}', {{ $json.offer_id }}, {{ $json.quantity }},
                {{ $json.revenue }}, {{ $json.fees }}, '{{ $json.sale_date }}', '{{ $json.raw }}'::jsonb)
        ON CONFLICT (sale_id) DO UPDATE SET
          revenue = EXCLUDED.revenue,
          fees = EXCLUDED.fees,
          quantity = EXCLUDED.quantity,
          raw = EXCLUDED.raw,
          imported_at = now()
        """,
        (880, 0),
    )
    gs(b, "Cost Prices", "read", "GOOGLE_SHEETS_CATALOGUE_ID", "Catalogue", (1100, 0))
    code(
        b,
        "Compute Daily Profit",
        """
        const sales = $('Normalize Sales').all().map(i => i.json);
        const costs = {};
        for (const c of $input.all().map(i => i.json)) {
          const sku = String(c.sku || '').trim();
          if (sku) costs[sku] = Number(c.cost_price || c.cost || 0);
        }
        let revenue = 0, fees = 0, cogs = 0;
        for (const s of sales) {
          revenue += Number(s.revenue || 0);
          fees += Number(s.fees || 0);
          cogs += (costs[s.sku] || 0) * Number(s.quantity || 0);
        }
        const r2 = n => Math.round(n * 100) / 100;
        return [{ json: {
          report_date: sales[0]?.sale_date || $('Yesterday Range').first().json.report_date,
          revenue: r2(revenue),
          fees: r2(fees),
          cogs: r2(cogs),
          profit: r2(revenue - fees - cogs),
          orders: sales.length
        }}];
        """,
        (1320, 0),
    )
    pg(
        b,
        "Save Daily Profit",
        """
        INSERT INTO profit_daily (report_date, revenue, fees, cogs, profit, updated_at)
        VALUES ('{{ $json.report_date }}', {{ $json.revenue }}, {{ $json.fees }},
                {{ $json.cogs }}, {{ $json.profit }}, now())
        ON CONFLICT (report_date) DO UPDATE SET
          revenue = EXCLUDED.revenue,
          fees = EXCLUDED.fees,
          cogs = EXCLUDED.cogs,
          profit = EXCLUDED.profit,
          updated_at = now()
        """,
        (1540, 0),
    )
    gs(b, "Append Report Row", "append", "GOOGLE_SHEETS_REPORT_ID", "DailyReport", (1760, 0))
    slack(
        b,
        "Notify Report",
        "'Daily report ' + $json.report_date + ': revenue R' + $json.revenue + ', fees R' + $json.fees + ', COGS R' + $json.cogs + ', profit R' + $json.profit",
        (1980, 0),
    )
    email(
        b,
        "Email Report",
        "={{ 'Takealot profit report - ' + $json.report_date }}",
        "={{ '<h2>' + $json.report_date + '</h2><p>Revenue: R' + $json.revenue + '<br>Fees: R' + $json.fees + '<br>COGS: R' + $json.cogs + '<br><b>Profit: R' + $json.profit + '</b></p>' }}",
        (2200, 0),
    )
    b.connect("Daily 07:00", "Yesterday Range")
    b.connect("Yesterday Range", "Fetch Sales")
    b.connect("Fetch Sales", "Normalize Sales")
    b.connect("Normalize Sales", "Upsert Sales")
    b.connect("Upsert Sales", "Cost Prices")
    b.connect("Cost Prices", "Compute Daily Profit")
    b.connect("Compute Daily Profit", "Save Daily Profit")
    b.connect("Save Daily Profit", "Append Report Row")
    b.connect("Append Report Row", "Notify Report")
    b.connect("Notify Report", "Email Report")
    write(b, "05-sales-profit-reporting")


# ---------------------------------------------------------------------------
# 06 - Product listing automation
# ---------------------------------------------------------------------------
def listing_automation():
    b = Builder("06 - Product Listing Automation")
    manual(b, "Run Listing Batch", (0, 0))
    gs(b, "Read Listing Queue", "read", "GOOGLE_SHEETS_CATALOGUE_ID", "Listings", (220, 0))
    code(
        b,
        "Validate Listings",
        """
        const rows = $input.all().map(i => i.json);
        const warehouse = Number($env.TAKEALOT_WAREHOUSE_ID || 1);
        const out = [];
        for (const r of rows) {
          const sku = String(r.sku || '').trim();
          const price = Number(r.selling_price || 0);
          const qty = Number(r.quantity || 0);
          if (!sku || price <= 0 || qty <= 0) continue;
          out.push({ json: {
            sku,
            selling_price: price,
            rrp: Number(r.rrp || price),
            leadtime_days: Number(r.leadtime_days || 0),
            leadtime_stock: [{ merchant_warehouse_id: warehouse, quantity: qty }],
            barcode: String(r.barcode || '')
          }});
        }
        return out;
        """,
        (440, -160),
    )
    code(
        b,
        "Collect Rejections",
        """
        const rows = $('Read Listing Queue').all().map(i => i.json);
        const bad = rows.filter(r => !String(r.sku || '').trim() || Number(r.selling_price || 0) <= 0 || Number(r.quantity || 0) <= 0);
        return bad.map(r => ({ json: {
          sku: String(r.sku || ''),
          error: 'sku, selling_price and quantity must be valid',
          raw: JSON.stringify(r).slice(0, 2000)
        }}));
        """,
        (440, 260),
    )
    pg(
        b,
        "Log Queue Items",
        """
        INSERT INTO listing_queue (sku, barcode, selling_price, rrp, quantity, warehouse_id, status)
        VALUES ('{{ $json.sku }}', '{{ $json.barcode }}', {{ $json.selling_price }}, {{ $json.rrp }},
                {{ $json.leadtime_stock[0].quantity }}, {{ $json.leadtime_stock[0].merchant_warehouse_id }}, 'pending')
        """,
        (660, -160),
    )
    http(
        b,
        "Submit Offer Batch",
        "POST",
        API + "/offers/batch",
        (880, -160),
        headers=takealot_headers(),
        json_body="""
        ={{ JSON.stringify({ offers: $('Validate Listings').all().map(i => i.json).map(o => ({
          sku: o.sku,
          selling_price: o.selling_price,
          rrp: o.rrp,
          leadtime_days: o.leadtime_days,
          leadtime_stock: o.leadtime_stock
        })) }) }}
        """.strip(),
    )
    code(
        b,
        "Extract Batch Id",
        """
        const body = $input.first().json;
        return [{ json: {
          batch_id: String(body.batch_id || body.id || body.batchId || ''),
          submitted_at: new Date().toISOString()
        }}];
        """,
        (1100, -160),
    )
    wait(b, "Wait For Batch", 30, (1320, -160))
    http(
        b,
        "Poll Batch Status",
        "GET",
        API + "/offers/batch/{{ $('Extract Batch Id').first().json.batch_id }}",
        (1540, -160),
        headers=takealot_headers(),
    )
    code(
        b,
        "Batch Result",
        """
        const body = $input.first().json;
        return [{ json: {
          batch_id: $('Extract Batch Id').first().json.batch_id,
          status: String(body.status || body.state || 'unknown'),
          summary: JSON.stringify(body).slice(0, 4000)
        }}];
        """,
        (1760, -160),
    )
    pg(
        b,
        "Update Queue Status",
        """
        UPDATE listing_queue
        SET status = '{{ $json.status }}', batch_id = '{{ $json.batch_id }}'
        WHERE batch_id IS NULL AND status = 'pending'
        """,
        (1980, -160),
    )
    slack(
        b,
        "Notify Listing Result",
        "'Listing batch ' + $json.batch_id + ' status: ' + $json.status",
        (2200, -160),
    )
    code(
        b,
        "Count Rejections",
        "const rows = $input.all().map(i => i.json); return [{ json: { count: rows.length, rows } }];",
        (660, 260),
    )
    if_node(b, "Any Rejections?", '={{ $json.count }}', "gt", 0, (880, 260), "number")
    pg(
        b,
        "Log Rejections",
        """
        INSERT INTO listing_queue (sku, status, error, created_at)
        VALUES ('{{ $json.sku }}', 'rejected', '{{ $json.error }}', now())
        """,
        (1100, 140),
    )
    slack(
        b,
        "Notify Rejections",
        "'Listing rows rejected: ' + $('Count Rejections').first().json.count",
        (1320, 140),
    )
    noop(b, "No Rejections", (1100, 400))
    b.connect("Run Listing Batch", "Read Listing Queue")
    b.connect("Read Listing Queue", "Validate Listings")
    b.connect("Read Listing Queue", "Collect Rejections")
    b.connect("Validate Listings", "Log Queue Items")
    b.connect("Log Queue Items", "Submit Offer Batch")
    b.connect("Submit Offer Batch", "Extract Batch Id")
    b.connect("Extract Batch Id", "Wait For Batch")
    b.connect("Wait For Batch", "Poll Batch Status")
    b.connect("Poll Batch Status", "Batch Result")
    b.connect("Batch Result", "Update Queue Status")
    b.connect("Update Queue Status", "Notify Listing Result")
    b.connect("Collect Rejections", "Count Rejections")
    b.connect("Count Rejections", "Any Rejections?")
    b.connect("Any Rejections?", "Log Rejections", 0)
    b.connect("Any Rejections?", "No Rejections", 1)
    b.connect("Log Rejections", "Notify Rejections")
    write(b, "06-product-listing-automation")


# ---------------------------------------------------------------------------
# 07 - Top selling products (last 30 days by units)
# ---------------------------------------------------------------------------
def top_products_analysis():
    b = Builder("07 - Top Products Analysis")
    schedule(b, "Daily 06:30", "30 6 * * *", (0, 0))
    code(
        b,
        "Thirty Day Window",
        """
        const now = new Date();
        const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        return [{ json: {
          start_date: start.toISOString().slice(0, 10),
          end_date: now.toISOString().slice(0, 10)
        }}];
        """,
        (220, 0),
    )
    http(
        b,
        "Fetch Sales",
        "GET",
        API + "/sales",
        (440, 0),
        query={
            "start_date": "={{ $json.start_date }}",
            "end_date": "={{ $json.end_date }}",
        },
        headers=takealot_headers(),
    )
    code(
        b,
        "Aggregate By Sku",
        """
        const body = $input.first().json;
        const sales = body.sales || body.data?.sales || body.results || [];
        const map = {};
        for (const s of sales) {
          const sku = String(s.sku || s.merchant_sku || '').trim();
          if (!sku) continue;
          const qty = Number(s.quantity || s.units || 0);
          const rev = Number(s.revenue || s.total || s.item_price || 0);
          const row = map[sku] || (map[sku] = {
            sku,
            product_title: String(s.product_title || s.title || ''),
            offer_id: Number(s.offer_id || 0),
            units_sold: 0,
            revenue: 0
          });
          row.units_sold += qty;
          row.revenue += rev;
        }
        const rows = Object.values(map).map(r => ({ json: {
          sku: r.sku,
          product_title: r.product_title,
          offer_id: r.offer_id,
          units_sold: r.units_sold,
          revenue: Math.round(r.revenue * 100) / 100,
          avg_selling_price: r.units_sold ? Math.round(r.revenue / r.units_sold * 100) / 100 : 0
        }}));
        rows.sort((a, b) => b.json.units_sold - a.json.units_sold);
        return rows;
        """,
        (660, 0),
    )
    http(
        b,
        "Fetch My Offers",
        "GET",
        API + "/offers",
        (880, 0),
        query={"page_number": "1", "page_size": "100"},
        headers=takealot_headers(),
    )
    code(
        b,
        "Normalize Current Prices",
        """
        const body = $input.first().json;
        const offers = body.offers || body.data?.offers || [];
        return offers.map(o => ({ json: {
          sku: String(o.sku || o.merchant_sku || '').trim(),
          offer_id: Number(o.offer_id || o.id || 0),
          product_title: String(o.title || o.product_title || ''),
          takealot_price: Number(o.selling_price || 0)
        }}));
        """,
        (1100, 0),
    )
    code(
        b,
        "Join And Rank",
        """
        const agg = $('Aggregate By Sku').all().map(i => i.json);
        const prices = {};
        for (const p of $input.all().map(i => i.json)) {
          if (p.sku) prices[p.sku] = p;
        }
        const limit = Number($env.TOP_PRODUCTS_LIMIT || 25);
        const window = $('Thirty Day Window').first().json;
        const rows = agg.map(a => {
          const p = prices[a.sku] || {};
          return { json: {
            sku: a.sku,
            product_title: p.product_title || a.product_title,
            offer_id: p.offer_id || a.offer_id,
            units_sold: a.units_sold,
            revenue: a.revenue,
            avg_selling_price: a.avg_selling_price,
            takealot_price: p.takealot_price || a.avg_selling_price,
            window_start: window.start_date,
            window_end: window.end_date
          }};
        });
        rows.sort((a, b) => b.json.units_sold - a.json.units_sold);
        return rows.slice(0, limit).map((r, i) => ({ json: { ...r.json, rank: i + 1 } }));
        """,
        (1320, 0),
    )
    pg(
        b,
        "Upsert Top Products",
        """
        INSERT INTO top_products (sku, product_title, offer_id, units_sold, revenue,
                                  avg_selling_price, takealot_price, window_start, window_end, rank, updated_at)
        VALUES ('{{ $json.sku }}', '{{ $json.product_title.replace(/'/g, "''") }}', {{ $json.offer_id }},
                {{ $json.units_sold }}, {{ $json.revenue }}, {{ $json.avg_selling_price }},
                {{ $json.takealot_price }}, '{{ $json.window_start }}', '{{ $json.window_end }}',
                {{ $json.rank }}, now())
        ON CONFLICT (sku) DO UPDATE SET
          product_title = EXCLUDED.product_title,
          offer_id = EXCLUDED.offer_id,
          units_sold = EXCLUDED.units_sold,
          revenue = EXCLUDED.revenue,
          avg_selling_price = EXCLUDED.avg_selling_price,
          takealot_price = EXCLUDED.takealot_price,
          window_start = EXCLUDED.window_start,
          window_end = EXCLUDED.window_end,
          rank = EXCLUDED.rank,
          updated_at = now()
        """,
        (1540, 0),
    )
    code(
        b,
        "Build Top Products Digest",
        """
        const rows = $('Join And Rank').all().map(i => i.json).slice(0, 10);
        const lines = rows.map(r => r.rank + '. ' + r.sku + ' - ' + r.product_title +
          ': ' + r.units_sold + ' units, R' + r.revenue);
        return [{ json: {
          count: rows.length,
          text: 'Top Takealot sellers (last 30 days)\\n' + lines.join('\\n'),
          html: '<h2>Top sellers - last 30 days</h2><ol>' +
            lines.map(l => '<li>' + l + '</li>').join('') + '</ol>'
        }}];
        """,
        (1760, 0),
    )
    slack(b, "Notify Top Products", "$json.text", (1980, 0))
    email(
        b,
        "Email Top Products",
        "={{ 'Top Takealot sellers - ' + $json.count + ' products' }}",
        "={{ $json.html }}",
        (2200, 0),
    )
    b.connect("Daily 06:30", "Thirty Day Window")
    b.connect("Thirty Day Window", "Fetch Sales")
    b.connect("Fetch Sales", "Aggregate By Sku")
    b.connect("Aggregate By Sku", "Fetch My Offers")
    b.connect("Fetch My Offers", "Normalize Current Prices")
    b.connect("Normalize Current Prices", "Join And Rank")
    b.connect("Join And Rank", "Upsert Top Products")
    b.connect("Upsert Top Products", "Build Top Products Digest")
    b.connect("Build Top Products Digest", "Notify Top Products")
    b.connect("Notify Top Products", "Email Top Products")
    write(b, "07-top-products-analysis")


# ---------------------------------------------------------------------------
# 08 - Wholesale deal finder for the top sellers
# ---------------------------------------------------------------------------
def wholesale_deal_finder():
    b = Builder("08 - Wholesale Deal Finder")
    schedule(b, "Daily 08:00", "0 8 * * *", (0, 0))
    pg(
        b,
        "Read Top Products",
        """
        SELECT sku, product_title, rank, units_sold, takealot_price
        FROM top_products
        WHERE rank <= {{ $env.TOP_PRODUCTS_LIMIT }}
        ORDER BY rank
        """,
        (220, 0),
    )
    gs(
        b,
        "Wholesale Prices",
        "read",
        "GOOGLE_SHEETS_WHOLESALE_ID",
        "WholesalePrices",
        (440, 0),
    )
    code(
        b,
        "Rank Deals",
        """
        const products = $('Read Top Products').all().map(i => i.json);
        const offers = $input.all().map(i => i.json);
        const bySku = {};
        for (const o of offers) {
          const sku = String(o.sku || '').trim();
          if (!sku) continue;
          (bySku[sku] || (bySku[sku] = [])).push(o);
        }
        const target = Number($env.TARGET_MARGIN_PERCENT || 25);
        const clamp = n => Math.max(0, Math.min(1, n));
        const out = [];
        for (const p of products) {
          const candidates = bySku[p.sku] || [];
          const sell = Number(p.takealot_price || 0);
          if (!candidates.length || sell <= 0) continue;
          const positive = candidates
            .map(c => Number(c.unit_price || 0))
            .filter(n => n > 0);
          const minPrice = positive.length ? Math.min(...positive) : 0;
          const ranked = candidates.map(c => {
            const unit = Number(c.unit_price || 0);
            const shipping = Number(c.shipping || 0);
            const stock = Number(c.stock || c.available_stock || 0);
            const lead = Number(c.lead_time_days || c.lead_time || 0);
            const landed = unit + shipping;
            const margin = sell - landed;
            const marginPct = (margin / sell) * 100;
            const marginScore = clamp(marginPct / target);
            const priceScore = unit > 0 && minPrice > 0 ? clamp(minPrice / unit) : 0;
            const stockScore = clamp(stock / Math.max(Number(p.units_sold || 0), 1));
            const leadScore = clamp((14 - lead) / 14);
            const score = 0.5 * marginScore + 0.2 * priceScore +
                          0.15 * stockScore + 0.15 * leadScore;
            return {
              sku: p.sku,
              product_title: String(p.product_title || ''),
              product_rank: Number(p.rank || 0),
              units_sold: Number(p.units_sold || 0),
              takealot_price: sell,
              best_wholesaler: String(c.wholesaler || c.supplier || ''),
              unit_price: unit,
              shipping: shipping,
              landed_cost: landed,
              gross_margin: Math.round(margin * 100) / 100,
              margin_pct: Math.round(marginPct * 100) / 100,
              available_stock: stock,
              lead_time_days: lead,
              supplier_url: String(c.url || c.supplier_url || ''),
              score: Math.round(score * 10000) / 10000
            };
          }).sort((a, b) => b.score - a.score);
          const best = ranked[0];
          best.alternatives = ranked.slice(1, 4);
          out.push({ json: best });
        }
        return out;
        """,
        (660, 0),
    )
    pg(
        b,
        "Upsert Sourcing Deals",
        """
        INSERT INTO sourcing_deals (sku, product_title, product_rank, units_sold, takealot_price,
                                    best_wholesaler, unit_price, shipping, landed_cost, gross_margin,
                                    margin_pct, available_stock, lead_time_days, supplier_url, score, computed_at)
        VALUES ('{{ $json.sku }}', '{{ $json.product_title.replace(/'/g, "''") }}', {{ $json.product_rank }},
                {{ $json.units_sold }}, {{ $json.takealot_price }},
                '{{ $json.best_wholesaler.replace(/'/g, "''") }}', {{ $json.unit_price }},
                {{ $json.shipping }}, {{ $json.landed_cost }}, {{ $json.gross_margin }},
                {{ $json.margin_pct }}, {{ $json.available_stock }}, {{ $json.lead_time_days }},
                '{{ $json.supplier_url.replace(/'/g, "''") }}', {{ $json.score }}, now())
        ON CONFLICT (sku) DO UPDATE SET
          product_title = EXCLUDED.product_title,
          product_rank = EXCLUDED.product_rank,
          units_sold = EXCLUDED.units_sold,
          takealot_price = EXCLUDED.takealot_price,
          best_wholesaler = EXCLUDED.best_wholesaler,
          unit_price = EXCLUDED.unit_price,
          shipping = EXCLUDED.shipping,
          landed_cost = EXCLUDED.landed_cost,
          gross_margin = EXCLUDED.gross_margin,
          margin_pct = EXCLUDED.margin_pct,
          available_stock = EXCLUDED.available_stock,
          lead_time_days = EXCLUDED.lead_time_days,
          supplier_url = EXCLUDED.supplier_url,
          score = EXCLUDED.score,
          computed_at = now()
        """,
        (880, 0),
    )
    pg(
        b,
        "Log Deal History",
        """
        INSERT INTO sourcing_deal_history (sku, best_wholesaler, unit_price, landed_cost, margin_pct, score, computed_at)
        VALUES ('{{ $json.sku }}', '{{ $json.best_wholesaler.replace(/'/g, "''") }}', {{ $json.unit_price }},
                {{ $json.landed_cost }}, {{ $json.margin_pct }}, {{ $json.score }}, now())
        """,
        (1100, 0),
    )
    code(
        b,
        "Build Sourcing Digest",
        """
        const rows = $('Rank Deals').all().map(i => i.json).slice(0, 10);
        const lines = rows.map(r => r.product_rank + '. ' + r.sku + ' -> ' + r.best_wholesaler +
          ': cost R' + r.landed_cost + ' vs R' + r.takealot_price +
          ' | margin ' + r.margin_pct + '% | score ' + r.score);
        return [{ json: {
          count: rows.length,
          text: 'Best wholesale deals for top sellers\\n' + lines.join('\\n'),
          html: '<h2>Best wholesale deals</h2><ol>' +
            lines.map(l => '<li>' + l + '</li>').join('') + '</ol>'
        }}];
        """,
        (1320, 0),
    )
    slack(b, "Notify Sourcing Deals", "$json.text", (1540, 0))
    email(
        b,
        "Email Sourcing Deals",
        "={{ 'Wholesale deals for ' + $json.count + ' top products' }}",
        "={{ $json.html }}",
        (1760, 0),
    )
    b.connect("Daily 08:00", "Read Top Products")
    b.connect("Read Top Products", "Wholesale Prices")
    b.connect("Wholesale Prices", "Rank Deals")
    b.connect("Rank Deals", "Upsert Sourcing Deals")
    b.connect("Upsert Sourcing Deals", "Log Deal History")
    b.connect("Log Deal History", "Build Sourcing Digest")
    b.connect("Build Sourcing Digest", "Notify Sourcing Deals")
    b.connect("Notify Sourcing Deals", "Email Sourcing Deals")
    write(b, "08-wholesale-deal-finder")


if __name__ == "__main__":
    health_check()
    price_monitoring()
    order_processing()
    inventory_sync()
    stock_alerts()
    profit_reporting()
    listing_automation()
    top_products_analysis()
    wholesale_deal_finder()
