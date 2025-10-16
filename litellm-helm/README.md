# LiteLLM Vertex AI Gateway with Guardrails and Cost Monitoring

This Helm chart deploys a comprehensive LiteLLM gateway for Google Cloud Vertex AI with advanced guardrails, cost monitoring, and usage analytics.

## Features

### 🛡️ **Guardrails & Safety**
- **Content Filtering**: Block PII, toxic content, hate speech, violence, and sexual content
- **Input Validation**: Token limits, request size limits, content type validation
- **Output Validation**: Token limits, secret scanning in responses
- **Request Monitoring**: Suspicious request logging and anomaly detection

### 💰 **Cost Monitoring & Budget Controls**
- **Multi-tier Budgets**: Daily, weekly, and monthly budget limits
- **Real-time Cost Tracking**: Per-model, per-user cost tracking
- **Budget Alerts**: Warning (75%), Critical (90%), Emergency (95%) thresholds
- **Cost Analytics**: Detailed cost breakdowns and usage patterns

### 📊 **Analytics & Monitoring**
- **Usage Metrics**: Request counts, token usage, latency tracking
- **Prometheus Integration**: Custom metrics for monitoring
- **Comprehensive Logging**: Configurable logging levels and destinations
- **Health Checks**: Liveness and readiness probes

### 🚀 **Enhanced Rate Limiting**
- **Multi-dimensional Limits**: QPM, QPH, QPD, concurrent requests
- **Per-user Limits**: Individual user rate limiting
- **Model-specific Limits**: Different limits per AI model
- **Memory-based Storage**: No Redis dependency

## Quick Start

### Prerequisites
- Kubernetes cluster with Helm 3.x
- Google Cloud Project with Vertex AI API enabled
- Service Account with Vertex AI permissions

### Installation

1. **Configure your values:**
```bash
# Copy and edit the values file
cp values.yaml my-values.yaml
# Edit my-values.yaml with your configuration
```

2. **Install the chart:**
```bash
helm install litellm-gateway . -f my-values.yaml
```

## Configuration

### Basic Configuration

```yaml
# Service Account Configuration
serviceAccount:
  gcpSAEmail: your-service-account@project.iam.gserviceaccount.com

# Vertex AI Models
proxyConfig:
  model_list:
    - model_name: vertex-gemini-pro
      litellm_params:
        model: vertex_ai/gemini-pro
        vertex_project: your-gcp-project
        vertex_location: us-central1
```

### Cost Monitoring Configuration

```yaml
costMonitoring:
  enabled: true
  budgets:
    daily: 100.0      # $100 daily budget
    weekly: 500.0     # $500 weekly budget
    monthly: 2000.0   # $2000 monthly budget
  
  alerts:
    warning: 75       # Alert at 75% of budget
    critical: 90      # Alert at 90% of budget
    emergency: 95     # Block requests at 95% of budget
```

### Guardrails Configuration

```yaml
guardrails:
  enabled: true
  contentFilter:
    blockPII: true           # Block personally identifiable information
    blockToxic: true         # Block toxic content
    blockHate: true          # Block hate speech
    blockViolence: true      # Block violent content
    blockSexual: true        # Block sexual content
  
  inputValidation:
    maxTokens: 8192          # Maximum input tokens
    maxRequestSize: 1048576  # 1MB max request size
  
  outputValidation:
    maxTokens: 8192          # Maximum output tokens
    scanForSecrets: true     # Scan output for API keys, passwords
```

### Rate Limiting Configuration

```yaml
rateLimit:
  enabled: true
  backend: memory  # No Redis required
  limit:
    qpm: 60        # Queries per minute
    qpd: 1000      # Queries per day
    qph: 300       # Queries per hour
    concurrent: 10  # Max concurrent requests
  
  # Per-user limits
  userLimits:
    enabled: true
    defaultQpm: 30
    defaultQpd: 500
```

## Using Your GCP Service Account Key

If you have downloaded a Vertex AI JSON key for your service account, you can use it in two ways:

### Option 1: Workload Identity (Recommended)
Configure Workload Identity to bind your Kubernetes service account to your GCP service account:

```yaml
serviceAccount:
  create: true
  name: litellm-service
  gcpSAEmail: vertexai@your-project.iam.gserviceaccount.com
```

