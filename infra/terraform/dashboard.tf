# The ridership dashboard, deployed from the definition in dashboards/.
# The same file can also be imported by hand in the Databricks UI
# (Dashboards > Create > Import dashboard from file).

data "databricks_current_user" "me" {
  count = var.dashboard_parent_path == "" ? 1 : 0
}

locals {
  dashboard_file = "${path.module}/../../dashboards/citibike_ridership.lvdash.json"

  # Default: a "dashboards" folder in the home folder of whoever runs Terraform.
  dashboard_parent_path = (
    var.dashboard_parent_path != ""
    ? var.dashboard_parent_path
    : "${data.databricks_current_user.me[0].home}/dashboards"
  )

  # The file is written for the default catalog; swap in var.catalog if it differs.
  dashboard_json = replace(
    file(local.dashboard_file),
    "workspace.citibike_gold.",
    "${var.catalog}.citibike_gold."
  )

  workspace_url = split("/#", databricks_job.pipeline.url)[0]
}

resource "databricks_directory" "dashboards" {
  path = local.dashboard_parent_path
}

resource "databricks_dashboard" "ridership" {
  display_name         = "Citi Bike JC & Hoboken - Ridership"
  parent_path          = databricks_directory.dashboards.path
  warehouse_id         = local.warehouse_id
  serialized_dashboard = local.dashboard_json
  embed_credentials    = true
}
