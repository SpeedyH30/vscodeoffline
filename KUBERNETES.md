# VSCode Offline Kubernetes Deployment Guide

This guide shows you how to deploy VSCode Offline to Kubernetes using the included Helm chart.

## 🚀 Quick Start

### Prerequisites

- Kubernetes cluster (1.19+)
- Helm 3.2.0+
- kubectl configured to access your cluster

### 1. Clone the Repository

```bash
git clone https://github.com/SpeedyH30/vscodeoffline.git
cd vscodeoffline
```

### 2. Deploy with Helm

#### Option A: Development Deployment (Minimal Resources)

```bash
# Create namespace and install
kubectl create namespace vscode-offline
helm install vscode-offline ./helm/vscode-offline \
  -f ./helm/vscode-offline/examples/development.yaml \
  --namespace vscode-offline
```

#### Option B: Production Deployment (With Ingress)

```bash
# Install with production configuration
kubectl create namespace vscode-offline
helm install vscode-offline ./helm/vscode-offline \
  -f ./helm/vscode-offline/examples/production.yaml \
  --namespace vscode-offline \
  --set vscgallery.ingress.hosts[0].host=vscode.yourdomain.com
```

#### Option C: Minimal Deployment (Gallery Only)

```bash
# Minimal deployment without sync job
kubectl create namespace vscode-offline
helm install vscode-offline ./helm/vscode-offline \
  -f ./helm/vscode-offline/examples/minimal.yaml \
  --namespace vscode-offline
```

### 3. Access the Gallery

#### Port Forward (All Deployments)
```bash
kubectl port-forward -n vscode-offline service/vscode-offline-gallery 8080:8080
```
Then visit: https://localhost:8080

#### NodePort (Development)
```bash
export NODE_PORT=$(kubectl get -n vscode-offline -o jsonpath="{.spec.ports[0].nodePort}" services vscode-offline-gallery)
export NODE_IP=$(kubectl get nodes -o jsonpath="{.items[0].status.addresses[0].address}")
echo "Visit: https://$NODE_IP:$NODE_PORT"
```

#### Ingress (Production)
Visit your configured domain (e.g., https://vscode.yourdomain.com)

## 🔧 Configuration

### Storage Configuration

```yaml
# Custom storage sizes and classes
persistence:
  enabled: true
  artifacts:
    storageClass: "fast-ssd"
    size: 200Gi  # For large extension collections
  ssl:
    storageClass: "standard"
    size: 1Gi
```

### Sync Job Configuration

```yaml
# Configure automatic sync
vscsync:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  config:
    checkRecommendedExtensions: true
    totalRecommended: 100  # Top 100 popular extensions
    updateExtensions: true
    updateBinaries: true
    platforms: "win32-x64,darwin-x64,linux-x64"  # Specific platforms only
    includeServer: true
    includeCli: true
```

### Security Configuration

```yaml
# Enable network policies
networkPolicy:
  enabled: true

# Pod security contexts
vscgallery:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
```

## 📊 Monitoring

### Check Deployment Status

```bash
# View all resources
kubectl get all -n vscode-offline

# Check pod logs
kubectl logs -n vscode-offline -l app.kubernetes.io/component=gallery
kubectl logs -n vscode-offline -l app.kubernetes.io/component=sync

# Check sync job status
kubectl get cronjob -n vscode-offline
```

### Scaling

```bash
# Manual scaling
kubectl scale deployment vscode-offline-gallery --replicas=3 -n vscode-offline

# Enable auto-scaling
helm upgrade vscode-offline ./helm/vscode-offline \
  --set autoscaling.enabled=true \
  --set autoscaling.maxReplicas=5 \
  -n vscode-offline
```

## 🔄 Maintenance

### Update Extensions

```bash
# Trigger sync job manually
kubectl create job -n vscode-offline --from=cronjob/vscode-offline-sync manual-sync-$(date +%s)
```

### Upgrade Deployment

```bash
# Upgrade to latest version
helm upgrade vscode-offline ./helm/vscode-offline -n vscode-offline

# Change configuration
helm upgrade vscode-offline ./helm/vscode-offline \
  --set vscsync.config.totalRecommended=200 \
  -n vscode-offline
```

### Backup

```bash
# Backup persistent volumes
kubectl get pvc -n vscode-offline
# Use your preferred backup solution (Velero, etc.)
```

## 🗑️ Cleanup

```bash
# Remove deployment (keeps PVCs)
helm uninstall vscode-offline -n vscode-offline

# Remove everything including storage
helm uninstall vscode-offline -n vscode-offline
kubectl delete pvc -n vscode-offline -l app.kubernetes.io/name=vscode-offline
kubectl delete namespace vscode-offline
```

## 🎯 Use Cases

### Air-Gapped Environment

```yaml
# Disable external sync, use manual artifact loading
vscsync:
  enabled: false

persistence:
  enabled: true
  artifacts:
    size: 100Gi
    # Pre-populate with existing artifacts
```

### CI/CD Integration

```yaml
# Configure for automated builds
vscsync:
  schedule: "0 */6 * * *"  # Every 6 hours
  config:
    checkRecommendedExtensions: true
    totalRecommended: 50
    platforms: "linux-x64"  # CI/CD specific platforms
```

### Multi-Region Deployment

```yaml
# Configure for specific regions
vscgallery:
  nodeSelector:
    topology.kubernetes.io/region: us-west-2
  
persistence:
  artifacts:
    storageClass: "regional-ssd"
```

## 📞 Support

- **Documentation**: [README.md](../README.md)
- **Issues**: https://github.com/SpeedyH30/vscodeoffline/issues
- **Chart Values**: `helm show values ./helm/vscode-offline`
- **Status**: `helm status vscode-offline -n vscode-offline`

## 🧪 Testing

Run the included test suite:

```bash
# Validate chart without installing
./helm/test-chart.sh

# Test different configurations
helm template test ./helm/vscode-offline -f ./helm/vscode-offline/examples/development.yaml
```