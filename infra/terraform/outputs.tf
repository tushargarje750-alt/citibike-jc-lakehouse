output "job_id" {
  description = "ID of the pipeline job."
  value       = databricks_job.pipeline.id
}

output "job_url" {
  description = "Link to the job in the Databricks workspace."
  value       = databricks_job.pipeline.url
}

output "dashboard_id" {
  description = "ID of the ridership dashboard."
  value       = databricks_dashboard.ridership.id
}

output "dashboard_url" {
  description = "Link to the published dashboard."
  value       = "${local.workspace_url}/dashboardsv3/${databricks_dashboard.ridership.id}/published"
}
