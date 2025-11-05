#!/bin/bash
# Helm chart testing script

set -e

CHART_PATH="./helm/vscode-offline"
RELEASE_NAME="vscode-offline-test"
NAMESPACE="vscode-offline-test"

echo "🧪 Testing VSCode Offline Helm Chart"

# Function to cleanup
cleanup() {
    echo "🧹 Cleaning up test resources..."
    helm uninstall $RELEASE_NAME -n $NAMESPACE --ignore-not-found || true
    kubectl delete namespace $NAMESPACE --ignore-not-found || true
}

# Trap cleanup on exit
trap cleanup EXIT

# Create test namespace
echo "📦 Creating test namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE || true

# Test 1: Helm lint
echo "🔍 Running Helm lint..."
helm lint $CHART_PATH

# Test 2: Helm template (dry-run)
echo "🏗️  Testing Helm template rendering..."
helm template $RELEASE_NAME $CHART_PATH --namespace $NAMESPACE > /tmp/vscode-offline-template.yaml
echo "✅ Template rendered successfully"

# Test 3: Install with minimal configuration
echo "🚀 Installing with minimal configuration..."
helm install $RELEASE_NAME $CHART_PATH \
  --namespace $NAMESPACE \
  --set persistence.enabled=false \
  --set vscsync.enabled=false \
  --set vscgallery.resources.requests.memory=64Mi \
  --set vscgallery.resources.limits.memory=128Mi \
  --wait --timeout=300s

# Test 4: Check deployment status
echo "📊 Checking deployment status..."
kubectl get all -n $NAMESPACE
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=gallery -n $NAMESPACE --timeout=120s

# Test 5: Test service connectivity
echo "🌐 Testing service connectivity..."
kubectl port-forward -n $NAMESPACE svc/vscode-offline-test-gallery 18080:8080 &
PORT_FORWARD_PID=$!
sleep 5

# Test HTTPS endpoint
if curl -k -s --connect-timeout 10 https://localhost:18080 | grep -q "Offline VSCode Gallery"; then
    echo "✅ Gallery service is responding correctly"
else
    echo "❌ Gallery service test failed"
    exit 1
fi

# Kill port-forward
kill $PORT_FORWARD_PID || true

# Test 6: Upgrade test
echo "🔄 Testing Helm upgrade..."
helm upgrade $RELEASE_NAME $CHART_PATH \
  --namespace $NAMESPACE \
  --set persistence.enabled=false \
  --set vscsync.enabled=false \
  --set vscgallery.replicaCount=1 \
  --wait --timeout=300s

# Test 7: Test with different values files
echo "🧪 Testing with example configurations..."

# Test minimal example
helm template $RELEASE_NAME $CHART_PATH \
  -f $CHART_PATH/examples/minimal.yaml \
  --namespace $NAMESPACE > /tmp/minimal-template.yaml
echo "✅ Minimal configuration template OK"

# Test development example
helm template $RELEASE_NAME $CHART_PATH \
  -f $CHART_PATH/examples/development.yaml \
  --namespace $NAMESPACE > /tmp/dev-template.yaml
echo "✅ Development configuration template OK"

# Test production example (without actually deploying)
helm template $RELEASE_NAME $CHART_PATH \
  -f $CHART_PATH/examples/production.yaml \
  --namespace $NAMESPACE > /tmp/prod-template.yaml
echo "✅ Production configuration template OK"

echo ""
echo "🎉 All tests passed! VSCode Offline Helm chart is ready for deployment."
echo ""
echo "📋 Test Summary:"
echo "   ✅ Helm lint passed"
echo "   ✅ Template rendering works"
echo "   ✅ Installation successful"
echo "   ✅ Pod readiness check passed"
echo "   ✅ Service connectivity verified"
echo "   ✅ Helm upgrade works"
echo "   ✅ Example configurations valid"
echo ""
echo "🚀 To deploy in your cluster:"
echo "   helm install vscode-offline $CHART_PATH"
echo ""
echo "📖 For more options, see:"
echo "   cat $CHART_PATH/README.md"