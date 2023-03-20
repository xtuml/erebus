terraform {
  backend "s3" {
    bucket  = "terraform-state-cdsdt"
    key     = "test-harness/state.tfstate"
    region  = "eu-west-2"
    encrypt = true
    profile = "smartcdsdigitaltwin"
  }
}
