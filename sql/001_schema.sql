CREATE TABLE IF NOT EXISTS offers (
  offer_id        BIGINT PRIMARY KEY,
  sku             TEXT UNIQUE NOT NULL,
  product_title   TEXT,
  selling_price   NUMERIC(12, 2),
  rrp             NUMERIC(12, 2),
  cost_price      NUMERIC(12, 2) DEFAULT 0,
  seller_stock    INTEGER DEFAULT 0,
  stock_total     INTEGER DEFAULT 0,
  warehouse_id    INTEGER,
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS price_history (
  id                BIGSERIAL PRIMARY KEY,
  sku               TEXT NOT NULL,
  offer_id          BIGINT,
  selling_price     NUMERIC(12, 2),
  competitor_price  NUMERIC(12, 2),
  recommended_price NUMERIC(12, 2),
  action            TEXT,
  recorded_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_history_sku_time
  ON price_history (sku, recorded_at DESC);

CREATE TABLE IF NOT EXISTS orders (
  order_id       BIGINT NOT NULL,
  order_item_id  BIGINT NOT NULL,
  sku            TEXT,
  product_title  TEXT,
  quantity       INTEGER DEFAULT 0,
  item_price     NUMERIC(12, 2),
  status         TEXT,
  created_at     TIMESTAMPTZ,
  raw            JSONB,
  imported_at    TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (order_id, order_item_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at DESC);

CREATE TABLE IF NOT EXISTS sales (
  sale_id     BIGINT PRIMARY KEY,
  sku         TEXT,
  offer_id    BIGINT,
  quantity    INTEGER DEFAULT 0,
  revenue     NUMERIC(14, 2) DEFAULT 0,
  fees        NUMERIC(14, 2) DEFAULT 0,
  sale_date   DATE,
  raw         JSONB,
  imported_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sales_date ON sales (sale_date DESC);

CREATE TABLE IF NOT EXISTS inventory (
  sku             TEXT PRIMARY KEY,
  supplier_stock  INTEGER DEFAULT 0,
  takealot_stock  INTEGER DEFAULT 0,
  reserved_stock  INTEGER DEFAULT 0,
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profit_daily (
  report_date DATE PRIMARY KEY,
  revenue     NUMERIC(14, 2) DEFAULT 0,
  fees        NUMERIC(14, 2) DEFAULT 0,
  cogs        NUMERIC(14, 2) DEFAULT 0,
  profit      NUMERIC(14, 2) DEFAULT 0,
  updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS listing_queue (
  id            BIGSERIAL PRIMARY KEY,
  sku           TEXT NOT NULL,
  barcode       TEXT,
  selling_price NUMERIC(12, 2),
  rrp           NUMERIC(12, 2),
  quantity      INTEGER,
  warehouse_id  INTEGER,
  status        TEXT DEFAULT 'pending',
  batch_id      TEXT,
  error         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS automation_log (
  id           BIGSERIAL PRIMARY KEY,
  workflow     TEXT NOT NULL,
  level        TEXT NOT NULL DEFAULT 'info',
  message      TEXT,
  details      JSONB,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_automation_log_created
  ON automation_log (created_at DESC);
