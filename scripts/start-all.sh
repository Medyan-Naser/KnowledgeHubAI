#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="rag-cluster"
NAMESPACE="enterprise-rag"
HELM_RELEASE="enterprise-rag"
FRONTEND_PORT=5173
BACKEND_PORT=30000
TEMPORAL_PORT=30088
MLFLOW_PORT=30500

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Enterprise RAG - Complete Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Function to wait for deployment
wait_for_deployment() {
    local namespace=$1
    local deployment=$2
    local timeout=${3:-300}
    
    echo -e "${YELLOW}Waiting for deployment ${deployment} to be ready...${NC}"
    kubectl wait --for=condition=available --timeout=${timeout}s \
        deployment/${deployment} -n ${namespace} 2>/dev/null || true
}

# Function to wait for pod
wait_for_pod() {
    local namespace=$1
    local label=$2
    local timeout=${3:-300}
    
    echo -e "${YELLOW}Waiting for pod with label ${label} to be ready...${NC}"
    kubectl wait --for=condition=ready --timeout=${timeout}s \
        pod -l ${label} -n ${namespace} 2>/dev/null || true
}

# Step 1: Configure Ollama
echo -e "\n${BLUE}[1/8] Configuring Ollama...${NC}"
if systemctl is-active --quiet ollama; then
    print_status "Ollama service is running"
else
    print_info "Starting Ollama service..."
    sudo systemctl stop ollama 2>/dev/null || true
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    echo -e '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"' | sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null
    sudo systemctl daemon-reload
    sudo systemctl start ollama
    sleep 3
    print_status "Ollama configured and started"
fi

# Step 2: Pull AI Models
echo -e "\n${BLUE}[2/8] Pulling AI Models...${NC}"
if ollama list | grep -q "llama3"; then
    print_status "llama3 model already available"
else
    print_info "Pulling llama3 model (this may take a while)..."
    ollama pull llama3
    print_status "llama3 model pulled"
fi

if ollama list | grep -q "nomic-embed-text"; then
    print_status "nomic-embed-text model already available"
else
    print_info "Pulling nomic-embed-text model..."
    ollama pull nomic-embed-text
    print_status "nomic-embed-text model pulled"
fi

# Step 3: Start Docker Services
echo -e "\n${BLUE}[3/8] Starting Docker Services (PostgreSQL, Redis, Temporal)...${NC}"
cd /home/medy/projects/knowledgeHubAI
docker compose up -d postgres redis temporal temporal-ui mlflow
sleep 5
print_status "Docker services started"

# Step 4: Create/Verify Kind Cluster
echo -e "\n${BLUE}[4/8] Setting up Kubernetes Cluster...${NC}"
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    print_status "Kind cluster '${CLUSTER_NAME}' already exists"
else
    print_info "Creating Kind cluster '${CLUSTER_NAME}'..."
    kind create cluster --name ${CLUSTER_NAME} --config k8s/kind-config.yaml
    print_status "Kind cluster created"
fi

# Step 5: Build and Load Docker Images
echo -e "\n${BLUE}[5/8] Building and Loading Docker Images...${NC}"
print_info "Building backend image..."
docker build -f docker/backend.Dockerfile -t enterprise-rag-backend:latest . -q
print_status "Backend image built"

print_info "Building worker image..."
docker build -f docker/worker.Dockerfile -t enterprise-rag-worker:latest . -q
print_status "Worker image built"

print_info "Loading images into Kind cluster..."
kind load docker-image enterprise-rag-backend:latest --name ${CLUSTER_NAME}
kind load docker-image enterprise-rag-worker:latest --name ${CLUSTER_NAME}
print_status "Images loaded into cluster"

# Step 6: Deploy with Helm
echo -e "\n${BLUE}[6/8] Deploying with Helm...${NC}"

# Create namespace if it doesn't exist
kubectl create namespace ${NAMESPACE} 2>/dev/null || true

# Check if release exists
if helm list -n ${NAMESPACE} | grep -q ${HELM_RELEASE}; then
    print_info "Upgrading existing Helm release..."
    helm upgrade ${HELM_RELEASE} ./helm/enterprise-rag \
        -f ./helm/enterprise-rag/values-local.yaml \
        -n ${NAMESPACE} \
        --wait --timeout 10m
    print_status "Helm release upgraded"
else
    print_info "Installing Helm release..."
    helm install ${HELM_RELEASE} ./helm/enterprise-rag \
        -f ./helm/enterprise-rag/values-local.yaml \
        -n ${NAMESPACE} \
        --wait --timeout 10m
    print_status "Helm release installed"
fi

# Step 7: Wait for all pods to be ready
echo -e "\n${BLUE}[7/8] Waiting for all services to be ready...${NC}"
print_info "This may take a few minutes..."

# Wait for backend
wait_for_deployment ${NAMESPACE} enterprise-rag-backend

# Wait for worker
wait_for_deployment ${NAMESPACE} enterprise-rag-worker

# Wait for PostgreSQL
wait_for_pod ${NAMESPACE} "app.kubernetes.io/name=postgresql"

# Wait for Redis
wait_for_pod ${NAMESPACE} "app.kubernetes.io/name=redis"

print_status "All Kubernetes services are ready"

# Step 8: Run Database Migrations
echo -e "\n${BLUE}[8/8] Running Database Migrations...${NC}"
if [ ! -d ".venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

print_info "Running Alembic migrations..."
alembic upgrade head
print_status "Database migrations completed"

# Step 9: Start Frontend
echo -e "\n${BLUE}[9/9] Starting Frontend...${NC}"
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_info "Installing frontend dependencies..."
    npm install --silent
fi

# Kill any existing frontend process
pkill -f "vite" 2>/dev/null || true
sleep 1

# Start frontend in background
print_info "Starting frontend development server..."
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to be ready
sleep 5

if ps -p $FRONTEND_PID > /dev/null; then
    print_status "Frontend started successfully"
else
    print_error "Frontend failed to start. Check /tmp/frontend.log for details"
fi

cd ..

# Display URLs and Status
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  🚀 All Services Started Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo -e "  ${GREEN}Frontend:${NC}      http://localhost:${FRONTEND_PORT}"
echo -e "  ${GREEN}Backend API:${NC}   http://localhost:${BACKEND_PORT}/docs"
echo -e "  ${GREEN}Temporal UI:${NC}   http://localhost:${TEMPORAL_PORT}"
echo -e "  ${GREEN}MLflow UI:${NC}     http://localhost:${MLFLOW_PORT}"
echo ""
echo -e "${BLUE}Quick Commands:${NC}"
echo -e "  ${YELLOW}Check health:${NC}     ./scripts/check-health.sh"
echo -e "  ${YELLOW}Run E2E test:${NC}     ./scripts/k8s-test-e2e.sh"
echo -e "  ${YELLOW}View logs:${NC}        kubectl logs -f -n ${NAMESPACE} -l app=enterprise-rag-backend"
echo -e "  ${YELLOW}Stop all:${NC}         ./scripts/stop-all.sh"
echo ""
echo -e "${BLUE}Kubernetes Resources:${NC}"
kubectl get pods -n ${NAMESPACE}
echo ""
kubectl get services -n ${NAMESPACE}
echo ""

# Save PIDs for cleanup
echo $FRONTEND_PID > /tmp/enterprise-rag-frontend.pid

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Ready to use! Open http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${GREEN}========================================${NC}"
