# TrendRadar 快速开始指南

## 🚀 5 分钟上手

### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/qvest-ssels/TrendRadar.git
cd TrendRadar

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .
```

### 2. 基础配置
```bash
# 编辑配置文件
nano config/config.yaml

# 关键配置项：
# - timezone: 设置您的时区 (默认: "Asia/Shanghai")
# - enable_crawler: 启用数据采集 (默认: true)
# - platforms: 配置需要监控的平台
```

### 3. 运行测试
```bash
# 验证安装
make test

# 测试所有平台连接
make test-platforms

# 测试 MCP 服务器
make test-mcp
```

## 🎯 常见使用场景

### 场景 1: 新闻趋势监控
```bash
# 启动 MCP 服务器
trendradar --transport http --port 3333

# 在 AI 助手 (如 Cherry Studio) 中配置 MCP 服务器
# 地址: http://localhost:3333
```

### 场景 2: 定时数据采集
```bash
# 配置定时任务 (crontab)
# 每小时采集一次
0 * * * * cd /path/to/TrendRadar && python main.py
```

### 场景 3: 特定平台监控
```yaml
# config/config.yaml
platforms:
  - id: "zhihu"
    name: "知乎"
  - id: "weibo"
    name: "微博"
  - id: "spiegel"
    name: "Der Spiegel"
    crawler:
      type: "rss"
      url_template: "https://www.spiegel.de/schlagzeilen/index.rss"
```

## 🔧 故障排除

### 常见问题

**Q: 测试失败怎么办？**
```bash
# 查看详细错误信息
make test-verbose

# 检查网络连接
ping newsnow.busiyi.world

# 验证配置文件
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

**Q: 时区设置不生效？**
```bash
# 检查环境变量
echo $TIMEZONE

# 或配置文件
grep timezone config/config.yaml
```

**Q: MCP 服务器无法启动？**
```bash
# 检查端口占用
lsof -i :3333

# 更换端口
trendradar --transport http --port 3334
```

### 性能优化

```yaml
# config/config.yaml 优化配置
crawler:
  request_interval: 2000  # 增加请求间隔
  use_proxy: true         # 启用代理
  default_proxy: "http://your-proxy:8080"

notification:
  push_window:
    enabled: true         # 限制推送时间
    start: "09:00"
    end: "18:00"
```

## 📊 监控和维护

### 系统状态检查
```bash
# MCP 工具调用
get_system_status()
```

### 日志查看
```bash
# 查看最近的输出
ls -la output/
tail output/*/txt/*.txt
```

### 数据清理
```bash
# 清理测试缓存
make clean

# 清理旧数据 (保留7天)
find output/ -type d -mtime +7 -exec rm -rf {} \;
```

## 🎓 进阶配置

### 多时区部署
```yaml
# 欧洲用户
app:
  timezone: "Europe/Berlin"

# 美国用户
app:
  timezone: "America/New_York"

# 亚洲用户
app:
  timezone: "Asia/Shanghai"
```

### 企业级部署
```bash
# 使用环境变量
export TIMEZONE="UTC"
export ENABLE_CRAWLER="true"
export REPORT_MODE="daily"

# HTTP 模式运行
trendradar --transport http --host 0.0.0.0 --port 3333
```

### 自定义关键词
```txt
# config/frequency_words.txt
人工智能
+机器学习
+深度学习
!广告内容
@5
```

## 📞 获取帮助

- 📖 **完整文档**: [docs/README.md](docs/README.md)
- 🐛 **问题反馈**: [GitHub Issues](https://github.com/qvest-ssels/TrendRadar/issues)
- 💬 **讨论交流**: [GitHub Discussions](https://github.com/qvest-ssels/TrendRadar/discussions)

---

**享受使用 TrendRadar！** 🎉