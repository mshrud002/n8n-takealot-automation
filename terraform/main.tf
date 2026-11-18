locals {
  redis_password = var.redis_password != "" ? var.redis_password : random_password.redis.result
  workflow_path  = abspath("${path.module}/${var.workflow_dir}")
  sql_path       = abspath("${path.module}/../sql")
  sql_files      = sort(fileset(local.sql_path, "*.sql"))
  sql_hash       = join(",", [for f in local.sql_files : filemd5("${local.sql_path}/${f}")])
  workflow_hash  = join(",", [for f in fileset(local.workflow_path, "*.json") : filemd5("${local.workflow_path}/${f}")])

  common_env = [
    "N8N_ENCRYPTION_KEY=${random_password.encryption.result}",
    "DB_TYPE=postgresdb",
    "DB_POSTGRESDB_HOST=${var.postgres_container_name}",
    "DB_POSTGRESDB_PORT=5432",
    "DB_POSTGRESDB_DATABASE=${var.postgres_db}",
    "DB_POSTGRESDB_USER=${var.postgres_user}",
    "DB_POSTGRESDB_PASSWORD=${var.postgres_password}",
    "DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false",
    "GENERIC_TIMEZONE=${var.n8n_timezone}",
    "TZ=${var.n8n_timezone}",
    "N8N_DIAGNOSTICS_ENABLED=false",
    "N8N_VERSION_NOTIFICATIONS_ENABLED=false",
    "N8N_TEMPLATES_ENABLED=false",
    "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
  ]

  workflow_env = [
    "TAKEALOT_API_KEY=${var.takealot_api_key}",
    "TAKEALOT_API_BASE_URL=${var.takealot_api_base_url}",
    "TAKEALOT_API_VERSION=${var.takealot_api_version}",
    "TAKEALOT_WAREHOUSE_ID=${var.takealot_warehouse_id}",
    "BUSINESS_DB_HOST=${var.postgres_container_name}",
    "BUSINESS_DB_PORT=5432",
    "BUSINESS_DB_NAME=${var.business_db}",
    "BUSINESS_DB_USER=${var.postgres_user}",
    "BUSINESS_DB_PASSWORD=${var.postgres_password}",
    "LOW_STOCK_THRESHOLD=${var.low_stock_threshold}",
    "PRICE_MIN_MARGIN_PERCENT=${var.price_min_margin_percent}",
    "PRICE_UNDERCUT_CENTS=${var.price_undercut_cents}",
    "SLACK_WEBHOOK_URL=${var.slack_webhook_url}",
    "WHATSAPP_TOKEN=${var.whatsapp_token}",
    "WHATSAPP_PHONE_NUMBER_ID=${var.whatsapp_phone_number_id}",
    "WHATSAPP_RECIPIENT=${var.whatsapp_recipient}",
    "GOOGLE_SHEETS_COMPETITORS_ID=${var.google_sheets_competitors_id}",
    "GOOGLE_SHEETS_CATALOGUE_ID=${var.google_sheets_catalogue_id}",
    "GOOGLE_SHEETS_REPORT_ID=${var.google_sheets_report_id}",
    "GOOGLE_SHEETS_WHOLESALE_ID=${var.google_sheets_wholesale_id}",
    "TOP_PRODUCTS_LIMIT=${var.top_products_limit}",
    "TARGET_MARGIN_PERCENT=${var.target_margin_percent}",
    "XERO_TENANT_ID=${var.xero_tenant_id}",
    "SMTP_FROM_EMAIL=${var.smtp_from_email}",
    "ALERT_EMAIL=${var.alert_email}",
  ]

  queue_env = [
    "EXECUTIONS_MODE=queue",
    "QUEUE_BULL_REDIS_HOST=${var.redis_container_name}",
    "QUEUE_BULL_REDIS_PORT=6379",
    "QUEUE_BULL_REDIS_PASSWORD=${local.redis_password}",
    "N8N_REDIS_KEY_PREFIX=takealot",
  ]
}

resource "random_password" "encryption" {
  length  = 32
  special = false
}

resource "random_password" "redis" {
  length  = 24
  special = false
}

resource "docker_network" "n8n" {
  name = "takealot-n8n-net"
}

resource "docker_volume" "n8n_data" {
  name = "takealot-n8n-data"
}

resource "docker_volume" "postgres_data" {
  name = "takealot-postgres-data"
}

resource "docker_volume" "redis_data" {
  name = "takealot-redis-data"
}

resource "docker_image" "n8n" {
  name         = var.n8n_image
  keep_locally = true
}

resource "docker_image" "postgres" {
  name         = var.postgres_image
  keep_locally = true
}

resource "docker_image" "redis" {
  name         = var.redis_image
  keep_locally = true
}

