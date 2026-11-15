variable "databricks_profile" {
  description = "Databricks CLI profile used to authenticate (see ~/.databrickscfg)."
  type        = string
  default     = "citibike"
}

variable "catalog" {
  description = "Unity Catalog catalog that holds the project schemas."
  type        = string
  default     = "workspace"
}

variable "warehouse_name" {
  description = "Name of the SQL warehouse dbt runs on. Looked up by name so no ID is hard-coded."
  type        = string
  default     = "Serverless Starter Warehouse"
}

variable "warehouse_id" {
  description = "Optional. Set this to skip the lookup by name."
  type        = string
  default     = ""
}

variable "git_url" {
  description = "Repository the job checks out on every run."
  type        = string
  default     = "https://github.com/tushargarje750-alt/citibike-jc-lakehouse"
}

variable "git_branch" {
  description = "Branch the job runs."
  type        = string
  default     = "main"
}

variable "schedule_cron" {
  description = "Quartz cron expression (seconds minutes hours day-of-month month day-of-week)."
  type        = string
  default     = "0 0 6 ? * MON" # every Monday at 06:00
}

variable "schedule_timezone" {
  description = "Time zone the schedule is evaluated in."
  type        = string
  default     = "America/New_York"
}

variable "schedule_paused" {
  description = "Set to true to keep the job defined but stop scheduled runs."
  type        = bool
  default     = false
}

variable "dbt_package" {
  description = "pip requirement for the dbt adapter installed on the job's serverless environment."
  type        = string
  default     = "dbt-databricks==1.13.0"
}

variable "alert_emails" {
  description = "Optional list of addresses to email when a run fails. Set it in terraform.tfvars (git-ignored)."
  type        = list(string)
  default     = []
}

variable "dashboard_parent_path" {
  description = "Optional. Workspace folder for the dashboard. Default: a 'dashboards' folder in your home folder."
  type        = string
  default     = ""
}
