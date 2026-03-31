# ── ECS Infrastructure ───────────────────────────────────────────────────────

# ECS Cluster
resource "aws_ecs_cluster" "screening_engine" {
  name = "screening-engine-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "Screening Engine Cluster"
  }
}

# ECS Cluster Capacity Providers (EC2)
resource "aws_ecs_cluster_capacity_providers" "screening_engine" {
  cluster_name = aws_ecs_cluster.screening_engine.name

  capacity_providers = ["SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "SPOT"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/screening-engine"
  retention_in_days = 7

  tags = {
    Name = "Screening Engine ECS Logs"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "screening_engine" {
  family                   = "screening-engine"
  network_mode             = "host"
  requires_compatibilities = ["EC2"]
  cpu                      = "2048"
  memory                   = "4096"

  container_definitions = jsonencode([
    {
      name      = "screening-engine-api"
      image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/screening-engine:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      environment = [
        {
          name  = "DB_HOST"
          value = "localhost"
        },
        {
          name  = "DB_PORT"
          value = "5432"
        },
        {
          name  = "DB_NAME"
          value = "phoenician"
        }
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/screening/status || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "Screening Engine Task Definition"
  }
}

# ECS Service
resource "aws_ecs_service" "screening_engine" {
  name            = "screening-engine-service"
  cluster         = aws_ecs_cluster.screening_engine.id
  task_definition = aws_ecs_task_definition.screening_engine.arn
  desired_count   = 1
  launch_type     = "EC2"

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  placement_strategies {
    type  = "spread"
    field = "instanceId"
  }

  tags = {
    Name = "Screening Engine Service"
  }

  depends_on = [aws_cloudwatch_log_group.ecs]
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  alarm_name          = "screening-engine-ecs-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    ClusterName = aws_ecs_cluster.screening_engine.name
    ServiceName = aws_ecs_service.screening_engine.name
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_memory" {
  alarm_name          = "screening-engine-ecs-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    ClusterName = aws_ecs_cluster.screening_engine.name
    ServiceName = aws_ecs_service.screening_engine.name
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
