variable "n8n_image" {
  description = "n8n container image"
  type        = string
  default     = "n8nio/n8n:latest"
}

variable "n8n_container_name" {
  type    = string
  default = "takealot-n8n"
}

variable "n8n_port" {
  description = "Host port for the n8n editor/API"
  type        = number
  default     = 5678
}

variable "n8n_base_url" {
  description = "External URL used for webhooks"
  type        = string
  default     = "http://localhost:5678"
}

variable "n8n_timezone" {
  type    = string
  default = "Africa/Johannesburg"
}

variable "n8n_user_management" {
  description = "Enable n8n user management/owner setup"
  type        = bool
  default     = true
}

variable "enable_queue_mode" {
  description = "Run a worker process with Redis queue mode"
  type        = bool
  default     = true
}

variable "workflow_dir" {
  description = "Directory of workflow JSON files, relative to this module"
  type        = string
  default     = "../workflows"
}

variable "postgres_image" {
  type    = string
  default = "postgres:16-alpine"
}

variable "postgres_container_name" {
  type    = string
  default = "takealot-postgres"
}

variable "postgres_port" {
  description = "Host port exposed for PGAdmin/psql (0 lets Docker pick a free port)"
  type        = number
  default     = 5432
}

variable "postgres_db" {
  description = "Database used by n8n itself"
  type        = string
  default     = "n8n"
}

variable "postgres_user" {
  type    = string
  default = "n8n"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "business_db" {
  description = "Separate database used by the reselling workflows"
  type        = string
  default     = "takealot"
}

variable "redis_image" {
  type    = string
  default = "redis:7-alpine"
}

variable "redis_container_name" {
  type    = string
  default = "takealot-redis"
}

variable "redis_password" {
  description = "Leave blank to generate and store one in Terraform state"
  type        = string
  default     = ""
  sensitive   = true
}

# ---------------------------------------------------------------------------
# Values exposed to the n8n workflows through $env
# ---------------------------------------------------------------------------

variable "takealot_api_key" {
  description = "Seller API key from Takealot Seller Portal"
  type        = string
  sensitive   = true
}

variable "takealot_api_base_url" {
  description = "Seller API base URL (no trailing slash)"
  type        = string
  default     = "https://seller-api.takealot.com/api/seller-api"
}

variable "takealot_api_version" {
  type    = string
  default = "v2"
}

variable "low_stock_threshold" {
  type    = number
  default = 5
}

variable "price_min_margin_percent" {
  type    = number
  default = 15
}

variable "price_undercut_cents" {
  type    = number
  default = 100
}

variable "slack_webhook_url" {
  description = "Slack incoming webhook URL"
  type        = string
  default     = ""
  sensitive   = true
}

variable "whatsapp_token" {
  description = "WhatsApp Cloud API token (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "whatsapp_phone_number_id" {
  type    = string
  default = ""
}

variable "whatsapp_recipient" {
  type    = string
  default = ""
}

variable "google_sheets_competitors_id" {
  description = "Spreadsheet ID with a CompetitorPrices tab"
  type        = string
  default     = ""
}

variable "google_sheets_catalogue_id" {
  description = "Spreadsheet ID with a Catalogue tab (cost prices)"
  type        = string
  default     = ""
}

variable "google_sheets_report_id" {
  description = "Spreadsheet ID for the daily profit report"
  type        = string
  default     = ""
}

variable "xero_tenant_id" {
  description = "Optional Xero tenant ID for invoice sync"
  type        = string
  default     = ""
  sensitive   = true
}

variable "takealot_warehouse_id" {
  description = "Merchant warehouse ID used for leadtime stock updates"
  type        = number
  default     = 1
}

variable "smtp_from_email" {
  description = "From address used by the SMTP credential"
  type        = string
  default     = "automation@example.com"
}

variable "alert_email" {
  description = "Destination for alert and report emails"
  type        = string
  default     = "owner@example.com"
}

variable "google_sheets_wholesale_id" {
  description = "Spreadsheet ID with a WholesalePrices tab"
  type        = string
  default     = ""
}

variable "top_products_limit" {
  description = "Number of top-selling SKUs to analyse for wholesale deals"
  type        = number
  default     = 25
}

variable "target_margin_percent" {
  description = "Target gross margin used when scoring wholesale deals"
  type        = number
  default     = 25
}
