CREATE TABLE IF NOT EXISTS top_products (
  sku                TEXT PRIMARY KEY,
  product_title      TEXT,
  offer_id           BIGINT,
  units_sold         INTEGER DEFAULT 0,
  revenue            NUMERIC(14, 2) DEFAULT 0,
  avg_selling_price  NUMERIC(12, 2) DEFAULT 0,
  takealot_price     NUMERIC(12, 2) DEFAULT 0,
  window_start       DATE,
  window_end         DATE,
  rank               INTEGER,
  updated_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_top_products_rank ON top_products (rank);

CREATE TABLE IF NOT EXISTS sourcing_deals (
  sku                TEXT PRIMARY KEY,
  product_title      TEXT,
  product_rank       INTEGER,
  units_sold         INTEGER DEFAULT 0,
  takealot_price     NUMERIC(12, 2) DEFAULT 0,
  best_wholesaler    TEXT,
  unit_price         NUMERIC(12, 2) DEFAULT 0,
  shipping           NUMERIC(12, 2) DEFAULT 0,
  landed_cost        NUMERIC(12, 2) DEFAULT 0,
  gross_margin       NUMERIC(12, 2) DEFAULT 0,
  margin_pct         NUMERIC(6, 2) DEFAULT 0,
  available_stock    INTEGER DEFAULT 0,
  lead_time_days     INTEGER DEFAULT 0,
  supplier_url       TEXT,
  score              NUMERIC(6, 4) DEFAULT 0,
  computed_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sourcing_deal_history (
  id                 BIGSERIAL PRIMARY KEY,
  sku                TEXT NOT NULL,
  best_wholesaler    TEXT,
  unit_price         NUMERIC(12, 2),
  landed_cost        NUMERIC(12, 2),
  margin_pct         NUMERIC(6, 2),
  score              NUMERIC(6, 4),
  computed_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sourcing_history_sku_time
  ON sourcing_deal_history (sku, computed_at DESC);
