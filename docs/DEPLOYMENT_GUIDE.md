# TrendRadar 部署指南

## 📦 部署选项

TrendRadar 支持多种部署方式，从单机开发环境到企业级分布式部署。

## 🖥️ 本地开发部署

### 环境要求
- Python 3.10+
- 4GB RAM (推荐8GB+)
- 2GB 磁盘空间
- macOS/Linux/Windows

### 快速启动
```bash
# 1. 克隆项目
git clone <repository-url>
cd TrendRadar

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
cp config/config.yaml config/config.local.yaml
# 编辑 config.local.yaml 进行本地配置

# 4. 运行应用
python main.py
```

### 开发环境配置
```yaml
# config/config.local.yaml
app:
  timezone: "Asia/Shanghai"  # 本地时区
  debug: true
  log_level: "DEBUG"

platforms:
  # 只启用少量平台进行测试
  - id: "zhihu"
    enabled: true
  - id: "weibo"
    enabled: true
```

## 🐳 Docker 部署

### 单容器部署
```bash
# 构建镜像
docker build -f docker/Dockerfile -t trendradar:latest .

# 运行容器
docker run -d \
  --name trendradar \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/output:/app/output \
  trendradar:latest
```

### Docker Compose 部署
```bash
# 使用开发环境配置
docker-compose -f docker/docker-compose.yml up -d

# 使用生产环境配置
docker-compose -f docker/docker-compose-build.yml up -d
```

### Docker Compose 配置
```yaml
# docker/docker-compose.yml
version: '3.8'
services:
  trendradar:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - ./output:/app/output
      - ./logs:/app/logs
    environment:
      - TREND_RADAR_CONFIG=/app/config/config.yaml
    restart: unless-stopped
```

## ☁️ 云服务器部署

### AWS EC2 部署
```bash
# 1. 创建 EC2 实例 (t3.medium 推荐)
aws ec2 run-instances \
  --image-id ami-0abcdef1234567890 \
  --instance-type t3.medium \
  --key-name your-key-pair

# 2. 连接实例并安装依赖
ssh -i your-key.pem ec2-user@your-instance-ip
sudo yum update -y
sudo yum install python3.10 git -y

# 3. 部署应用
git clone <repository-url>
cd TrendRadar
pip3 install -r requirements.txt

# 4. 配置 systemd 服务
sudo cp deploy/trendradar.service /etc/systemd/system/
sudo systemctl enable trendradar
sudo systemctl start trendradar
```

### Google Cloud Run
```yaml
# cloud-run.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: trendradar
spec:
  template:
    spec:
      containers:
      - image: gcr.io/your-project/trendradar:latest
        ports:
        - containerPort: 8000
        env:
        - name: TREND_RADAR_CONFIG
          value: "/app/config/config.yaml"
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Azure Container Instances
```bash
# 使用 Azure CLI
az container create \
  --resource-group your-rg \
  --name trendradar \
  --image your-registry/trendradar:latest \
  --cpu 1 \
  --memory 1 \
  --ports 8000 \
  --environment-variables TREND_RADAR_CONFIG=/app/config/config.yaml \
  --vnet your-vnet \
  --subnet your-subnet
```

## 🏢 企业级部署

### Kubernetes 部署
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trendradar
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trendradar
  template:
    metadata:
      labels:
        app: trendradar
    spec:
      containers:
      - name: trendradar
        image: your-registry/trendradar:latest
        ports:
        - containerPort: 8000
        env:
        - name: TREND_RADAR_CONFIG
          valueFrom:
            configMapKeyRef:
              name: trendradar-config
              key: config.yaml
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 负载均衡配置
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: trendradar-service
spec:
  selector:
    app: trendradar
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 持久化存储
```yaml
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: trendradar-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
```

## 🔧 配置管理

### 环境变量配置
```bash
# 生产环境变量
export TREND_RADAR_CONFIG=/etc/trendradar/config.yaml
export TREND_RADAR_LOG_LEVEL=INFO
export TREND_RADAR_TIMEZONE=UTC
export TREND_RADAR_CACHE_SIZE=1000
```

### 配置文件模板
```yaml
# config/config.prod.yaml
app:
  timezone: "UTC"
  debug: false
  log_level: "INFO"
  cache:
    max_size: 10000
    ttl_hours: 24

platforms:
  # 启用所有平台
  - id: "zhihu"
    enabled: true
    rate_limit: 60
  - id: "weibo"
    enabled: true
    rate_limit: 30
  # ... 其他平台配置

database:
  type: "postgresql"
  host: "trendradar-db"
  port: 5432
  database: "trendradar"
  username: "${DB_USER}"
  password: "${DB_PASSWORD}"
```

## 📊 监控和日志

### 健康检查端点
```
GET /health  - 应用健康状态
GET /ready   - 就绪状态
GET /metrics - Prometheus 指标
```

### 日志配置
```yaml
logging:
  level: "INFO"
  format: "json"
  outputs:
    - type: "file"
      path: "/var/log/trendradar/app.log"
    - type: "stdout"
  rotation:
    max_size: "100MB"
    max_age: "30d"
    max_backups: 10
```

### 监控指标
- 请求响应时间
- 错误率
- 平台爬取成功率
- 缓存命中率
- 系统资源使用率

## 🔒 安全配置

### HTTPS 配置
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 防火墙配置
```bash
# UFW 配置
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

### 密钥管理
```yaml
secrets:
  database:
    password: "${DB_PASSWORD}"
  api_keys:
    openai: "${OPENAI_API_KEY}"
    twitter: "${TWITTER_BEARER_TOKEN}"
```

## 🚀 性能优化

### 生产环境优化
```yaml
app:
  workers: 4
  max_requests: 1000
  max_requests_jitter: 50

cache:
  redis_url: "redis://trendradar-redis:6379"
  ttl_hours: 24

database:
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
```

### 扩展策略
- **水平扩展**: 使用 Kubernetes HPA 根据 CPU/内存自动扩展
- **垂直扩展**: 增加实例规格 (CPU/内存)
- **缓存优化**: 使用 Redis 集群
- **数据库优化**: 读写分离，分库分表

## 🔄 更新部署

### 滚动更新
```bash
# Kubernetes 滚动更新
kubectl set image deployment/trendradar trendradar=your-registry/trendradar:v2.0.0
kubectl rollout status deployment/trendradar
```

### 蓝绿部署
```bash
# 创建新版本
kubectl apply -f k8s/deployment-v2.yaml
kubectl apply -f k8s/service-blue.yaml

# 切换流量
kubectl patch service trendradar-service -p '{"spec":{"selector":{"version":"v2.0.0"}}}'

# 清理旧版本
kubectl delete deployment trendradar-v1
```

---

**部署版本**: 1.0.0 | **最后更新**: 2025-11-27