resource "docker_container" "postgres" {
  name    = var.postgres_container_name
  image   = docker_image.postgres.image_id
  restart = "unless-stopped"

  networks_advanced {
    name = docker_network.n8n.name
  }

  ports {
    internal = 5432
    external = var.postgres_port
  }

  env = [
    "POSTGRES_DB=${var.postgres_db}",
    "POSTGRES_USER=${var.postgres_user}",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "PGDATA=/var/lib/postgresql/data/pgdata",
  ]

  volumes {
    volume_name    = docker_volume.postgres_data.name
    container_path = "/var/lib/postgresql/data"
  }

  healthcheck {
    test         = ["CMD-SHELL", "pg_isready -U ${var.postgres_user} -d ${var.postgres_db}"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 12
    start_period = "10s"
  }
}

resource "docker_container" "redis" {
  name    = var.redis_container_name
  image   = docker_image.redis.image_id
  restart = "unless-stopped"

  networks_advanced {
    name = docker_network.n8n.name
  }

  command = [
    "redis-server",
    "--requirepass", local.redis_password,
    "--appendonly", "yes",
    "--dir", "/data",
  ]

  volumes {
    volume_name    = docker_volume.redis_data.name
    container_path = "/data"
  }

  healthcheck {
    test         = ["CMD-SHELL", "redis-cli -a '${local.redis_password}' ping | grep -q PONG"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 12
    start_period = "5s"
  }
}

resource "docker_container" "n8n" {
  name    = var.n8n_container_name
  image   = docker_image.n8n.image_id
  restart = "unless-stopped"

  networks_advanced {
    name = docker_network.n8n.name
  }

  ports {
    internal = 5678
    external = var.n8n_port
  }

  env = concat(
    local.common_env,
    local.workflow_env,
    local.queue_env,
    [
      "N8N_HOST=localhost",
      "N8N_PORT=5678",
      "N8N_PROTOCOL=http",
      "WEBHOOK_URL=${var.n8n_base_url}",
      "N8N_API_ENABLED=true",
      "N8N_USER_MANAGEMENT_DISABLED=${var.n8n_user_management ? "false" : "true"}",
    ],
  )

  volumes {
    volume_name    = docker_volume.n8n_data.name
    container_path = "/home/node/.n8n"
  }

  volumes {
    host_path      = local.workflow_path
    container_path = "/workflows"
    read_only      = true
  }

  healthcheck {
    test         = ["CMD", "node", "-e", "require('http').get('http://localhost:5678/healthz',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"]
    interval     = "20s"
    timeout      = "5s"
    retries      = 20
    start_period = "30s"
  }

  depends_on = [docker_container.postgres, docker_container.redis]
}

resource "docker_container" "worker" {
  count   = var.enable_queue_mode ? 1 : 0
  name    = "${var.n8n_container_name}-worker"
  image   = docker_image.n8n.image_id
  restart = "unless-stopped"
  command = ["worker"]

  networks_advanced {
    name = docker_network.n8n.name
  }

  env = concat(
    local.common_env,
    local.workflow_env,
    local.queue_env,
  )

  volumes {
    volume_name    = docker_volume.n8n_data.name
    container_path = "/home/node/.n8n"
  }

  volumes {
    host_path      = local.workflow_path
    container_path = "/workflows"
    read_only      = true
  }

  depends_on = [docker_container.n8n, docker_container.postgres, docker_container.redis]
}

resource "null_resource" "business_db" {
  triggers = {
    schema = local.sql_hash
    db     = var.business_db
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      EXISTS=$$(docker exec ${var.postgres_container_name} psql -U ${var.postgres_user} -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${var.business_db}'" || true)
      if [ "$$EXISTS" != "1" ]; then
        docker exec ${var.postgres_container_name} psql -U ${var.postgres_user} -d postgres -c "CREATE DATABASE ${var.business_db}"
      fi
    EOT
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      for f in "${local.sql_path}"/*.sql; do
        docker exec -i ${var.postgres_container_name} psql -v ON_ERROR_STOP=1 -U ${var.postgres_user} -d ${var.business_db} < "$$f"
      done
    EOT
  }

  depends_on = [docker_container.postgres]
}

resource "null_resource" "workflow_import" {
  triggers = {
    workflow_hashes = local.workflow_hash
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      for i in $$(seq 1 60); do
        if docker exec -u node ${var.n8n_container_name} n8n --version >/dev/null 2>&1; then
          break
        fi
        sleep 5
      done
      IMPORTED=0
      for i in $$(seq 1 10); do
        if docker exec -u node ${var.n8n_container_name} n8n import:workflow --separate --input=/workflows; then
          IMPORTED=1
          break
        fi
        sleep 10
      done
      if [ "$$IMPORTED" != "1" ]; then
        echo "workflow import failed" >&2
        exit 1
      fi
    EOT
  }

  depends_on = [docker_container.n8n, docker_container.worker, null_resource.business_db]
}