### Option 2: Service Account Key File
Add your service account key to the values file:

```yaml
gcp:
  serviceAccountKey: |
    {
      "type": "service_account",
      "project_id": "your-project-id",
      "private_key_id": "[REDACTED]",
      "private_key": "[REDACTED]",
      "client_email": "[SERVICE_ACCOUNT_EMAIL]",
      "client_id": "[REDACTED]",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/service-account%40your-project.iam.gserviceaccount.com"
    }
```

## API Usage

### Making Requests

```bash
# Basic request
curl -X POST http://your-gateway:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vertex-gemini-pro",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Monitoring Endpoints

```bash
# Health check
curl http://your-gateway:4000/health/readyz

# Cost status (if implemented)
curl http://your-gateway:4000/cost/status

# Metrics (Prometheus format)
curl http://your-gateway:9090/metrics
```

## Monitoring and Observability

### Prometheus Metrics

The gateway exposes custom metrics on port 9090:
- `vertex_ai_requests_total`: Total number of requests
- `vertex_ai_cost_total`: Total cost of requests
- `vertex_ai_tokens_total`: Total tokens processed
- `vertex_ai_latency_seconds`: Request latency histogram

**Monitoring Setup Options:**

1. **Basic Prometheus Scraping** (Default):
   ```yaml
   monitoring:
     enabled: true
     prometheus:
       enabled: true
       serviceMonitor:
         enabled: false  # Default - uses service annotations
   ```

2. **Prometheus Operator with ServiceMonitor**:
   ```yaml
   monitoring:
     enabled: true
     prometheus:
       enabled: true
       serviceMonitor:
         enabled: true  # Requires Prometheus Operator
   ```

### Alerting

Configure alerts for:
- Budget threshold breaches
- High error rates
- Guardrail violations
- Service health issues

## Security Considerations

### Content Safety
- All requests are scanned for PII, toxic content, and secrets
- Configurable content filtering rules
- Output validation to prevent data leakage

### Access Control
- Master key authentication required
- Per-user rate limiting
- Request logging and audit trails

### Data Privacy
- Response content not logged by default
- Configurable data retention policies
- In-memory storage (no persistent data)

## Troubleshooting

### Common Issues

1. **Service Account Permissions**
   ```bash
   # Verify your service account has required permissions
   gcloud projects add-iam-policy-binding YOUR_PROJECT \
     --member="serviceAccount:vertexai@YOUR_PROJECT.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

2. **Budget Alerts Not Working**
   - Check environment variables are properly set
   - Verify cost monitoring is enabled
   - Check logs for cost calculation errors

3. **Guardrails Blocking Valid Requests**
   - Review content filter settings
   - Check token limits
   - Examine request logs for violation details

### Debugging

Enable debug logging:
```yaml
analytics:
  logging:
    level: DEBUG
    logRequests: true
    logErrors: true
```

Check pod logs:
```bash
kubectl logs -n litellm-gateway deployment/litellm -f
```

## Advanced Configuration

### Custom Cost Models
```yaml
costMonitoring:
  modelCosts:
    vertex-gemini-pro:
      inputTokenCost: 0.000125   # per 1K tokens
      outputTokenCost: 0.000375  # per 1K tokens
    custom-model:
      inputTokenCost: 0.0001
      outputTokenCost: 0.0002
```

### Custom Guardrails
```yaml
guardrails:
  inputValidation:
    allowedContentTypes:
      - "text/plain"
      - "application/json"
      - "multipart/form-data"
  
  monitoring:
    logSuspiciousRequests: true
    alertOnAnomalies: true
```

### Caching Configuration
```yaml
proxyConfig:
  general_settings:
    cache: true
    cache_params:
      type: memory
      ttl: 3600  # 1 hour cache
```

## Legacy Configuration Support

This chart maintains backward compatibility with the original LiteLLM Helm chart configuration. The following legacy parameters are still supported:

- `replicaCount`: Number of LiteLLM Proxy pods
- `masterkey`: Master API Key for LiteLLM
- `environmentSecrets`: Array of Secret object names for environment variables
- `image.*`: Image configuration settings
- `service.*`: Kubernetes Service configuration
- `ingress.*`: Ingress configuration

For database configurations and other legacy settings, please refer to the original documentation or migrate to the new memory-based approach.
