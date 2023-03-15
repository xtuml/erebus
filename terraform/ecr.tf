#tfsec:ignore:aws-ecr-repository-customer-key
resource "aws_ecr_repository" "test_harness" {
  name                 = local.application_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS" 
  }
}

# resource "aws_ecr_lifecycle_policy" "test_harness" {
#   repository = aws_ecr_repository.test_harness.name

#   policy = <<EOF
# {
#   "rules": [
#     {
#       "rulePriority": 1,
#       "description": "Expire untagged images older than 14 days",
#       "seclection": {
#         "tagStatus": "untagged",
#         "countType": "sinceImagePushed",
#         "countUnit": "days",
#         "countNumber": 14
#       },
#       "action": {
#         "type": "expire"
#       }
#     }
#   ]
# }
# EOF
# }