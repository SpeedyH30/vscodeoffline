# VSCode Offline - Build, Docker, and Helm Chart Management

.PHONY: help build docker podman run helm-* docker-build docker-push

# Original build targets
build: ## Install Python dependencies
	pip install -r vscoffline/vscsync/requirements.txt
	pip install -r vscoffline/vscgallery/requirements.txt

docker: ## Build with docker-compose
	docker-compose build

podman: ## Build with podman-compose
	podman-compose build

run: ## Run with docker-compose
	docker-compose up --build -d

# Docker registry targets
docker-build: ## Build Docker images for registry
	docker build -t ghcr.io/speedyh30/vscodeoffline/vscgallery:latest ./vscoffline/vscgallery/
	docker build -t ghcr.io/speedyh30/vscodeoffline/vscsync:latest ./vscoffline/vscsync/

docker-push: ## Push Docker images to registry
	docker push ghcr.io/speedyh30/vscodeoffline/vscgallery:latest
	docker push ghcr.io/speedyh30/vscodeoffline/vscsync:latest

# Helm Chart Management
CHART_NAME := vscode-offline
CHART_PATH := ./helm/$(CHART_NAME)
RELEASE_NAME := vscode-offline
NAMESPACE := vscode-offline

helm-lint: ## Lint the Helm chart
	@echo "🔍 Linting Helm chart..."
	helm lint $(CHART_PATH)

helm-template: ## Generate Kubernetes manifests from the chart
	@echo "🏗️  Generating templates..."
	helm template $(RELEASE_NAME) $(CHART_PATH) \
		--namespace $(NAMESPACE) \
		--output-dir ./output

helm-install: ## Install the chart with default values
	@echo "🚀 Installing VSCode Offline..."
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm install $(RELEASE_NAME) $(CHART_PATH) \
		--namespace $(NAMESPACE) \
		--wait --timeout=600s

helm-install-dev: ## Install with development configuration
	@echo "🚀 Installing VSCode Offline (development)..."
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm install $(RELEASE_NAME) $(CHART_PATH) \
		-f $(CHART_PATH)/examples/development.yaml \
		--namespace $(NAMESPACE) \
		--wait --timeout=600s

helm-upgrade: ## Upgrade the existing release
	@echo "🔄 Upgrading VSCode Offline..."
	helm upgrade $(RELEASE_NAME) $(CHART_PATH) \
		--namespace $(NAMESPACE) \
		--wait --timeout=600s

helm-uninstall: ## Uninstall the release
	@echo "🗑️  Uninstalling VSCode Offline..."
	helm uninstall $(RELEASE_NAME) --namespace $(NAMESPACE)

helm-test: ## Run chart tests
	@echo "🧪 Running Helm chart tests..."
	./helm/test-chart.sh

helm-package: ## Package the Helm chart
	@echo "📦 Packaging Helm chart..."
	mkdir -p ./helm/packages
	helm package $(CHART_PATH) --destination ./helm/packages/

helm-port-forward: ## Port forward to access the gallery locally
	@echo "🌐 Port forwarding to gallery service..."
	@echo "Access at: https://localhost:8080"
	kubectl port-forward -n $(NAMESPACE) service/$(RELEASE_NAME)-gallery 8080:8080

help: ## Show this help message
	@echo "VSCode Offline - Build, Docker, and Helm Management"
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
