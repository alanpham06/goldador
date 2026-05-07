variable "google_credentials_json" {
  description = "Google credentials JSON"
  type        = string
  sensitive   = true
}

locals {
  google_project_id = jsondecode(var.google_credentials_json)["quota_project_id"]
}
