output "n8n_url" {
  value = var.n8n_base_url
}

output "n8n_container" {
  value = var.n8n_container_name
}

output "postgres_container" {
  value = var.postgres_container_name
}

output "business_database" {
  value = var.business_db
}

output "next_steps" {
  value = <<-EOT
    1. Open ${var.n8n_base_url} and complete the owner setup.
    2. Create credentials: 'Takealot Postgres', 'Takealot Google Sheets', 'Takealot SMTP', 'Takealot Xero' (optional).
    3. Open each imported workflow, attach credentials to the marked nodes, then activate it.
  EOT
}
