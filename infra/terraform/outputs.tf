output "job_id" {
  description = "ID of the pipeline job."
  value       = databricks_job.pipeline.id
}

output "job_url" {
  description = "Link to the job in the Databricks workspace."
  value       = databricks_job.pipeline.url
}
