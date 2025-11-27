# TrendRadar - 新闻热点聚合与分析工具

[![Version](https://img.shields.io/badge/version-3.3.0-blue.svg)](https://github.com/qvest-ssels/TrendRadar)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

**TrendRadar** 是一个强大的新闻热点聚合与分析工具，支持多平台数据采集、智能趋势分析和AI助手集成。通过 MCP (Model Context Protocol) 协议，为 AI 助手提供全面的新闻分析能力。

## 🌟 核心特性

### 📊 多平台新闻聚合
- **12个主流平台**：支持今日头条、百度、微博、知乎、B站、澎湃新闻等中文平台
- **国际新闻支持**：集成 Der Spiegel (德国之声) RSS 源
- **智能去重**：基于内容相似度自动去重
- **实时更新**：支持定时爬取和手动触发

### 🧠 智能分析能力
- **趋势分析**：热点话题生命周期追踪
- **情感分析**：新闻内容情感倾向识别
- **关键词共现**：发现相关话题关联
- **预测分析**：基于历史数据预测趋势发展

### 🤖 AI 助手集成
- **MCP 协议支持**：兼容 FastMCP 2.0 标准
- **13个专业工具**：涵盖数据查询、分析、搜索等功能
- **多传输模式**：支持 stdio 和 HTTP 模式
- **生产就绪**：企业级稳定性和性能

### 🌍 国际化支持
- **多时区配置**：支持全球任何时区 (UTC, Europe/Berlin, Asia/Shanghai 等)
- **多语言内容**：中文、德文等多语言新闻支持
- **灵活配置**：环境变量和配置文件双重配置

## 🚀 快速开始

### 环境要求
- Python 3.10+
- pip (包管理器)

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/qvest-ssels/TrendRadar.git
cd TrendRadar
```

2. **创建虚拟环境**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows
```

3. **安装依赖**
```bash
pip install -e .
```

4. **配置设置**
```bash
# 复制并编辑配置文件
cp config/config.yaml config/config.yaml.backup
# 编辑 config/config.yaml 根据需要调整配置
```

### 基本使用

#### 命令行模式
```bash
# 运行新闻聚合
python main.py

# 指定配置文件
python main.py --config /path/to/config.yaml
```

#### MCP 服务器模式
```bash
# stdio 模式 (推荐用于 AI 助手集成)
python -m mcp_server.server

# HTTP 模式 (生产环境)
trendradar --transport http --port 3333

# 指定项目目录
trendradar --project-root /path/to/project
```

## 📖 配置指南

### 核心配置 (config/config.yaml)

```yaml
app:
  timezone: "Europe/Berlin"  # 时区设置，支持 pytz 时区名称
  version_check_url: "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/version"

crawler:
  enable_crawler: true       # 是否启用爬虫
  request_interval: 1000     # 请求间隔(毫秒)
  use_proxy: false          # 代理设置

platforms:
  - id: "zhihu"
    name: "知乎"
  - id: "weibo"
    name: "微博"
  - id: "spiegel"
    name: "Der Spiegel — Schlagzeilen"
    crawler:
      type: "rss"
      url_template: "https://www.spiegel.de/schlagzeilen/index.rss"
```

### 时区配置

TrendRadar 支持全球任何时区：

```yaml
app:
  timezone: "UTC"           # 协调世界时
  # timezone: "Europe/Berlin"  # 柏林时间 (UTC+1)
  # timezone: "Asia/Shanghai"  # 上海时间 (UTC+8)
  # timezone: "America/New_York"  # 纽约时间 (UTC-5)
```

### 环境变量覆盖

```bash
export TIMEZONE="Europe/London"
export ENABLE_CRAWLER="true"
export REPORT_MODE="daily"
```

## 🧪 测试验证

TrendRadar 提供全面的测试套件，确保系统稳定运行。

### 运行测试

```bash
# 运行所有单元测试
make test

# 详细测试输出
make test-verbose

# 测试所有新闻平台
make test-platforms

# 测试 Spiegel RSS 源
make test-spiegel

# 测试 MCP 服务器
make test-mcp

# 清理测试缓存
make clean
```

### 测试覆盖

- ✅ **单元测试**: 核心功能逻辑验证
- ✅ **集成测试**: 平台数据获取验证
- ✅ **RSS 测试**: Spiegel.de 源测试
- ✅ **MCP 测试**: AI 助手集成验证
- ✅ **端到端测试**: 完整工作流验证

## 🔧 MCP 工具详解

TrendRadar 通过 MCP 协议提供 13 个专业工具：

### 日期解析工具
- `resolve_date_range` - 自然语言日期解析

### 基础数据查询 (P0 核心)
- `get_latest_news` - 获取最新新闻
- `get_news_by_date` - 按日期查询新闻
- `get_trending_topics` - 获取趋势话题

### 智能检索工具
- `search_news` - 统一新闻搜索
- `search_related_news_history` - 历史相关新闻检索

### 高级数据分析
- `analyze_topic_trend` - 话题趋势分析
- `analyze_data_insights` - 数据洞察分析
- `analyze_sentiment` - 情感倾向分析
- `find_similar_news` - 相似新闻查找
- `generate_summary_report` - 摘要报告生成

### 配置与系统管理
- `get_current_config` - 获取系统配置
- `get_system_status` - 获取系统状态
- `trigger_crawl` - 手动触发爬取

## 📊 数据分析功能

### 趋势分析
```python
# 分析话题趋势
result = analyze_topic_trend(
    topic="人工智能",
    days=7,
    include_prediction=True
)
```

### 情感分析
```python
# 分析新闻情感
result = analyze_sentiment(
    platform="zhihu",
    date_range="2025-11-20 to 2025-11-27"
)
```

### 智能搜索
```python
# 统一搜索接口
result = search_news(
    query="ChatGPT",
    platforms=["zhihu", "weibo"],
    date_range="last_7_days"
)
```

## 🌐 平台支持

### 中文平台
- **今日头条** (toutiao) - 综合新闻聚合
- **百度热搜** (baidu) - 百度搜索热点
- **微博** (weibo) - 社交媒体热点
- **知乎** (zhihu) - 问答社区热点
- **B站** (bilibili-hot-search) - 视频平台热点
- **财联社** (cls-hot) - 金融新闻热点
- **凤凰网** (ifeng) - 传统媒体热点
- **贴吧** (tieba) - 论坛社区热点
- **抖音** (douyin) - 短视频平台热点
- **澎湃新闻** (thepaper) - 深度新闻分析
- **华尔街见闻** (wallstreetcn-hot) - 财经资讯

### 国际平台
- **Der Spiegel** (spiegel) - 德国权威媒体

## 🔒 安全与隐私

- **无数据存储**: 默认不存储用户数据
- **本地处理**: 所有分析在本地完成
- **可配置代理**: 支持代理服务器
- **请求限流**: 内置请求间隔控制

## 📈 性能优化

- **缓存机制**: 智能缓存减少重复请求
- **异步处理**: 支持并发数据获取
- **内存优化**: 高效的数据结构和算法
- **监控告警**: 系统状态实时监控

## 🤝 贡献指南

### 开发环境设置
```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
make test

# 代码格式化
black .
isort .
```

### 添加新平台
1. 在 `config/config.yaml` 中添加平台配置
2. 实现对应的数据获取逻辑
3. 添加平台测试用例
4. 更新文档

### 添加新功能
1. 遵循现有代码结构
2. 添加相应的单元测试
3. 更新 MCP 工具接口
4. 更新文档

## 📝 更新日志

### v3.3.0 (2025-11-27)
- ✨ 添加 Der Spiegel RSS 源支持
- 🌍 实现可配置时区系统
- 🧪 重构测试套件，添加全面集成测试
- 🔧 优化 MCP 服务器性能
- 📚 完善文档和使用指南

### v3.2.0
- 🚀 升级至 FastMCP 2.0
- 📊 增强数据分析能力
- 🔍 改进搜索功能
- 🐛 修复多平台兼容性问题

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙋‍♂️ 支持与反馈

- 📧 **邮箱**: sels@tnwx.net
- 🐛 **问题反馈**: [GitHub Issues](https://github.com/qvest-ssels/TrendRadar/issues)
- 📖 **文档**: [完整文档](https://github.com/qvest-ssels/TrendRadar/wiki)

## 🙏 致谢

感谢所有为 TrendRadar 贡献代码和建议的开发者！

---

**TrendRadar** - 让 AI 助手更好地理解新闻趋势！ 🤖📰