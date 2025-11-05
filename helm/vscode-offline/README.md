# VSCode Offline Helm Chart

This Helm chart deploys VSCode Offline - an extension gallery and binary server for offline Visual Studio Code environments.

## Features

- **VSCode Gallery**: Web-based interface for browsing and downloading VS Code extensions and installers
- **Automated Sync**: CronJob for syncing the latest extensions and binaries from Microsoft's marketplace
- **High Availability**: Support for multiple replicas, autoscaling, and pod disruption budgets
- **Security**: Network policies, pod security contexts, and SSL/TLS support
- **Flexibility**: Configurable sync schedules, platform filtering, and resource limits

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Persistent storage support (for production deployments)

## Installation

### Quick Start

```bash
# Add the repository (if published)
helm repo add vscode-offline https://your-repo.com/charts
helm repo update

# Install with default values
helm install vscode-offline vscode-offline/vscode-offline
```

### Local Installation

```bash
# Clone the repository
git clone https://github.com/SpeedyH30/vscodeoffline.git
cd vscodeoffline

# Install from local chart
helm install vscode-offline ./helm/vscode-offline
```

### Customized Installation

```bash
# Development environment
helm install vscode-offline-dev ./helm/vscode-offline -f helm/vscode-offline/examples/development.yaml

# Production environment
helm install vscode-offline-prod ./helm/vscode-offline -f helm/vscode-offline/examples/production.yaml

# Minimal deployment (gallery only)
helm install vscode-offline-minimal ./helm/vscode-offline -f helm/vscode-offline/examples/minimal.yaml
```

## Configuration

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `vscgallery.enabled` | Enable gallery service | `true` |
| `vscgallery.replicaCount` | Number of gallery replicas | `1` |
| `vscgallery.image.repository` | Gallery image repository | `ghcr.io/speedyh30/vscodeoffline/vscgallery` |
| `vscgallery.image.tag` | Gallery image tag | `latest` |
| `vscgallery.service.type` | Service type | `ClusterIP` |
| `vscgallery.ingress.enabled` | Enable ingress | `false` |
| `vscsync.enabled` | Enable sync cronjob | `true` |
| `vscsync.schedule` | Sync schedule (cron format) | `"0 2 * * *"` |
| `vscsync.config.totalRecommended` | Number of popular extensions to sync | `50` |
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.artifacts.size` | Artifacts storage size | `50Gi` |

### Storage Configuration

```yaml
persistence:
  enabled: true
  artifacts:
    storageClass: "fast-ssd"
    size: 200Gi
  ssl:
    storageClass: "standard"
    size: 1Gi
```

### Ingress Configuration

```yaml
vscgallery:
  ingress:
    enabled: true
    className: "nginx"
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
    hosts:
      - host: vscode-gallery.yourdomain.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: vscode-gallery-tls
        hosts:
          - vscode-gallery.yourdomain.com
```

### Sync Configuration

```yaml
vscsync:
  schedule: "0 2 * * *"  # Daily at 2 AM
  config:
    checkRecommendedExtensions: true
    totalRecommended: 100
    updateExtensions: true
    updateBinaries: true
    platforms: "win32-x64,darwin-x64,linux-x64"
    includeServer: true
    includeCli: true
    includeArm: false
```

## Security

### SSL/TLS Configuration

The chart automatically creates SSL certificates for HTTPS. You can provide your own:

```yaml
ssl:
  enabled: true
  createSecret: true
  certificate: |
    -----BEGIN CERTIFICATE-----
    # Your certificate here
    -----END CERTIFICATE-----
  privateKey: |
    -----BEGIN PRIVATE KEY-----
    # Your private key here
    -----END PRIVATE KEY-----
```

### Network Policies

Enable network policies for enhanced security:

```yaml
networkPolicy:
  enabled: true
  ingress:
    from:
      - namespaceSelector:
          matchLabels:
            name: allowed-namespace
  egress:
    to:
      - {}  # Allow all egress (required for sync operations)
```

## Monitoring

Enable Prometheus monitoring:

```yaml
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    namespace: monitoring
    interval: 30s
```

## Scaling

### Horizontal Pod Autoscaler

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
```

### Pod Disruption Budget

```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

## Examples

### Development Environment

```bash
helm install vscode-offline ./helm/vscode-offline \\
  --set vscgallery.service.type=NodePort \\
  --set persistence.artifacts.size=10Gi \\
  --set vscsync.config.totalRecommended=25
```

### Production Environment

```bash
helm install vscode-offline ./helm/vscode-offline \\
  --set vscgallery.replicaCount=3 \\
  --set autoscaling.enabled=true \\
  --set persistence.artifacts.size=200Gi \\
  --set vscgallery.ingress.enabled=true \\
  --set vscgallery.ingress.hosts[0].host=vscode.company.com
```

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -l app.kubernetes.io/name=vscode-offline
```

### View Logs

```bash
# Gallery service logs
kubectl logs -l app.kubernetes.io/component=gallery

# Sync job logs
kubectl logs -l app.kubernetes.io/component=sync
```

### Check Persistent Volumes

```bash
kubectl get pvc -l app.kubernetes.io/name=vscode-offline
```

### Access Gallery Service

```bash
# Port forward for local access
kubectl port-forward service/vscode-offline-gallery 8080:8080
```

## Upgrading

```bash
# Update to latest version
helm upgrade vscode-offline ./helm/vscode-offline

# Upgrade with new values
helm upgrade vscode-offline ./helm/vscode-offline -f new-values.yaml
```

## Uninstalling

```bash
helm uninstall vscode-offline

# Remove persistent volumes (if needed)
kubectl delete pvc -l app.kubernetes.io/name=vscode-offline
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with different Kubernetes versions
5. Submit a pull request

## License

This chart is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.