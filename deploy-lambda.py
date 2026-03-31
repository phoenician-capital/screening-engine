"""
AWS Lambda function for auto-deploying on GitHub webhook
Deploy with: zip function.zip deploy-lambda.py && aws lambda create-function \
  --function-name screening-engine-deploy \
  --runtime python3.11 \
  --handler deploy-lambda.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-ec2-role \
  --zip-file fileb://function.zip
"""

import json
import boto3
import hmac
import hashlib

ssm = boto3.client('ssm', region_name='eu-north-1')

def lambda_handler(event, context):
    """Handle GitHub webhook push events"""

    # Verify GitHub webhook signature (optional but recommended)
    # signature = event.get('headers', {}).get('x-hub-signature-256', '')
    # if not verify_signature(event['body'], signature):
    #     return {'statusCode': 401, 'body': 'Unauthorized'}

    try:
        payload = json.loads(event['body'])

        # Only deploy on main branch pushes
        if payload.get('ref') != 'refs/heads/main':
            return {'statusCode': 200, 'body': 'Skipped (not main branch)'}

        # Send command to EC2 instance
        response = ssm.send_command(
            InstanceIds=['i-08bd901b0a0efefad'],  # screening-engine instance ID
            DocumentName='AWS-RunShellScript',
            Parameters={
                'command': [
                    'cd ~/screening-engine',
                    'git pull origin main',
                    'docker compose restart mcp-server',
                    'echo "✅ Deploy complete at $(date)"'
                ]
            }
        )

        command_id = response['Command']['CommandId']
        print(f"Deploy triggered: {command_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'Deploy triggered',
                'command_id': command_id
            })
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def verify_signature(body, signature):
    """Verify GitHub webhook signature"""
    secret = 'your-github-webhook-secret'  # Set this as Lambda env var
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
