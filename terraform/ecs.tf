# ── ECS Cluster ───────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled" # detailed per-container CPU/memory metrics in CloudWatch
  }

  tags = { Name = "${local.name_prefix}-cluster" }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

# ── ECS Task Definition ───────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.app_cpu
  memory                   = var.app_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = local.app_image
      essential = true

      portMappings = [
        {
          containerPort = var.app_port
          protocol      = "tcp"
        }
      ]

      # Secrets — pulled from SSM at task startup (never in plaintext)
      secrets = [
        { name = "ANTHROPIC_API_KEY",  valueFrom = aws_ssm_parameter.anthropic_api_key.arn },
        { name = "OPENAI_API_KEY",     valueFrom = aws_ssm_parameter.openai_api_key.arn },
        { name = "PERPLEXITY_API_KEY", valueFrom = aws_ssm_parameter.perplexity_api_key.arn },
        { name = "GOOGLE_API_KEY",     valueFrom = aws_ssm_parameter.google_api_key.arn },
        { name = "FMP_API_KEY",        valueFrom = aws_ssm_parameter.fmp_api_key.arn },
        { name = "DB_PASSWORD",        valueFrom = aws_ssm_parameter.db_password.arn }
      ]

      # Non-sensitive environment variables
      environment = [
        { name = "APP_ENV",               value = var.environment },
        { name = "LOG_LEVEL",             value = "INFO" },
        { name = "DB_HOST",               value = aws_db_instance.postgres.address },
        { name = "DB_PORT",               value = "5432" },
        { name = "DB_NAME",               value = var.db_name },
        { name = "DB_USER",               value = var.db_username },
        { name = "DB_SSL",                value = "require" },
        { name = "REDIS_HOST",            value = aws_elasticache_cluster.redis.cache_nodes[0].address },
        { name = "REDIS_PORT",            value = "6379" },
        { name = "REDIS_DB",              value = "0" },
        { name = "PRIMARY_LLM",           value = "claude-sonnet-4-6" },
        { name = "MEMO_LLM",              value = "claude-opus-4-6" },
        { name = "EXTRACTION_LLM",        value = "gpt-4.1-mini" },
        { name = "PERPLEXITY_MODEL",      value = "sonar-deep-research" },
        { name = "EMBEDDING_MODEL",       value = "text-embedding-3-small" },
        { name = "EMBEDDING_DIM",         value = "1536" },
        { name = "VECTOR_BACKEND",        value = "pgvector" },
        { name = "VECTOR_COLLECTION",     value = "documents" },
        { name = "SEC_EDGAR_USER_AGENT",  value = "PhoenicianCapital admin@phoenician.capital" },
        { name = "SEC_RATE_LIMIT_RPS",    value = "10" },
        { name = "MIN_MARKET_CAP",        value = "250000000" },
        { name = "MAX_MARKET_CAP",        value = "5000000000" },
        { name = "HARD_MIN_MARKET_CAP",   value = "100000000" },
        { name = "HARD_MAX_MARKET_CAP",   value = "10000000000" }
      ]

      # Structured JSON logging → CloudWatch
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_app.name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "app"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.app_port}/api/v1/screening/status || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = { Name = "${local.name_prefix}-app-task" }
}

# ── ECS Service ───────────────────────────────────────────────────────────────

resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.app_desired_count
  launch_type     = "FARGATE"

  # Rolling deploys — keep old task running until new one is healthy
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  # Deployment circuit breaker — auto-rollback on failed deploy
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = [aws_subnet.private[1].id] # eu-north-1b only — eu-north-1a health checks timeout
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false # private subnet — outbound via NAT only
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.app_port
  }

  # Allow ECS to manage task placement without Terraform drift
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_task_execution_managed
  ]

  tags = { Name = "${local.name_prefix}-service" }
}
