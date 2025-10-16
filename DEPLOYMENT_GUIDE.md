# Vertex AI Gateway Deployment Guide

This guide will help you deploy the LiteLLM Vertex AI Gateway with guardrails and cost monitoring.

## Prerequisites

1. **Kubernetes Cluster**: Running Kubernetes 1.21+
2. **Helm**: Version 3.8.0 or higher
3. **Google Cloud Project**: With Vertex AI API enabled
4. **Service Account**: With appropriate Vertex AI permissions

## Step 1: Prepare Your GCP Service Account

### Option A: Create a New Service Account

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Create service account
gcloud iam service-accounts create vertexai-gateway \
    --description="Service account for Vertex AI Gateway" \
    --display-name="Vertex AI Gateway"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:vertexai-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:vertexai-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/ml.developer"

# Download service account key (if not using Workload Identity)
gcloud iam service-accounts keys create vertexai-key.json \
    --iam-account=vertexai-gateway@$PROJECT_ID.iam.gserviceaccount.com
```

### Option B: Use Existing Service Account

If you already have a service account key file, ensure it has the following permissions:
- `roles/aiplatform.user`
- `roles/ml.developer`

## Step 2: Configure Your Values File

Create a custom values file:

```bash
cp litellm-helm/values.yaml my-values.yaml
```

Edit `my-values.yaml` with your configuration:

```yaml
# Basic Configuration
namespace: litellm-gateway
masterKey: "your-secure-master-key-here"  # Change this!

# Service Account Configuration
serviceAccount:
  create: true
  name: litellm-service
  gcpSAEmail: vertexai-gateway@your-project.iam.gserviceaccount.com

# GCP Configuration
gcp:
  serviceAccount:
    create: false
  # If using service account key file (paste your JSON key here):
  # serviceAccountKey: |
  #   {
  #     "type": "service_account",
  #     "project_id": "your-project-id",
  #     "private_key_id": "[REDACTED]",
  #     "private_key": "[REDACTED]",
  #     "client_email": "[SERVICE_ACCOUNT_EMAIL]"
  #   }

# Vertex AI Models Configuration
proxyConfig:
  model_list:
    - model_name: vertex-gemini-pro
      litellm_params:
        model: vertex_ai/gemini-pro
        vertex_project: your-gcp-project-id  # Change this!
        vertex_location: us-central1
    - model_name: vertex-gemini-flash
      litellm_params:
        model: vertex_ai/gemini-1.5-flash
        vertex_project: your-gcp-project-id  # Change this!
        vertex_location: us-central1

# Cost Monitoring (adjust budgets as needed)
costMonitoring:
  enabled: true
  budgets:
    daily: 50.0      # $50 daily budget
    weekly: 300.0    # $300 weekly budget
    monthly: 1000.0  # $1000 monthly budget

# Guardrails (customize as needed)
guardrails:
  enabled: true
  contentFilter:
    blockPII: true
    blockToxic: true
    blockHate: true
    blockViolence: true
    blockSexual: true

# Rate Limiting (adjust as needed)
rateLimit:
  enabled: true
  limit:
    qpm: 100       # Queries per minute
    qpd: 2000      # Queries per day
    concurrent: 20  # Max concurrent requests

# Service Configuration
service:
  type: LoadBalancer  # Change to ClusterIP if using Ingress
  port: 4000

# Resource Configuration
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 1000m
    memory: 2Gi
```

## Step 3: Deploy the Gateway

```bash
# Create namespace
kubectl create namespace litellm-gateway

# Deploy using Helm
helm install litellm-gateway ./litellm-helm -f my-values.yaml

# Check deployment status
kubectl get pods -n litellm-gateway
kubectl get services -n litellm-gateway
```

## Step 4: Verify Deployment

### Check Pod Status
```bash
kubectl logs -n litellm-gateway deployment/litellm -f
```

### Test Health Endpoints
```bash
# Get the service IP
kubectl get service -n litellm-gateway litellm

# Test health check (replace IP with your service IP)
curl http://YOUR_SERVICE_IP:4000/health/readyz
```

### Test API Endpoint
```bash
# Test a simple request
curl -X POST http://YOUR_SERVICE_IP:4000/v1/chat/completions \
  -H "Authorization: Bearer your-secure-master-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vertex-gemini-pro",
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "max_tokens": 100
  }'
```

## Step 5: Set Up Monitoring (Optional)

### Prometheus Metrics
If you have Prometheus installed in your cluster:

```bash
# Check if ServiceMonitor was created
kubectl get servicemonitor -n litellm-gateway

# View metrics endpoint
curl http://YOUR_SERVICE_IP:9090/metrics
```

### Grafana Dashboard
Import the provided Grafana dashboard to visualize:
- Request rates and latency
- Cost trends and budget utilization
- Error rates and guardrail violations

## Step 6: Configure Ingress (Optional)

If you want to expose the gateway via Ingress:

```yaml
# Add to your values file
service:
  type: ClusterIP

ingress:
  enabled: true
  className: "nginx"  # or your ingress class
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
  hosts:
    - host: vertex-ai-gateway.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: vertex-ai-gateway-tls
      hosts:
        - vertex-ai-gateway.yourdomain.com
```

## Troubleshooting

### Common Issues

1. **Pod Not Starting**
   ```bash
   kubectl describe pod -n litellm-gateway -l app=litellm
   kubectl logs -n litellm-gateway -l app=litellm
   ```

2. **Authentication Errors**
   - Verify your service account has correct permissions
   - Check if service account key is properly configured
   - Ensure Workload Identity is set up correctly (if using)

3. **Vertex AI API Errors**
   ```bash
   # Check if Vertex AI API is enabled
   gcloud services list --enabled --filter="name:aiplatform.googleapis.com"
   
   # Enable if not enabled
   gcloud services enable aiplatform.googleapis.com
   ```

4. **Budget/Cost Monitoring Not Working**
   - Check environment variables in the pod
   - Verify cost monitoring is enabled in values
   - Check logs for cost calculation errors

### Debug Commands

```bash
# Check all resources
kubectl get all -n litellm-gateway

# Check configmap
kubectl get configmap -n litellm-gateway litellm-config -o yaml

# Check secrets
kubectl get secrets -n litellm-gateway

# Check service account
kubectl get serviceaccount -n litellm-gateway

# Port forward for local testing
kubectl port-forward -n litellm-gateway service/litellm 4000:4000
```

## Security Best Practices

1. **Change Default Master Key**: Always use a strong, unique master key
2. **Use Workload Identity**: Preferred over service account key files
3. **Network Policies**: Implement network policies to restrict traffic
4. **Resource Limits**: Set appropriate CPU and memory limits
5. **Regular Updates**: Keep the gateway and dependencies updated

## Scaling Considerations

### Horizontal Scaling
```yaml
# Add to values file
replicaCount: 3

# Or use HPA
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

### Vertical Scaling
```yaml
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

## Maintenance

### Updating the Gateway
```bash
# Update values if needed
helm upgrade litellm-gateway ./litellm-helm -f my-values.yaml

# Check rollout status
kubectl rollout status deployment/litellm -n litellm-gateway
```

### Backup Configuration
```bash
# Backup your values file
cp my-values.yaml my-values-backup-$(date +%Y%m%d).yaml

# Export current configuration
helm get values litellm-gateway > current-values.yaml
```

## Support

For issues and questions:
1. Check the logs: `kubectl logs -n litellm-gateway deployment/litellm`
2. Review the troubleshooting section above
3. Check the main README.md for detailed configuration options
4. Create an issue in the repository with logs and configuration details
