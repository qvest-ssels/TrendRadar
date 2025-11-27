# TrendRadar MCP API 参考

## 📋 概述

TrendRadar 通过 MCP (Model Context Protocol) 提供 13 个专业工具，涵盖新闻数据查询、分析、搜索和系统管理功能。

## 🛠️ 工具分类

### 1. 日期解析工具 (1个)

#### `resolve_date_range`
将自然语言日期表达式解析为标准日期范围格式。

**参数:**
- `expression` (str): 自然语言日期表达式，如 "今天"、"本周"、"最近7天"

**返回值:**
- `str`: 标准化的日期范围字符串

**示例:**
```python
# 输入: "本周"
# 输出: "2025-11-25 to 2025-12-01"

# 输入: "昨天"
# 输出: "2025-11-26 to 2025-11-26"
```

### 2. 基础数据查询工具 (3个)

#### `get_latest_news`
获取最新一批爬取的新闻数据。

**参数:**
- `platforms` (Optional[List[str]]): 平台ID列表，None表示所有平台
- `limit` (int): 返回条数限制，默认50
- `include_url` (bool): 是否包含URL链接，默认False

**返回值:**
- `List[Dict]`: 新闻列表，每个项目包含 title, platform, platform_name, rank, timestamp

**示例:**
```python
result = get_latest_news(platforms=['zhihu', 'weibo'], limit=10)
# 返回最近10条知乎和微博新闻
```

#### `get_news_by_date`
按日期查询新闻，支持自然语言日期表达式。

**参数:**
- `date_expression` (str): 日期表达式，如 "今天"、"2025-11-27"
- `platforms` (Optional[List[str]]): 平台过滤
- `limit` (int): 返回条数限制

**返回值:**
- `List[Dict]`: 指定日期的新闻列表

#### `get_trending_topics`
获取当前趋势话题，按热度排序。

**参数:**
- `limit` (int): 返回话题数量，默认20
- `platforms` (Optional[List[str]]): 平台过滤

**返回值:**
- `List[Dict]`: 趋势话题列表，包含话题名称、热度分数等

### 3. 智能检索工具 (2个)

#### `search_news`
统一新闻搜索接口，支持关键词、模糊搜索和实体识别。

**参数:**
- `query` (str): 搜索关键词
- `platforms` (Optional[List[str]]): 搜索平台范围
- `date_range` (Optional[str]): 日期范围
- `limit` (int): 返回条数限制

**返回值:**
- `List[Dict]`: 匹配的新闻列表

**搜索语法:**
```
# 关键词搜索
"人工智能"

# 模糊搜索
"AI OR 人工智能"

# 实体搜索
"entity:OpenAI"

# 时间范围
"机器学习 date:2025-11"
```

#### `search_related_news_history`
检索历史上相关新闻，支持话题演变追踪。

**参数:**
- `topic` (str): 主题关键词
- `days` (int): 历史天数，默认30
- `platforms` (Optional[List[str]]): 平台过滤

**返回值:**
- `Dict`: 包含时间线、相关话题、热度变化等

### 4. 高级数据分析工具 (5个)

#### `analyze_topic_trend`
统一话题趋势分析，包含热度、生命周期、爆火预测。

**参数:**
- `topic` (str): 分析话题
- `days` (int): 分析天数，默认7
- `include_prediction` (bool): 是否包含趋势预测，默认True
- `platforms` (Optional[List[str]]): 平台范围

**返回值:**
- `Dict`: 包含趋势图表、预测数据、关键指标等

**分析指标:**
- 热度趋势曲线
- 生命周期阶段 (萌芽/成长/巅峰/衰退)
- 平台分布
- 关键词共现网络
- 情感倾向变化

#### `analyze_data_insights`
统一数据洞察分析，平台对比和活跃度分析。

**参数:**
- `date_range` (Optional[str]): 分析时间范围
- `platforms` (Optional[List[str]]): 平台范围
- `insight_type` (str): 洞察类型 ("platform_comparison", "activity_analysis", "keyword_network")

