terraform {
  required_version = ">= 1.6.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.100.0, < 2.0.0"
    }
  }
}

# Authentication comes from the Databricks CLI profile created in Phase 0
# (`databricks auth login --profile citibike`). No host or token is stored in this repo.
provider "databricks" {
  profile = var.databricks_profile
}
