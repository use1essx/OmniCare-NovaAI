# Setup Guide - OmniCare Healthcare AI

## Prerequisites

- Docker Desktop installed
- AWS Account with Bedrock access enabled
- IAM user with Bedrock permissions

## AWS Setup

### 1. Enable Bedrock Models

Go to AWS Console > Bedrock > Model access and enable:
- Amazon Nova Lite
- Amazon Nova Pro  
- Amazon Titan Embeddings

### 2. Create IAM User

Create an IAM user with this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"
      ]
    }
  ]
}
```

Save the Access Key ID and Secret Access Key.

## Application Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd healthcare_ai_live2d_unified
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your AWS credentials:

```bash
# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1
USE_BEDROCK=true
```

### 3. Start Application

```bash
docker-compose up -d
```

Wait for all containers to be healthy:

```bash
docker-compose ps
```

### 4. Access Application

- Main Application: http://localhost:8000
- PgAdmin: http://localhost:5050

## Verification

Test that Nova is working:

```bash
curl http://localhost:8000/health
```

Should return `{"status": "healthy", "nova_configured": true}`

## Troubleshooting

**Issue**: Nova not configured
- Check AWS credentials in `.env`
- Verify Bedrock models are enabled in AWS Console
- Check IAM permissions

**Issue**: Container not starting
- Check Docker logs: `docker-compose logs healthcare_ai`
- Verify ports 8000 and 5050 are available

**Issue**: Budget exceeded
- Check budget status: `GET /api/v1/budget/status` (requires admin auth)
- Reset if needed (development only)

## Development

Run tests:

```bash
docker-compose exec healthcare_ai pytest -v
```

View logs:

```bash
docker-compose logs -f healthcare_ai
```

## Production Deployment

For production, consider:
- Use AWS Secrets Manager for credentials
- Enable CloudWatch logging
- Set up AWS Budget alerts
- Use RDS for PostgreSQL
- Deploy with ECS/EKS
