terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "4.58.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.13.1"
    }
  }
  required_version = "1.3.7"
}

provider "aws" {
  region  = "eu-west-2"
  profile = "smartcdsdigitaltwin"

  default_tags {
    tags = {
      Application = local.application_name
      Environment = "Production"
      IaC         = "Terraform"
      Client      = "CDSDT"
      GitlabRepo  = local.gitlab_repo
      GitlabGroup = local.gitlab_group
    }
  }
}
