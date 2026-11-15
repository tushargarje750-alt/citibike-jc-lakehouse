# The whole pipeline as one scheduled Databricks job:
#
#   land_tripdata ──> bronze_trips ───┐
#                                     ├──> dbt_build   (silver + gold + all tests)
#   land_weather ───> bronze_weather ─┘
#
# Every task runs on serverless compute (no cluster is defined anywhere), and the
# code is checked out from GitHub on each run, so the job always runs what is on main.

data "databricks_sql_warehouse" "dbt" {
  count = var.warehouse_id == "" ? 1 : 0
  name  = var.warehouse_name
}

locals {
  warehouse_id = var.warehouse_id != "" ? var.warehouse_id : data.databricks_sql_warehouse.dbt[0].id

  notebook_parameters = {
    catalog = var.catalog
  }
}

resource "databricks_job" "pipeline" {
  name        = "citibike-jc-lakehouse"
  description = "Citi Bike JC & Hoboken lakehouse: land new files, load bronze, build and test silver and gold with dbt. Managed by Terraform (infra/terraform); do not edit in the UI."

  max_concurrent_runs = 1

  git_source {
    url      = var.git_url
    provider = "gitHub"
    branch   = var.git_branch
  }

  schedule {
    quartz_cron_expression = var.schedule_cron
    timezone_id            = var.schedule_timezone
    pause_status           = var.schedule_paused ? "PAUSED" : "UNPAUSED"
  }

  # Python environment for the dbt task (serverless tasks cannot use cluster libraries).
  environment {
    environment_key = "dbt"
    spec {
      environment_version = "2"
      dependencies        = [var.dbt_package]
    }
  }

  dynamic "email_notifications" {
    for_each = length(var.alert_emails) > 0 ? [1] : []
    content {
      on_failure = var.alert_emails
    }
  }

  # Tasks are listed in alphabetical order of task_key on purpose. Databricks returns
  # them in that order, and Terraform compares the list position by position, so any
  # other order makes every `terraform plan` report a change that is not real.
  # Execution order comes from depends_on, not from the order here:
  #   land_tripdata -> bronze_trips  -+
  #                                   +-> dbt_build
  #   land_weather  -> bronze_weather -+

  task {
    task_key    = "bronze_trips"
    description = "Auto Loader: append new trip CSVs to bronze and reconcile row counts."

    depends_on {
      task_key = "land_tripdata"
    }

    notebook_task {
      notebook_path   = "ingestion/notebooks/03_bronze_trips"
      source          = "GIT"
      base_parameters = local.notebook_parameters
    }
  }

  task {
    task_key    = "bronze_weather"
    description = "Rebuild the bronze weather table from the landed files."

    depends_on {
      task_key = "land_weather"
    }

    notebook_task {
      notebook_path   = "ingestion/notebooks/04_bronze_weather"
      source          = "GIT"
      base_parameters = local.notebook_parameters
    }
  }

  task {
    task_key        = "dbt_build"
    description     = "dbt build: silver and gold models plus every data test and unit test."
    environment_key = "dbt"

    depends_on {
      task_key = "bronze_trips"
    }
    depends_on {
      task_key = "bronze_weather"
    }

    dbt_task {
      source            = "GIT"
      project_directory = "dbt"
      commands          = ["dbt build"]
      warehouse_id      = local.warehouse_id
      catalog           = var.catalog
      schema            = "citibike"
    }
  }

  task {
    task_key    = "land_tripdata"
    description = "Download new or republished monthly trip files into the landing volume."

    notebook_task {
      notebook_path   = "ingestion/notebooks/01_land_tripdata"
      source          = "GIT"
      base_parameters = local.notebook_parameters
    }
  }

  task {
    task_key    = "land_weather"
    description = "Fetch daily weather for years that are missing or still open."

    notebook_task {
      notebook_path   = "ingestion/notebooks/02_land_weather"
      source          = "GIT"
      base_parameters = local.notebook_parameters
    }
  }
}