**返回值:**
- `Dict`: 包含对比图表、统计数据、异常检测等

#### `analyze_sentiment`
情感倾向分析，识别新闻内容情感。

**参数:**
- `platform` (Optional[str]): 指定平台
- `date_range` (Optional[str]): 时间范围
- `topic` (Optional[str]): 主题过滤

**返回值:**
- `Dict`: 情感分布统计，正面/负面/中性比例

#### `find_similar_news`
相似新闻查找，基于内容相似度。

**参数:**
- `news_id` (str): 基准新闻ID
- `limit` (int): 返回相似新闻数量，默认10
- `threshold` (float): 相似度阈值，默认0.7

**返回值:**
- `List[Dict]`: 相似新闻列表，按相似度排序

#### `generate_summary_report`
生成每日/每周摘要报告。

**参数:**
- `report_type` (str): 报告类型 ("daily", "weekly", "monthly")
- `date` (Optional[str]): 报告日期
- `platforms` (Optional[List[str]]): 平台范围

**返回值:**
- `str`: 格式化的摘要报告 (Markdown)

### 5. 配置与系统管理工具 (2个)

#### `get_current_config`
获取当前系统配置信息。

**参数:** 无

**返回值:**
- `Dict`: 当前配置文件内容

#### `get_system_status`
获取系统运行状态和健康信息。

**参数:** 无

**返回值:**
- `Dict`: 包含系统状态、数据统计、缓存信息等

**状态指标:**
```json
{
  "system": {
    "version": "3.3.0",
    "uptime": "2h 30m",
    "timezone": "Europe/Berlin"
  },
  "data": {
    "total_platforms": 12,
    "last_crawl": "2025-11-27 14:30:00",
    "data_points": 15420
  },
  "cache": {
    "hit_rate": 0.85,
    "size_mb": 45.2
  },
  "health": "healthy"
}
```

## 🔧 工具使用示例

### 基本查询
```python
# 获取最新新闻
news = get_latest_news(limit=5)
for item in news:
    print(f"{item['platform_name']}: {item['title']}")

# 搜索特定话题
results = search_news("人工智能", platforms=['zhihu'])
```

### 趋势分析
```python
# 分析话题趋势
trend = analyze_topic_trend("ChatGPT", days=14)
print(f"当前热度: {trend['current_heat']}")
print(f"预测峰值: {trend['predicted_peak']}")

# 生成摘要报告
report = generate_summary_report("daily", "2025-11-27")
```

### 系统管理
```python
# 检查系统状态
status = get_system_status()
if status['health'] == 'healthy':
    print("系统运行正常")
else:
    print(f"系统异常: {status['issues']}")

# 手动触发爬取
result = trigger_crawl(platforms=['zhihu', 'weibo'])
print(f"爬取完成: {result['success_count']} 成功")
```

## ⚡ 性能优化建议

### 缓存策略
- 热点数据缓存 15 分钟
- 历史数据缓存 1 小时
- 配置数据缓存 24 小时

### 请求限制
- 普通用户: 100 次/小时
- 高级用户: 1000 次/小时
- 企业用户: 无限制

### 并发控制
- 单个用户最大并发: 3
- 全局最大并发: 50
- 队列等待超时: 30秒

## 🚨 错误处理

### 常见错误码
- `400`: 参数错误
- `404`: 数据不存在
- `429`: 请求过于频繁
- `500`: 服务器内部错误
- `503`: 服务暂时不可用

### 重试策略
- 网络错误: 指数退避重试 (最多3次)
- 服务器错误: 固定间隔重试 (最多2次)
- 客户端错误: 不重试，直接返回错误

## 🔒 安全限制

- 请求大小限制: 10MB
- 响应大小限制: 50MB
- 文本长度限制: 10000字符
- 数组长度限制: 1000项

---

**API 版本**: 1.0.0 | **最后更新**: 2025-11-27