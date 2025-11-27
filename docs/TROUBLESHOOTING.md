# TrendRadar 故障排除指南

## 🔍 诊断工具

### 快速健康检查
```bash
# 运行完整测试套件
make test-platforms

# 检查系统状态
make test-mcp

# 验证配置文件
python -c "
import yaml
config = yaml.safe_load(open('config/config.yaml'))
print('✅ 配置文件有效')
print(f'时区: {config[\"app\"][\"timezone\"]}')
print(f'平台数量: {len(config[\"platforms\"])}')
"
```

### 网络连接测试
```bash
# 测试主要数据源
curl -I https://newsnow.busiyi.world/api/s?id=zhihu&latest
curl -I https://www.spiegel.de/schlagzeilen/index.rss

# DNS 解析测试
nslookup newsnow.busiyi.world
nslookup spiegel.de
```

## 🚨 常见问题及解决方案

### 1. 安装问题

**问题**: `ModuleNotFoundError` 或依赖安装失败
```bash
# 解决方案：重新创建虚拟环境
deactivate
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

**问题**: Python 版本不兼容
```bash
# 检查 Python 版本
python --version  # 需要 3.10+

# 使用特定 Python 版本
python3.11 -m venv .venv
```

### 2. 配置问题

**问题**: 时区设置不生效
```yaml
# config/config.yaml
app:
  timezone: "Europe/Berlin"  # 检查拼写
```
```bash
# 环境变量覆盖
export TIMEZONE="Europe/Berlin"
python main.py
```

**问题**: 平台配置无效
```bash
# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# 检查平台 ID
grep -A 5 "platforms:" config/config.yaml
```

### 3. 网络问题

**问题**: 请求超时或连接失败
```yaml
# config/config.yaml - 增加超时设置
crawler:
  request_interval: 2000  # 增加间隔
  use_proxy: true
  default_proxy: "http://127.0.0.1:8080"
```

**问题**: SSL 证书错误
```bash
# 禁用 SSL 验证 (仅测试用)
export REQUESTS_CA_BUNDLE=""
# 或更新证书
pip install --upgrade certifi
```

### 4. MCP 服务器问题

**问题**: 服务器启动失败
```bash
# 检查端口占用
lsof -i :3333

# 使用不同端口
trendradar --transport http --port 3334
```

**问题**: AI 助手无法连接
```bash
# 测试服务器响应
curl http://localhost:3333/mcp

# 检查防火墙
sudo ufw status
sudo ufw allow 3333
```

### 5. 数据问题

**问题**: 没有数据输出
```bash
# 检查输出目录
ls -la output/

# 手动运行测试
python -c "
from main import DataFetcher
f = DataFetcher()
result = f.fetch_data({'id': 'zhihu', 'name': '知乎'})
print('Result:', result[:100])
"
```

**问题**: 数据格式错误
```bash
# 查看原始响应
python -c "
import requests
response = requests.get('https://newsnow.busiyi.world/api/s?id=zhihu&latest')
print('Status:', response.status_code)
print('Content:', response.text[:500])
"
```

## 📊 性能问题

### 内存使用过高
```yaml
# config/config.yaml
report:
  max_news_per_keyword: 5  # 限制每关键词新闻数
```

### 请求过于频繁
```yaml
# config/config.yaml
crawler:
  request_interval: 3000  # 增加到 3 秒
```

### 存储空间不足
```bash
# 清理旧数据
find output/ -type f -mtime +30 -delete

# 检查磁盘使用
df -h
du -sh output/
```

## 🔧 高级调试

### 启用详细日志
```python
# 在 main.py 中添加
import logging
logging.basicConfig(level=logging.DEBUG)

# 或使用环境变量
export PYTHONPATH=/path/to/TrendRadar
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from main import DataFetcher
# 调试代码
"
```

### 数据库调试
```bash
# 检查缓存文件
find . -name "*.db" -o -name "*.cache"

# 重置缓存
rm -rf __pycache__/
rm -rf .pytest_cache/
make clean
```

### 网络调试
```bash
# 使用代理调试
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080

# 抓包分析
tcpdump -i any port 80 or port 443 -w capture.pcap
```

## 🚑 紧急恢复

### 完全重置
```bash
# 备份配置
cp config/config.yaml config/config.yaml.backup

# 清理所有生成文件
make clean
rm -rf output/
rm -rf __pycache__/
rm -rf .venv/

# 重新安装
git checkout .
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp config/config.yaml.backup config/config.yaml
```

### 从备份恢复
```bash
# 如果有数据库备份
cp backup/output.tar.gz .
tar -xzf output.tar.gz

# 恢复配置
cp config/config.yaml.backup config/config.yaml
```

## 📞 获取支持

### 诊断信息收集
```bash
# 生成系统报告
python -c "
import sys, platform
print('Python:', sys.version)
print('Platform:', platform.platform())
print('Working dir:', os.getcwd())

import yaml
try:
    config = yaml.safe_load(open('config/config.yaml'))
    print('Config loaded: ✅')
except Exception as e:
    print('Config error:', e)
"
```

### 社区支持
- 🐛 **GitHub Issues**: [报告问题](https://github.com/qvest-ssels/TrendRadar/issues)
- 💬 **Discussions**: [讨论交流](https://github.com/qvest-ssels/TrendRadar/discussions)
- 📧 **邮件支持**: sels@tnwx.net

### 商业支持
对于企业用户，我们提供：
- 🔧 专业技术支持
- 🚀 性能优化服务
- 📚 定制培训
- 🛠️ 定制开发

---

**记住**: 大多数问题都可以通过 `make test-platforms` 快速诊断！ 🔍