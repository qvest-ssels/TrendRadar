"""
TrendRadar MCP Server - FastMCP 2.0 实现

使用 FastMCP 2.0 提供生产级 MCP 工具服务器。
支持 stdio 和 HTTP 两种传输模式。
"""

import json
import logging
import signal
import sys
from datetime import datetime
from typing import List, Optional, Dict

from fastmcp import FastMCP

from .tools.data_query import DataQueryTools
from .tools.analytics import AnalyticsTools
from .tools.search_tools import SearchTools
from .tools.config_mgmt import ConfigManagementTools
from .tools.system import SystemManagementTools
from .utils.date_parser import DateParser
from .utils.errors import MCPError


# 创建 FastMCP 2.0 应用
mcp = FastMCP('trendradar-news')

# 全局工具实例（在第一次请求时初始化）
_tools_instances = {}


def _get_tools(project_root: Optional[str] = None):
    """获取或创建工具实例（单例模式）"""
    if not _tools_instances:
        _tools_instances['data'] = DataQueryTools(project_root)
        _tools_instances['analytics'] = AnalyticsTools(project_root)
        _tools_instances['search'] = SearchTools(project_root)
        _tools_instances['config'] = ConfigManagementTools(project_root)
        _tools_instances['system'] = SystemManagementTools(project_root)
    return _tools_instances


# ==================== 日期解析工具（优先调用）====================

@mcp.tool
async def resolve_date_range(
    expression: str
) -> str:
    """
    【推荐优先调用】将自然语言日期表达式解析为标准日期范围

    **为什么需要这个工具？**
    用户经常使用"本周"、"最近7天"等自然语言表达日期，但 AI 模型自己计算日期
    可能导致不一致的结果。此工具在服务器端使用精确的当前时间计算，确保所有
    AI 模型获得一致的日期范围。

    **推荐使用流程：**
    1. 用户说"分析AI本周的情感倾向"
    2. AI 调用 resolve_date_range("本周") → 获取精确日期范围
    3. AI 调用 analyze_sentiment(topic="ai", date_range=上一步返回的date_range)

    Args:
        expression: 自然语言日期表达式，支持：
            - 单日: "今天", "昨天", "today", "yesterday"
            - 周: "本周", "上周", "this week", "last week"
            - 月: "本月", "上月", "this month", "last month"
            - 最近N天: "最近7天", "最近30天", "last 7 days", "last 30 days"
            - 动态: "最近5天", "last 10 days"（任意天数）

    Returns:
        JSON格式的日期范围，可直接用于其他工具的 date_range 参数：
        {
            "success": true,
            "expression": "本周",
            "date_range": {
                "start": "2025-11-18",
                "end": "2025-11-26"
            },
            "current_date": "2025-11-26",
            "description": "本周（周一到周日，11-18 至 11-26）"
        }

    Examples:
        用户："分析AI本周的情感倾向"
        AI调用步骤：
        1. resolve_date_range("本周")
           → {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}, ...}
        2. analyze_sentiment(topic="ai", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        用户："看看最近7天的特斯拉新闻"
        AI调用步骤：
        1. resolve_date_range("最近7天")
           → {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}, ...}
        2. search_news(query="特斯拉", date_range={"start": "2025-11-20", "end": "2025-11-26"})
    """
    try:
        result = DateParser.resolve_date_range_expression(expression)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except MCPError as e:
        return json.dumps({
            "success": False,
            "error": e.to_dict()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# ==================== 数据查询工具 ====================

@mcp.tool
async def get_latest_news(
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    获取最新一批爬取的新闻数据，快速了解当前热点

    Args:
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"Zhihu"、"Weibo"），方便AI识别
        limit: 返回条数限制，默认50，最大1000
               注意：实际返回数量可能少于请求值，取决于当前可用的新闻总数
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的新闻列表

    **重要：数据展示建议**
    本工具会返回完整的新闻列表（通常50条）给你。但请注意：
    - **工具返回**：完整的50条数据 ✅
    - **建议展示**：向用户展示全部数据，除非用户明确要求总结
    - **用户期望**：用户可能需要完整数据，请谨慎总结

    **何时可以总结**：
    - 用户明确说"给我总结一下"或"挑重点说"
    - 数据量超过100条时，可先展示部分并询问是否查看全部

    **注意**：如果用户询问"为什么只显示了部分"，说明他们需要完整数据
    """
    tools = _get_tools()
    result = tools['data'].get_latest_news(platforms=platforms, limit=limit, include_url=include_url)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_trending_topics(
    top_n: int = 10,
    mode: str = 'current'
) -> str:
    """
    获取个人关注词的新闻出现频率统计（基于 config/frequency_words.txt）

    注意：本工具不是自动提取新闻热点，而是统计你在 config/frequency_words.txt 中
    设置的个人关注词在新闻中出现的频率。你可以自定义这个关注词列表。

    Args:
        top_n: 返回TOP N关注词，默认10
        mode: 模式选择
            - daily: 当日累计数据统计
            - current: 最新一批数据统计（默认）

    Returns:
        JSON格式的关注词频率统计列表
    """
    tools = _get_tools()
    result = tools['data'].get_trending_topics(top_n=top_n, mode=mode)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_news_by_date(
    date_query: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    获取指定日期的新闻数据，用于历史数据分析和对比

    Args:
        date_query: 日期查询，可选格式:
            - 自然语言: "今天", "昨天", "前天", "3天前"
            - 标准日期: "2024-01-15", "2024/01/15"
            - 默认值: "今天"（节省token）
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"Zhihu"、"Weibo"），方便AI识别
        limit: 返回条数限制，默认50，最大1000
               注意：实际返回数量可能少于请求值，取决于指定日期的新闻总数
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的新闻列表，包含标题、平台、排名等信息

    **重要：数据展示建议**
    本工具会返回完整的新闻列表（通常50条）给你。但请注意：
    - **工具返回**：完整的50条数据 ✅
    - **建议展示**：向用户展示全部数据，除非用户明确要求总结
    - **用户期望**：用户可能需要完整数据，请谨慎总结

    **何时可以总结**：
    - 用户明确说"给我总结一下"或"挑重点说"
    - 数据量超过100条时，可先展示部分并询问是否查看全部

    **注意**：如果用户询问"为什么只显示了部分"，说明他们需要完整数据
    """
    tools = _get_tools()
    result = tools['data'].get_news_by_date(
        date_query=date_query,
        platforms=platforms,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)



# ==================== 高级数据分析工具 ====================

@mcp.tool
async def analyze_topic_trend(
    topic: str,
    analysis_type: str = "trend",
    date_range: Optional[Dict[str, str]] = None,
    granularity: str = "day",
    threshold: float = 3.0,
    time_window: int = 24,
    lookahead_hours: int = 6,
    confidence_threshold: float = 0.7
) -> str:
    """
    统一话题趋势分析工具 - 整合多种趋势分析模式

    **重要：日期范围处理**
    当用户使用"本周"、"最近7天"等自然语言时，请先调用 resolve_date_range 工具获取精确日期：
    1. 调用 resolve_date_range("本周") → 获取 {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    2. 将返回的 date_range 传入本工具

    Args:
        topic: 话题关键词（必需）
        analysis_type: 分析类型，可选值：
            - "trend": 热度趋势分析（追踪话题的热度变化）
            - "lifecycle": 生命周期分析（从出现到消失的完整周期）
            - "viral": 异常热度检测（识别突然爆火的话题）
            - "predict": 话题预测（预测未来可能的热点）
        date_range: 日期范围（trend和lifecycle模式），可选
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **获取方式**: 调用 resolve_date_range 工具解析自然语言日期
                    - **默认**: 不指定时默认分析最近7天
        granularity: 时间粒度（trend模式），默认"day"（仅支持 day，因为底层数据按天聚合）
        threshold: 热度突增倍数阈值（viral模式），默认3.0
        time_window: 检测时间窗口小时数（viral模式），默认24
        lookahead_hours: 预测未来小时数（predict模式），默认6
        confidence_threshold: 置信度阈值（predict模式），默认0.7

    Returns:
        JSON格式的趋势分析结果

    Examples:
        用户："分析AI本周的趋势"
        推荐调用流程：
        1. resolve_date_range("本周") → {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}}
        2. analyze_topic_trend(topic="AI", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        用户："看看特斯拉最近30天的热度"
        推荐调用流程：
        1. resolve_date_range("最近30天") → {"date_range": {"start": "2025-10-28", "end": "2025-11-26"}}
        2. analyze_topic_trend(topic="特斯拉", analysis_type="lifecycle", date_range=...)
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_topic_trend_unified(
        topic=topic,
        analysis_type=analysis_type,
        date_range=date_range,
        granularity=granularity,
        threshold=threshold,
        time_window=time_window,
        lookahead_hours=lookahead_hours,
        confidence_threshold=confidence_threshold
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_data_insights(
    insight_type: str = "platform_compare",
    topic: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None,
    min_frequency: int = 3,
    top_n: int = 20
) -> str:
    """
    统一数据洞察分析工具 - 整合多种数据分析模式

    Args:
        insight_type: 洞察类型，可选值：
            - "platform_compare": 平台对比分析（对比不同平台对话题的关注度）
            - "platform_activity": 平台活跃度统计（统计各平台发布频率和活跃时间）
            - "keyword_cooccur": 关键词共现分析（分析关键词同时出现的模式）
        topic: 话题关键词（可选，platform_compare模式适用）
        date_range: **【对象类型】** 日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **示例**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **重要**: 必须是对象格式，不能传递整数
        min_frequency: 最小共现频次（keyword_cooccur模式），默认3
        top_n: 返回TOP N结果（keyword_cooccur模式），默认20

    Returns:
        JSON格式的数据洞察分析结果

    Examples:
        - analyze_data_insights(insight_type="platform_compare", topic="人工智能")
        - analyze_data_insights(insight_type="platform_activity", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        - analyze_data_insights(insight_type="keyword_cooccur", min_frequency=5, top_n=15)
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_data_insights_unified(
        insight_type=insight_type,
        topic=topic,
        date_range=date_range,
        min_frequency=min_frequency,
        top_n=top_n
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_sentiment(
    topic: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    date_range: Optional[Dict[str, str]] = None,
    limit: int = 50,
    sort_by_weight: bool = True,
    include_url: bool = False
) -> str:
    """
    分析新闻的情感倾向和热度趋势

    **重要：日期范围处理**
    当用户使用"本周"、"最近7天"等自然语言时，请先调用 resolve_date_range 工具获取精确日期：
    1. 调用 resolve_date_range("本周") → 获取 {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    2. 将返回的 date_range 传入本工具

    Args:
        topic: 话题关键词（可选）
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"Zhihu"、"Weibo"），方便AI识别
        date_range: 日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **获取方式**: 调用 resolve_date_range 工具解析自然语言日期
                    - **默认**: 不指定则默认查询今天的数据
        limit: 返回新闻数量，默认50，最大100
               注意：本工具会对新闻标题进行去重（同一标题在不同平台只保留一次），
               因此实际返回数量可能少于请求的 limit 值
        sort_by_weight: 是否按热度权重排序，默认True
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的分析结果，包含情感分布、热度趋势和相关新闻

    Examples:
        用户："分析AI本周的情感倾向"
        推荐调用流程：
        1. resolve_date_range("本周") → {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}}
        2. analyze_sentiment(topic="AI", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        用户："分析特斯拉最近7天的新闻情感"
        推荐调用流程：
        1. resolve_date_range("最近7天") → {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}}
        2. analyze_sentiment(topic="特斯拉", date_range={"start": "2025-11-20", "end": "2025-11-26"})

    **重要：数据展示策略**
    - 本工具返回完整的分析结果和新闻列表
    - **默认展示方式**：展示完整的分析结果（包括所有新闻）
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_sentiment(
        topic=topic,
        platforms=platforms,
        date_range=date_range,
        limit=limit,
        sort_by_weight=sort_by_weight,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def find_similar_news(
    reference_title: str,
    threshold: float = 0.6,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    查找与指定新闻标题相似的其他新闻

    Args:
        reference_title: 新闻标题（完整或部分）
        threshold: 相似度阈值，0-1之间，默认0.6
                   注意：阈值越高匹配越严格，返回结果越少
        limit: 返回条数限制，默认50，最大100
               注意：实际返回数量取决于相似度匹配结果，可能少于请求值
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的相似新闻列表，包含相似度分数

    **重要：数据展示策略**
    - 本工具返回完整的相似新闻列表
    - **默认展示方式**：展示全部返回的新闻（包括相似度分数）
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['analytics'].find_similar_news(
        reference_title=reference_title,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def generate_summary_report(
    report_type: str = "daily",
    date_range: Optional[Dict[str, str]] = None
) -> str:
    """
    每日/每周摘要生成器 - 自动生成热点摘要报告

    Args:
        report_type: 报告类型（daily/weekly）
        date_range: **【对象类型】** 自定义日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **示例**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **重要**: 必须是对象格式，不能传递整数

    Returns:
        JSON格式的摘要报告，包含Markdown格式内容
    """
    tools = _get_tools()
    result = tools['analytics'].generate_summary_report(
        report_type=report_type,
        date_range=date_range
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 智能检索工具 ====================

@mcp.tool
async def search_news(
    query: str,
    search_mode: str = "keyword",
    date_range: Optional[Dict[str, str]] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    sort_by: str = "relevance",
    threshold: float = 0.6,
    include_url: bool = False
) -> str:
    """
    统一搜索接口，支持多种搜索模式

    **重要：日期范围处理**
    当用户使用"本周"、"最近7天"等自然语言时，请先调用 resolve_date_range 工具获取精确日期：
    1. 调用 resolve_date_range("本周") → 获取 {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    2. 将返回的 date_range 传入本工具

    Args:
        query: 搜索关键词或内容片段
        search_mode: 搜索模式，可选值：
            - "keyword": 精确关键词匹配（默认，适合搜索特定话题）
            - "fuzzy": 模糊内容匹配（适合搜索内容片段，会过滤相似度低于阈值的结果）
            - "entity": 实体名称搜索（适合搜索人物/地点/机构）
        date_range: 日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **获取方式**: 调用 resolve_date_range 工具解析自然语言日期
                    - **默认**: 不指定时默认查询今天的新闻
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"Zhihu"、"Weibo"），方便AI识别
        limit: 返回条数限制，默认50，最大1000
               注意：实际返回数量取决于搜索匹配结果（特别是 fuzzy 模式下会过滤低相似度结果）
        sort_by: 排序方式，可选值：
            - "relevance": 按相关度排序（默认）
            - "weight": 按新闻权重排序
            - "date": 按日期排序
        threshold: 相似度阈值（仅fuzzy模式有效），0-1之间，默认0.6
                   注意：阈值越高匹配越严格，返回结果越少
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的搜索结果，包含标题、平台、排名等信息

    Examples:
        用户："搜索本周的AI新闻"
        推荐调用流程：
        1. resolve_date_range("本周") → {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}}
        2. search_news(query="AI", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        用户："最近7天的特斯拉新闻"
        推荐调用流程：
        1. resolve_date_range("最近7天") → {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}}
        2. search_news(query="特斯拉", date_range={"start": "2025-11-20", "end": "2025-11-26"})

        用户："今天的AI新闻"（默认今天，无需解析）
        → search_news(query="AI")

    **重要：数据展示策略**
    - 本工具返回完整的搜索结果列表
    - **默认展示方式**：展示全部返回的新闻，无需总结或筛选
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['search'].search_news_unified(
        query=query,
        search_mode=search_mode,
        date_range=date_range,
        platforms=platforms,
        limit=limit,
        sort_by=sort_by,
        threshold=threshold,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def search_related_news_history(
    reference_text: str,
    time_preset: str = "yesterday",
    threshold: float = 0.4,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    基于种子新闻，在历史数据中搜索相关新闻

    Args:
        reference_text: 参考新闻标题（完整或部分）
        time_preset: 时间范围预设值，可选：
            - "yesterday": 昨天
            - "last_week": 上周 (7天)
            - "last_month": 上个月 (30天)
            - "custom": 自定义日期范围（需要提供 start_date 和 end_date）
        threshold: 相关性阈值，0-1之间，默认0.4
                   注意：综合相似度计算（70%关键词重合 + 30%文本相似度）
                   阈值越高匹配越严格，返回结果越少
        limit: 返回条数限制，默认50，最大100
               注意：实际返回数量取决于相关性匹配结果，可能少于请求值
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的相关新闻列表，包含相关性分数和时间分布

    **重要：数据展示策略**
    - 本工具返回完整的相关新闻列表
    - **默认展示方式**：展示全部返回的新闻（包括相关性分数）
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['search'].search_related_news_history(
        reference_text=reference_text,
        time_preset=time_preset,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def deep_search(
    query: str,
    platforms: Optional[List[str]] = None,
    language: Optional[str] = None,
    mode: str = "both",
    max_results: int = 50,
    date_range: Optional[Dict[str, str]] = None,
    include_url: bool = False
) -> str:
    """
    深度搜索 - 结合本地缓存和站点实时搜索

    此工具提供比 search_news 更全面的搜索能力：
    - headlines: 仅搜索本地缓存的RSS新闻标题（快速）
    - site_search: 直接搜索新闻站点（更全面但较慢）
    - both: 两种模式结合，去重后返回（推荐）

    当前支持站点搜索的平台：
    - theguardian (The Guardian) - en
    - spiegel (Der Spiegel) - de
    - aljazeera (Al Jazeera English) - en
    - heise (Heise Online) - de
    - lemonde (Le Monde) - fr
    - straitstimes (The Straits Times) - en
    - timesofindia (Times of India) - en

    Args:
        query: 搜索关键词
        platforms: 平台ID列表，如 ['theguardian', 'spiegel', 'aljazeera']
                   - 不指定时：使用所有支持搜索的平台
                   - 仅支持配置了 search 的平台才能进行站点搜索
        language: 语言过滤，可选值：
            - "en": 英语平台 (Guardian, Al Jazeera, Straits Times, Times of India)
            - "de": 德语平台 (Spiegel, Heise)
            - "fr": 法语平台 (Le Monde)
            - "zh": 中文平台
            - None: 不过滤，搜索所有平台（默认）
        mode: 搜索模式，可选值：
            - "headlines": 仅搜索本地缓存的新闻标题（快速，但仅限RSS更新的内容）
            - "site_search": 仅搜索站点（更全面，但较慢且有速率限制）
            - "both": 两种模式结合（推荐，自动去重和排序）
        max_results: 返回条数限制，默认50，最大200
        date_range: 日期范围（仅对 headlines 模式有效）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **获取方式**: 调用 resolve_date_range 工具解析自然语言日期
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的搜索结果，包含：
        - results: 搜索结果列表
        - total_count: 总结果数
        - sources: 结果来源统计（headlines/site_search）
        - platforms_searched: 搜索的平台列表
        - language_filter: 使用的语言过滤

    Examples:
        用户："深度搜索关于AI的新闻"
        → deep_search(query="AI", mode="both")

        用户："搜索德语新闻中关于Tesla的报道"
        → deep_search(query="Tesla", language="de")

        用户："在Guardian上搜索climate change"
        → deep_search(query="climate change", platforms=["theguardian"], mode="site_search")

        用户："搜索所有英语平台关于AI的新闻"
        → deep_search(query="AI", language="en", mode="both")
    """
    from .services.search_service import DeepSearchService
    
    try:
        search_service = DeepSearchService()
        
        result = search_service.deep_search(
            query=query,
            platforms=platforms,
            language=language,
            mode=mode,
            max_results=max_results,
            date_range=date_range,
            include_url=include_url
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "DEEP_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_wikipedia_context(
    topic: str,
    language: str = "en",
    include_related: bool = False
) -> str:
    """
    获取维基百科背景信息 - Get Wikipedia context for a topic

    This tool provides background information from Wikipedia to enrich news context.
    Use it when users ask about:
    - Who is [person]?
    - What is [company/organization]?
    - Background on [topic/event]
    - Context about [news subject]

    Supports multiple languages for culturally-aware context.

    Args:
        topic: The topic to look up (person, company, event, concept, etc.)
        language: Wikipedia language code:
            - "en": English (default)
            - "de": German
            - "fr": French
            - "es": Spanish
            - "zh": Chinese
            - "ja": Japanese
            - "ru": Russian
            - "pt": Portuguese
            - "ar": Arabic
            - "ko": Korean
        include_related: Whether to include related topics (default: False)

    Returns:
        JSON with:
        - title: Article title
        - extract: Summary text
        - description: Short description
        - url: Link to Wikipedia article
        - thumbnail: Image URL (if available)
        - related_topics: Related articles (if include_related=True)

    Examples:
        用户："谁是马斯克？" / "Who is Elon Musk?"
        → get_wikipedia_context(topic="Elon Musk", language="en")

        用户："Was ist Tesla?" (German)
        → get_wikipedia_context(topic="Tesla, Inc.", language="de")

        用户："告诉我关于SpaceX的背景"
        → get_wikipedia_context(topic="SpaceX", language="zh")
    """
    from .services.wikipedia_service import get_wikipedia_service
    
    try:
        wiki = get_wikipedia_service()
        result = wiki.get_context(
            topic=topic,
            language=language,
            include_related=include_related
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "WIKIPEDIA_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_wikipedia(
    query: str,
    language: str = "en",
    limit: int = 5
) -> str:
    """
    搜索维基百科 - Search Wikipedia for articles

    Search Wikipedia to find relevant articles about a topic.
    Use when the exact article title is unknown.

    Args:
        query: Search query
        language: Wikipedia language code (en, de, fr, zh, etc.)
        limit: Maximum number of results (default: 5)

    Returns:
        JSON with search results including title, snippet, and URL

    Examples:
        用户："搜索关于人工智能的维基百科文章"
        → search_wikipedia(query="artificial intelligence", language="en")
    """
    from .services.wikipedia_service import get_wikipedia_service
    
    try:
        wiki = get_wikipedia_service()
        result = wiki.search(query=query, language=language, limit=limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "WIKIPEDIA_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_wikipedia_user(
    username: str,
    language: str = "en"
) -> str:
    """
    👤 Look up Wikipedia user information
    
    Get information about a Wikipedia editor/contributor.
    
    Args:
        username: Wikipedia username to look up
        language: Wikipedia language code (en, de, fr, etc.)
    
    Returns:
        JSON with user info: edit count, registration date, groups, block status
    
    Examples:
        Get info about a Wikipedia editor
        → get_wikipedia_user(username="Jimbo Wales")
    """
    from .services.wikipedia_service import get_wikipedia_service
    
    try:
        wiki = get_wikipedia_service()
        result = wiki.get_user(username=username, language=language)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "WIKIPEDIA_USER_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# =============================================================================
# ASK AN EXPERT - HuggingFace Tools
# =============================================================================

@mcp.tool
async def search_huggingface_models(
    query: str,
    task: Optional[str] = None,
    sort: str = "downloads",
    limit: int = 10
) -> str:
    """
    🧑‍🔬 Ask an Expert: Search HuggingFace for ML models
    
    Search the HuggingFace Hub for machine learning models.
    Use when users ask about:
    - Best models for a task (e.g., "best LLM for code generation")
    - Specific model families (e.g., "Llama models", "BERT variants")
    - Models by capability (e.g., "translation models", "image generation")
    
    Args:
        query: Search query (e.g., "code generation", "llama", "sentiment analysis")
        task: Filter by task type (optional):
            - "text-generation": LLMs, chat models
            - "text-classification": Sentiment, topic classification
            - "translation": Language translation
            - "summarization": Text summarization
            - "conversational": Chat/dialogue models
            - "text-to-image": Image generation (Stable Diffusion, etc.)
            - "automatic-speech-recognition": Speech-to-text
            - "feature-extraction": Embeddings models
        sort: Sort by "downloads" (default), "likes", "created", "modified"
        limit: Maximum results (default: 10, max: 100)
    
    Returns:
        JSON with models including name, downloads, likes, task, URL
    
    Examples:
        "What's the best LLM for code?" 
        → search_huggingface_models(query="code generation", task="text-generation")
        
        "Find image generation models"
        → search_huggingface_models(query="stable diffusion", task="text-to-image")
        
        "Most popular embedding models"
        → search_huggingface_models(query="embeddings", task="feature-extraction", sort="downloads")
    """
    from .services.huggingface_service import get_huggingface_service
    
    try:
        hf = get_huggingface_service()
        result = hf.search_models(query=query, task=task, sort=sort, limit=limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "HUGGINGFACE_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_huggingface_datasets(
    query: str,
    sort: str = "downloads",
    limit: int = 10
) -> str:
    """
    🧑‍🔬 Ask an Expert: Search HuggingFace for datasets
    
    Search the HuggingFace Hub for machine learning datasets.
    Use when users ask about:
    - Training data for specific tasks
    - Benchmark datasets
    - Data for fine-tuning models
    
    Args:
        query: Search query (e.g., "sentiment analysis", "code", "medical")
        sort: Sort by "downloads" (default), "likes", "created", "modified"
        limit: Maximum results (default: 10)
    
    Returns:
        JSON with datasets including name, downloads, tags, URL
    
    Examples:
        "Find datasets for training a code model"
        → search_huggingface_datasets(query="code programming")
        
        "What datasets are available for sentiment analysis?"
        → search_huggingface_datasets(query="sentiment")
    """
    from .services.huggingface_service import get_huggingface_service
    
    try:
        hf = get_huggingface_service()
        result = hf.search_datasets(query=query, sort=sort, limit=limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "HUGGINGFACE_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_ml_papers(
    query: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    🧑‍🔬 Ask an Expert: Get latest ML/AI research papers
    
    Get curated ML papers from HuggingFace Daily Papers or search by topic.
    Use when users ask about:
    - Latest research in AI/ML
    - Papers on specific topics (transformers, LLMs, etc.)
    - Academic research for a technique
    
    Args:
        query: Search query (optional, if None returns latest daily papers)
        limit: Maximum results (default: 10)
    
    Returns:
        JSON with papers including title, authors, summary, arXiv link
    
    Examples:
        "What are the latest AI research papers?"
        → get_ml_papers()
        
        "Find papers about retrieval augmented generation"
        → get_ml_papers(query="retrieval augmented generation")
        
        "Research on transformer architectures"
        → get_ml_papers(query="transformer architecture")
    """
    from .services.huggingface_service import get_huggingface_service
    
    try:
        hf = get_huggingface_service()
        if query:
            result = hf.search_papers(query=query, limit=limit)
        else:
            result = hf.get_daily_papers(limit=limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "HUGGINGFACE_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_arxiv(
    query: str,
    category: Optional[str] = None,
    max_results: int = 10,
    sort_by: str = "relevance",
    include_university_links: bool = True
) -> str:
    """
    🧑‍🔬 Ask an Expert: Search arXiv for academic papers
    
    Search the arXiv preprint server for academic research papers.
    Returns papers with abstracts, authors, affiliations, and links to universities via Wikipedia.
    
    Use when users ask about:
    - Academic research on specific topics
    - Scientific papers and preprints  
    - Research from specific fields (CS, ML, Physics, Math)
    - Papers by specific authors or institutions
    
    Args:
        query: Search query (e.g., "transformer architecture", "large language models")
        category: Filter by arXiv category (optional):
            - "cs.AI": Artificial Intelligence
            - "cs.CL": Computation and Language (NLP)
            - "cs.CV": Computer Vision
            - "cs.LG": Machine Learning
            - "cs.NE": Neural and Evolutionary Computing
            - "cs.IR": Information Retrieval
            - "stat.ML": Machine Learning (Statistics)
        max_results: Maximum papers to return (default: 10, max: 50)
        sort_by: Sort order - "relevance", "lastUpdatedDate", "submittedDate"
        include_university_links: Add Wikipedia links for author universities (default: True)
    
    Returns:
        JSON with papers including:
        - title, abstract, authors
        - affiliations with Wikipedia university links
        - arXiv URL and PDF link
        - categories and publication date
    
    Examples:
        "Latest transformer architecture research"
        → search_arxiv(query="transformer architecture", category="cs.LG")
        
        "Papers about RAG from NLP category"
        → search_arxiv(query="retrieval augmented generation", category="cs.CL")
        
        "Recent computer vision papers"
        → search_arxiv(query="deep learning", category="cs.CV", sort_by="submittedDate")
    """
    from .services.arxiv_service import get_arxiv_service
    
    try:
        arxiv = get_arxiv_service()
        result = arxiv.search(
            query=query,
            category=category,
            max_results=max_results,
            sort_by=sort_by,
            include_university_links=include_university_links
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "ARXIV_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_arxiv_paper(
    arxiv_id: str
) -> str:
    """
    🧑‍🔬 Ask an Expert: Get details for a specific arXiv paper
    
    Retrieve full details for a specific arXiv paper by its ID.
    
    Args:
        arxiv_id: arXiv paper ID (e.g., "2301.07041", "2312.12456")
    
    Returns:
        JSON with full paper details including abstract, all authors, affiliations
    
    Examples:
        "Get details for paper 2301.07041"
        → get_arxiv_paper(arxiv_id="2301.07041")
    """
    from .services.arxiv_service import get_arxiv_service
    
    try:
        arxiv = get_arxiv_service()
        result = arxiv.get_paper(arxiv_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "ARXIV_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_github_repos(
    query: str,
    language: Optional[str] = None,
    sort: str = "stars",
    limit: int = 10,
    min_stars: Optional[int] = None
) -> str:
    """
    🧑‍🔬 Ask an Expert: Search GitHub for repositories
    
    Search GitHub repositories by keywords, topics, or names.
    Great for finding open source projects, libraries, and tools.
    
    Use when users ask about:
    - Best libraries/tools for a specific task
    - Open source alternatives to products
    - Popular projects in a programming language
    - Implementations of algorithms/architectures
    
    Args:
        query: Search query (keywords, topics, project names)
               Examples: "web scraping", "machine learning", "react components"
        language: Filter by programming language (optional)
                  Options: python, javascript, typescript, java, go, rust, c, cpp, csharp, ruby, etc.
        sort: Sort results by (default: stars)
              - "stars": Most starred repos
              - "forks": Most forked repos
              - "updated": Recently updated
              - "best-match": Best match for query
        limit: Maximum results (default: 10, max: 30)
        min_stars: Minimum star count filter (optional)
    
    Returns:
        JSON with repos including name, description, stars, forks, language, topics, URL
    
    Examples:
        "Best Python libraries for web scraping"
        → search_github_repos(query="web scraping", language="python", sort="stars")
        
        "Open source LLM implementations"
        → search_github_repos(query="large language model LLM", min_stars=1000)
        
        "Popular React component libraries"
        → search_github_repos(query="react components ui", language="javascript")
        
        "Rust async runtime projects"
        → search_github_repos(query="async runtime", language="rust")
    """
    from .services.github_service import get_github_service
    
    try:
        github = get_github_service()
        result = github.search_repos(
            query=query,
            language=language,
            sort=sort,
            limit=limit,
            min_stars=min_stars
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "GITHUB_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def expert_research(
    query: str,
    include_papers: bool = True,
    include_repos: bool = True,
    include_models: bool = True,
    include_datasets: bool = False,
    max_results_per_source: int = 5
) -> str:
    """
    🧑‍🔬 Ask an Expert: Comprehensive research combining multiple expert sources
    
    This is the PREFERRED tool for technical/research questions. It combines:
    - arXiv academic papers (latest research)
    - GitHub repositories (implementations & tools)  
    - HuggingFace models (pre-trained ML models)
    - HuggingFace datasets (optional)
    
    Use when users ask broad technical questions like:
    - "How do I build a RAG system?"
    - "What's the state of the art in image generation?"
    - "Best approaches for sentiment analysis"
    - "How to implement a transformer from scratch"
    
    For specific narrow queries, use individual tools instead:
    - Just want papers? → search_arxiv
    - Just want repos? → search_github_repos
    - Just want models? → search_huggingface_models
    
    Args:
        query: Research question or topic
               Examples: "RAG retrieval augmented generation", "vision transformers", "code generation"
        include_papers: Include arXiv papers (default: True)
        include_repos: Include GitHub repos (default: True)
        include_models: Include HuggingFace models (default: True)
        include_datasets: Include HuggingFace datasets (default: False)
        max_results_per_source: Max results from each source (default: 5)
    
    Returns:
        JSON with combined research results:
        - papers: Academic papers with abstracts and links
        - repos: GitHub projects with stars and descriptions
        - models: ML models with download counts
        - datasets: Training datasets (if requested)
        - summary: Quick overview of what was found
    
    Examples:
        "How to build a RAG system"
        → expert_research(query="RAG retrieval augmented generation")
        
        "State of the art in image generation"
        → expert_research(query="diffusion models image generation", include_datasets=True)
        
        "Best way to do sentiment analysis"
        → expert_research(query="sentiment analysis NLP", include_models=True)
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    results = {
        "success": True,
        "query": query,
        "papers": [],
        "repos": [],
        "models": [],
        "datasets": [],
        "summary": {},
        "sources_queried": []
    }
    
    # Use ThreadPoolExecutor for parallel API calls
    executor = ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_event_loop()
    
    async def fetch_arxiv():
        if not include_papers:
            return None
        try:
            from .services.arxiv_service import get_arxiv_service
            arxiv = get_arxiv_service()
            return arxiv.search(
                query=query,
                max_results=max_results_per_source,
                include_university_links=True
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def fetch_github():
        if not include_repos:
            return None
        try:
            from .services.github_service import get_github_service
            github = get_github_service()
            return github.search_repos(
                query=query,
                sort="stars",
                limit=max_results_per_source,
                min_stars=100  # Filter out low-quality repos
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def fetch_models():
        if not include_models:
            return None
        try:
            from .services.huggingface_service import get_huggingface_service
            hf = get_huggingface_service()
            return hf.search_models(
                query=query,
                sort="downloads",
                limit=max_results_per_source
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def fetch_datasets():
        if not include_datasets:
            return None
        try:
            from .services.huggingface_service import get_huggingface_service
            hf = get_huggingface_service()
            return hf.search_datasets(
                query=query,
                sort="downloads",
                limit=max_results_per_source
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Run all fetches concurrently
    try:
        arxiv_result, github_result, models_result, datasets_result = await asyncio.gather(
            fetch_arxiv(),
            fetch_github(),
            fetch_models(),
            fetch_datasets(),
            return_exceptions=True
        )
        
        # Process arXiv results
        if arxiv_result and isinstance(arxiv_result, dict) and arxiv_result.get("success"):
            results["papers"] = arxiv_result.get("papers", [])
            results["sources_queried"].append("arxiv")
        
        # Process GitHub results
        if github_result and isinstance(github_result, dict) and github_result.get("success"):
            results["repos"] = github_result.get("repos", [])
            results["sources_queried"].append("github")
        
        # Process HuggingFace models
        if models_result and isinstance(models_result, dict) and models_result.get("success"):
            results["models"] = models_result.get("models", [])
            results["sources_queried"].append("huggingface_models")
        
        # Process HuggingFace datasets
        if datasets_result and isinstance(datasets_result, dict) and datasets_result.get("success"):
            results["datasets"] = datasets_result.get("datasets", [])
            results["sources_queried"].append("huggingface_datasets")
        
        # Generate summary
        results["summary"] = {
            "total_papers": len(results["papers"]),
            "total_repos": len(results["repos"]),
            "total_models": len(results["models"]),
            "total_datasets": len(results["datasets"]),
            "top_paper": results["papers"][0]["title"] if results["papers"] else None,
            "top_repo": f"{results['repos'][0]['full_name']} ({results['repos'][0]['stars']}⭐)" if results["repos"] else None,
            "top_model": results["models"][0]["id"] if results["models"] else None,
        }
        
        # Add cross-references (find repos that implement papers)
        if results["papers"] and results["repos"]:
            # Simple heuristic: look for matching keywords
            paper_keywords = set()
            for paper in results["papers"][:3]:
                title_words = paper.get("title", "").lower().split()
                paper_keywords.update(w for w in title_words if len(w) > 4)
            
            for repo in results["repos"]:
                repo_text = f"{repo.get('name', '')} {repo.get('description', '')}".lower()
                matches = sum(1 for kw in paper_keywords if kw in repo_text)
                if matches >= 2:
                    repo["likely_implements_paper"] = True
        
        return json.dumps(results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "EXPERT_RESEARCH_ERROR",
                "message": str(e)
            },
            "query": query
        }, ensure_ascii=False, indent=2)


# ==================== YouTube Context Tools ====================

@mcp.tool
async def search_youtube(
    query: str,
    limit: int = 5
) -> str:
    """
    🎬 Search YouTube for educational videos, tutorials, and talks
    
    Finds relevant videos for technical topics. Useful for:
    - Tutorial videos ("how to implement X")
    - Conference talks ("NeurIPS 2024 keynote")
    - Explainer videos ("transformer architecture explained")
    - Course lectures ("deep learning course")
    
    Note: Returns video IDs and URLs. Use get_youtube_transcript 
    to get the actual content from a video.
    
    Args:
        query: Search query
               Examples: "RAG tutorial", "attention mechanism explained", "PyTorch quickstart"
        limit: Number of results (default: 5, max: 20)
    
    Returns:
        JSON with video results:
        - videos: List of {video_id, title, channel, url}
        - count: Number of results
    
    Examples:
        "Find tutorials on RAG"
        → search_youtube(query="RAG tutorial retrieval augmented generation")
        
        "Conference talks on transformers"
        → search_youtube(query="transformer architecture conference talk")
        
        "Python async explained"
        → search_youtube(query="python async await tutorial")
    """
    from .services.youtube_service import get_youtube_service
    
    try:
        youtube = get_youtube_service()
        result = youtube.search(
            query=query,
            limit=min(limit, 20)
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "YOUTUBE_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_youtube_transcript(
    video_id: str,
    max_length: int = 10000
) -> str:
    """
    🎬 Get transcript/captions from a YouTube video
    
    Extracts the spoken content from a video. Perfect for:
    - Getting tutorial content without watching
    - Summarizing conference talks
    - Extracting key points from lectures
    - Research on video content
    
    Works with video IDs or full URLs:
    - "dQw4w9WgXcQ" (video ID)
    - "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    - "https://youtu.be/dQw4w9WgXcQ"
    
    Args:
        video_id: YouTube video ID or URL
        max_length: Maximum transcript length (default: 10000 chars)
    
    Returns:
        JSON with:
        - transcript: Full text of spoken content
        - language: Detected language
        - is_auto_generated: Whether captions are auto-generated
        - segments: Timestamped text segments
    
    Examples:
        Get transcript for a tutorial
        → get_youtube_transcript(video_id="abc123xyz")
        
        Get transcript from URL
        → get_youtube_transcript(video_id="https://www.youtube.com/watch?v=abc123xyz")
    """
    from .services.youtube_service import get_youtube_service
    
    try:
        youtube = get_youtube_service()
        result = youtube.get_transcript(
            video_id_or_url=video_id,
            max_length=max_length
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "YOUTUBE_TRANSCRIPT_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# ========== Learning & Education Tools ==========

@mcp.tool
async def search_udemy(
    query: str,
    level: Optional[str] = None,
    min_rating: float = 0.0,
    limit: int = 10,
    free_only: bool = False
) -> str:
    """
    📚 Search Udemy for online courses
    
    Find courses to learn new skills. Perfect for:
    - Learning programming languages
    - Mastering new frameworks
    - Professional development
    - Finding tutorials on specific topics
    
    Args:
        query: Topic or skill to learn (e.g., "Python async", "Kubernetes", "Machine Learning")
        level: Skill level filter (beginner, intermediate, expert, all)
        min_rating: Minimum course rating 0-5 (default: 0)
        limit: Maximum courses to return (default: 10)
        free_only: Only show free courses (default: False)
    
    Returns:
        JSON with courses including title, URL, rating, instructor
    
    Examples:
        Find Python courses
        → search_udemy(query="Python programming", level="beginner")
        
        Find highly-rated ML courses
        → search_udemy(query="machine learning", min_rating=4.5)
    """
    from .services.udemy_service import get_udemy_service
    
    try:
        udemy = get_udemy_service()
        result = udemy.search_courses(
            query=query,
            level=level,
            min_rating=min_rating,
            limit=limit,
            free_only=free_only
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "UDEMY_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_conferences(
    topic: Optional[str] = None,
    year: Optional[int] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 20,
    include_past: bool = False
) -> str:
    """
    🎤 Search for tech conferences
    
    Find upcoming tech conferences, meetups, and events. Great for:
    - Discovering conferences in your field
    - Finding CFP (Call for Papers) deadlines
    - Planning conference attendance
    - Networking opportunities
    
    Args:
        topic: Technology/field (python, javascript, ml, devops, kubernetes, etc.)
        year: Conference year (default: current year)
        country: Filter by country
        city: Filter by city
        limit: Maximum results (default: 20)
        include_past: Include past conferences (default: False)
    
    Returns:
        JSON with conferences including name, dates, location, CFP info
    
    Examples:
        Find Python conferences
        → search_conferences(topic="python")
        
        Find AI conferences in USA
        → search_conferences(topic="ml", country="USA")
        
        Find conferences in Berlin
        → search_conferences(city="Berlin")
    """
    from .services.conference_service import get_conference_service
    
    try:
        conf_service = get_conference_service()
        result = conf_service.search_conferences(
            topic=topic,
            year=year,
            country=country,
            city=city,
            limit=limit,
            include_past=include_past
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "CONFERENCE_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_newsletters(
    query: str,
    category: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    📰 Search for newsletters by topic
    
    Discover newsletters to stay informed. Great for:
    - Finding industry newsletters
    - Discovering new content creators
    - Building a reading list
    - Following specific topics
    
    Args:
        query: Topic or keyword (e.g., "AI", "startups", "Python")
        category: Category filter (technology, business, ai, etc.)
        limit: Maximum results (default: 10)
    
    Returns:
        JSON with newsletters including name, URL, author, platform
    
    Examples:
        Find AI newsletters
        → search_newsletters(query="artificial intelligence")
        
        Find tech business newsletters
        → search_newsletters(query="tech startups", category="business")
    """
    from .services.newsletter_service import get_newsletter_service
    
    try:
        newsletter_service = get_newsletter_service()
        result = newsletter_service.search_newsletters(
            query=query,
            category=category,
            limit=limit
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "NEWSLETTER_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_popular_newsletters(
    category: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    ⭐ Get popular/recommended newsletters
    
    Browse curated list of popular newsletters. Categories:
    - technology, business, ai, product, finance
    
    Args:
        category: Filter by category
        limit: Maximum results (default: 10)
    
    Returns:
        JSON with popular newsletters including subscriber counts
    """
    from .services.newsletter_service import get_newsletter_service
    
    try:
        newsletter_service = get_newsletter_service()
        result = newsletter_service.get_popular_newsletters(
            category=category,
            limit=limit
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "NEWSLETTER_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# ========== Entertainment Tools ==========

@mcp.tool
async def search_movies(
    query: str,
    content_type: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    🎬 Search for movies and TV shows
    
    Search IMDB for movies, series, and episodes. Fun for:
    - Finding movie info
    - Checking ratings before watching
    - Discovering related content
    - Correlating news with movies/documentaries
    
    Args:
        query: Movie or show title
        content_type: Filter by type (movie, series, episode)
        year: Filter by release year
        limit: Maximum results (default: 10)
    
    Returns:
        JSON with movies including title, year, type, IMDB ID
    
    Examples:
        Search for a movie
        → search_movies(query="Inception")
        
        Find TV series
        → search_movies(query="Breaking Bad", content_type="series")
        
        Find 2024 movies
        → search_movies(query="AI", year=2024, content_type="movie")
    
    Note: Requires OMDB_API_KEY environment variable (free at omdbapi.com)
    """
    from .services.imdb_service import get_imdb_service
    
    try:
        imdb = get_imdb_service()
        result = imdb.search_movies(
            query=query,
            content_type=content_type,
            year=year,
            limit=limit
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "IMDB_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_movie_details(
    imdb_id: Optional[str] = None,
    title: Optional[str] = None,
    year: Optional[int] = None
) -> str:
    """
    🎥 Get detailed movie/show information
    
    Get full details including plot, cast, ratings. Returns:
    - Plot summary, runtime, genre
    - Director, writer, actors
    - IMDB rating, Metascore, Rotten Tomatoes
    - Box office, awards
    
    Args:
        imdb_id: IMDB ID (e.g., "tt0111161" for Shawshank Redemption)
        title: Movie title (if no IMDB ID)
        year: Year to help disambiguation
    
    Returns:
        JSON with detailed movie information
    
    Examples:
        Get by IMDB ID
        → get_movie_details(imdb_id="tt0111161")
        
        Get by title
        → get_movie_details(title="The Matrix", year=1999)
    
    Note: Requires OMDB_API_KEY environment variable
    """
    from .services.imdb_service import get_imdb_service
    
    try:
        imdb = get_imdb_service()
        result = imdb.get_movie_details(
            imdb_id=imdb_id,
            title=title,
            year=year
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "IMDB_DETAILS_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_person(
    name: str,
    include_wikipedia: bool = True,
    limit: int = 5
) -> str:
    """
    👤 Search for actors, directors, and other celebrities
    
    Search IMDB for people in the entertainment industry.
    Optionally cross-references with Wikipedia for biography.
    
    No API key required - uses web scraping.
    
    Args:
        name: Person's name (e.g., "Tom Hanks", "Christopher Nolan")
        include_wikipedia: Include Wikipedia bio if available (default: True)
        limit: Maximum results (default: 5)
    
    Returns:
        JSON with:
        - name, IMDB ID, profile URL
        - profession (actor, director, etc.)
        - known_for: List of notable works
        - wikipedia: Summary and link if found
    
    Examples:
        Search for an actor
        → search_person(name="Leonardo DiCaprio")
        
        Search director without Wikipedia
        → search_person(name="Denis Villeneuve", include_wikipedia=False)
    """
    from .services.imdb_service import get_imdb_service
    
    try:
        imdb = get_imdb_service()
        result = imdb.search_person(
            name=name,
            include_wikipedia=include_wikipedia,
            limit=limit
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "PERSON_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_person_filmography(
    imdb_id: str,
    limit: int = 20
) -> str:
    """
    🎬 Get filmography for an actor or director
    
    Get the complete filmography for a person from IMDB.
    
    Args:
        imdb_id: IMDB person ID (e.g., "nm0000138" for Leonardo DiCaprio)
        limit: Maximum titles to return (default: 20)
    
    Returns:
        JSON with:
        - name, IMDB profile URL
        - filmography: List of movies/shows with titles, years, IDs
    
    Examples:
        Get Leonardo DiCaprio's filmography
        → get_person_filmography(imdb_id="nm0000138")
        
        Get Christopher Nolan's films
        → get_person_filmography(imdb_id="nm0634240", limit=10)
    """
    from .services.imdb_service import get_imdb_service
    
    try:
        imdb = get_imdb_service()
        result = imdb.get_person_filmography(
            imdb_id=imdb_id,
            limit=limit
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "FILMOGRAPHY_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_politician(
    name: str,
    party: Optional[str] = None,
    country: str = "de"
) -> str:
    """
    🏛️ Search for politicians (specializes in German politicians)
    
    Search for politicians with data from official sources like Bundestag.de
    and Wikipedia. Best results for German politicians (MdB).
    
    Args:
        name: Politician's name (e.g., "Olaf Scholz", "Friedrich Merz")
        party: Optional party filter (e.g., "SPD", "CDU", "Grüne")
        country: Country code ("de" for Germany, default)
    
    Returns:
        JSON with:
        - name, party, role
        - url: Link to official profile (Bundestag or Wikipedia)
        - photo, birth_date, electoral_district (when available)
        - Wikipedia summary if found
    
    Examples:
        Search German chancellor
        → search_politician(name="Olaf Scholz")
        
        Search CDU politicians
        → search_politician(name="Merz", party="CDU")
        
        Search any politician
        → search_politician(name="Angela Merkel")
    """
    from .services.people_service import get_people_service
    
    try:
        service = get_people_service()
        result = service.search_politician(
            name=name,
            party=party,
            country=country
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "POLITICIAN_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_people(
    name: str,
    person_type: Optional[str] = None,
    language: str = "de"
) -> str:
    """
    🔍 General people search across Wikipedia and official sources
    
    Search for any person using Wikipedia and specialized sources.
    For politicians, uses Bundestag.de as primary source.
    
    Args:
        name: Person's name to search
        person_type: Type hint - "politician", "bundestag", or None for general
        language: Primary language ("de" or "en", default: "de")
    
    Returns:
        JSON with:
        - name, type, source
        - url: Best available profile link
        - description, extract from Wikipedia
        - Additional fields depending on person type
    
    Examples:
        Search German person
        → search_people(name="Albert Einstein", language="de")
        
        Search for a Bundestag member
        → search_people(name="Habeck", person_type="bundestag")
    """
    from .services.people_service import get_people_service
    
    try:
        service = get_people_service()
        result = service.search_person(
            name=name,
            person_type=person_type,
            language=language
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "PEOPLE_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def meta_search(
    topic: str,
    related_terms: Optional[List[str]] = None,
    languages: Optional[List[str]] = None,
    max_results_per_query: int = 30,
    include_url: bool = True
) -> str:
    """
    Meta Search - Comprehensive research tool for news events and topics

    This is a high-level research tool that goes beyond simple search:
    1. Searches for the main topic across all supported platforms
    2. Optionally searches related terms to expand coverage
    3. Clusters similar articles to identify distinct news events/stories
    4. Analyzes coverage across platforms and languages
    5. Returns a research summary with key stories and insights

    Use this tool when you need to:
    - Research a complex topic with multiple angles
    - Find how different news sources cover an event
    - Identify the main stories/events within a topic
    - Compare international vs regional coverage
    - Get a comprehensive overview before deeper analysis

    Args:
        topic: Main topic or event to research
               Examples: "AI regulation", "Tesla layoffs", "climate summit", "election results"
        related_terms: Additional search terms to expand coverage (optional)
                      Examples for "AI regulation": ["artificial intelligence law", "OpenAI policy", "EU AI Act"]
                      This helps find articles that discuss the same topic but use different terminology
        languages: Filter by languages (optional)
                   - ["en"]: Only English sources
                   - ["en", "de"]: English and German
                   - None: All languages (default)
                   Available: en (English), de (German), fr (French), zh (Chinese), pt (Portuguese)
        max_results_per_query: Maximum results per search query (default 30)
        include_url: Include article URLs in results (default True)

    Returns:
        JSON with comprehensive research results:
        - topic: The searched topic
        - key_stories: Top stories identified with coverage count
        - clusters: Groups of related articles
        - platform_coverage: Which platforms covered this topic
        - language_coverage: Coverage by language
        - total_articles: Total unique articles found
        - search_queries: Statistics for each query

    Examples:
        User: "Research news about AI regulation"
        → meta_search(topic="AI regulation", related_terms=["artificial intelligence law", "EU AI Act"])

        User: "Find all coverage of the Tesla layoffs in English and German news"
        → meta_search(topic="Tesla layoffs", languages=["en", "de"])

        User: "What are the main stories about climate change this week?"
        → meta_search(topic="climate change", related_terms=["global warming", "COP29", "carbon emissions"])

        User: "Research how different countries cover the US election"
        → meta_search(topic="US election 2024", related_terms=["Trump", "Biden", "American politics"])
    """
    from .services.search_service import MetaSearchService
    
    try:
        search_service = MetaSearchService()
        
        result = search_service.research_topic(
            topic=topic,
            related_terms=related_terms,
            languages=languages,
            max_results_per_query=max_results_per_query,
            include_url=include_url
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "META_SEARCH_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# ==================== 翻译工具（可选功能）====================

@mcp.tool
async def translate_text(
    text: str,
    target: str = "en",
    source: str = "auto"
) -> str:
    """
    Translate text to another language using LibreTranslate (local service).
    
    This is an optional feature that requires LibreTranslate to be running locally.
    Start it with: cd libretranslate-upstream && docker compose up -d
    
    Args:
        text: Text to translate (single text or short paragraph)
        target: Target language code. Available:
                - en: English
                - de: German (Deutsch)
                - zh-Hans: Chinese Simplified (中文简体)
                - fr: French (Français)
                - es: Spanish (Español)
        source: Source language code, or "auto" for automatic detection (default)
    
    Returns:
        JSON with translation result:
        - success: Whether translation succeeded
        - original: Original text
        - translated: Translated text
        - source_language: Detected/specified source language
        - target_language: Target language
        - service_available: Whether translation service is running
    
    Examples:
        Translate German headline to English:
        → translate_text(text="Bundeskanzler kündigt neue Maßnahmen an", target="en")
        
        Translate English to Chinese:
        → translate_text(text="Breaking news from around the world", target="zh-Hans")
        
        Translate with known source language (faster):
        → translate_text(text="Hola mundo", source="es", target="en")
    """
    from .services.translation_service import get_translation_service
    
    try:
        service = get_translation_service()
        
        if not service.is_available():
            return json.dumps({
                "success": False,
                "service_available": False,
                "error": "Translation service not available. Start LibreTranslate with: cd libretranslate-upstream && docker compose up -d",
                "original": text
            }, ensure_ascii=False, indent=2)
        
        translated = service.translate(text, source=source, target=target)
        
        if translated:
            # Get detected language if auto
            detected = None
            if source == "auto":
                detection = service.detect_language(text)
                if detection:
                    detected = detection.get('language')
            
            return json.dumps({
                "success": True,
                "service_available": True,
                "original": text,
                "translated": translated,
                "source_language": detected or source,
                "target_language": target
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "service_available": True,
                "error": "Translation failed",
                "original": text
            }, ensure_ascii=False, indent=2)
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "original": text
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_translation_languages() -> str:
    """
    Get available languages for translation.
    
    Returns the list of supported languages and which translation pairs are available.
    Requires LibreTranslate to be running locally.
    
    Returns:
        JSON with available languages:
        - success: Whether service is available
        - languages: List of available languages with:
            - code: Language code (e.g., "en", "de", "zh-Hans")
            - name: Language name (e.g., "English", "German")
            - targets: Available target languages
        - service_available: Whether translation service is running
    
    Examples:
        Check what languages are available:
        → get_translation_languages()
    """
    from .services.translation_service import get_translation_service
    
    try:
        service = get_translation_service()
        
        if not service.is_available():
            return json.dumps({
                "success": False,
                "service_available": False,
                "error": "Translation service not available. Start LibreTranslate with: cd libretranslate-upstream && docker compose up -d",
                "languages": []
            }, ensure_ascii=False, indent=2)
        
        languages = service.get_languages()
        
        return json.dumps({
            "success": True,
            "service_available": True,
            "languages": languages,
            "language_count": len(languages)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "languages": []
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def translate_headlines(
    date_query: Optional[str] = "today",
    platforms: Optional[List[str]] = None,
    target_language: str = "en",
    limit: int = 20
) -> str:
    """
    Translate news headlines from cached data to a target language.
    
    This tool fetches headlines from the news cache and translates them.
    Useful for reading news from platforms in languages you don't understand.
    
    Args:
        date_query: Date to fetch headlines from (default: "today")
                   Supports: "today", "yesterday", "2025-11-29", etc.
        platforms: Platform IDs to include (default: all platforms)
                  Examples: ["spiegel", "lemonde", "folha", "elpais"]
        target_language: Language to translate to (default: "en")
                        Available: en, de, zh-Hans, fr, es
        limit: Maximum headlines to translate (default: 20)
    
    Returns:
        JSON with translated headlines:
        - success: Whether translation succeeded
        - headlines: List of headlines with original and translated text
        - source_platforms: Which platforms were included
        - target_language: Target language used
        - translation_count: Number of successfully translated headlines
    
    Examples:
        Translate today's German news to English:
        → translate_headlines(platforms=["spiegel", "heise"], target_language="en")
        
        Translate French news to Spanish:
        → translate_headlines(platforms=["lemonde"], target_language="es")
        
        Translate all non-English news from yesterday:
        → translate_headlines(date_query="yesterday", target_language="en", limit=30)
    """
    from .services.translation_service import get_translation_service
    
    try:
        service = get_translation_service()
        
        if not service.is_available():
            return json.dumps({
                "success": False,
                "service_available": False,
                "error": "Translation service not available. Start LibreTranslate with: cd libretranslate-upstream && docker compose up -d"
            }, ensure_ascii=False, indent=2)
        
        # Get headlines from data tools
        tools = _get_tools()
        news_result = tools['data'].get_news_by_date(
            date_query=date_query,
            platforms=platforms,
            limit=limit,
            include_url=True
        )
        
        if not news_result.get('success') or not news_result.get('data'):
            return json.dumps({
                "success": False,
                "error": "No headlines found for the specified date/platforms",
                "query": {
                    "date": date_query,
                    "platforms": platforms
                }
            }, ensure_ascii=False, indent=2)
        
        # Translate headlines
        translated_headlines = []
        for item in news_result['data'][:limit]:
            title = item.get('title', '')
            platform = item.get('platform', 'unknown')
            url = item.get('url', '')
            
            # Skip if empty
            if not title:
                continue
            
            # Translate
            translated = service.translate(title, source="auto", target=target_language)
            
            translated_headlines.append({
                "platform": platform,
                "original": title,
                "translated": translated or title,
                "url": url,
                "translation_success": translated is not None
            })
        
        success_count = sum(1 for h in translated_headlines if h['translation_success'])
        
        return json.dumps({
            "success": True,
            "service_available": True,
            "headlines": translated_headlines,
            "target_language": target_language,
            "translation_count": success_count,
            "total_headlines": len(translated_headlines),
            "source_platforms": list(set(h['platform'] for h in translated_headlines))
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


# ==================== 配置与系统管理工具 ====================

@mcp.tool
async def get_current_config(
    section: str = "all"
) -> str:
    """
    获取当前系统配置

    Args:
        section: 配置节，可选值：
            - "all": 所有配置（默认）
            - "crawler": 爬虫配置
            - "push": 推送配置
            - "keywords": 关键词配置
            - "weights": 权重配置

    Returns:
        JSON格式的配置信息
    """
    tools = _get_tools()
    result = tools['config'].get_current_config(section=section)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_system_status() -> str:
    """
    获取系统运行状态和健康检查信息

    返回系统版本、数据统计、缓存状态等信息

    Returns:
        JSON格式的系统状态信息
    """
    tools = _get_tools()
    result = tools['system'].get_system_status()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def trigger_crawl(
    platforms: List[str] = None,
    save_to_local: bool = False,
    include_url: bool = False,
    debug: bool = False
) -> str:
    """
    手动触发一次爬取任务（可选持久化）

    Args:
        platforms: 指定平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"Zhihu"、"Weibo"），方便AI识别
                   - 注意：失败的平台会在返回结果的 failed_platforms 字段中列出
        save_to_local: 是否保存到本地 output 目录，默认 False
        include_url: 是否包含URL链接，默认False（节省token）
        debug: 是否启用调试模式，默认False（启用时输出详细的爬取日志）

    Returns:
        JSON格式的任务状态信息，包含：
        - platforms: 成功爬取的平台列表
        - failed_platforms: 失败的平台列表（如有）
        - total_news: 爬取的新闻总数
        - data: 新闻数据
        - debug_info: 调试信息（仅当debug=True时包含）

    Examples:
        - 临时爬取: trigger_crawl(platforms=['zhihu'])
        - 爬取并保存: trigger_crawl(platforms=['weibo'], save_to_local=True)
        - 使用默认平台: trigger_crawl()  # 爬取config.yaml中配置的所有平台
        - 调试模式: trigger_crawl(platforms=['theguardian'], debug=True)
    """
    print(f"🔄 MCP trigger_crawl called - platforms: {platforms or 'all'}, save_to_local: {save_to_local}, debug: {debug}")
    
    tools = _get_tools()
    result = tools['system'].trigger_crawl(platforms=platforms, save_to_local=save_to_local, include_url=include_url, debug=debug)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Woodchuck News 页面索引 ====================

@mcp.tool
async def get_woodchuck_pages(
    page_type: Optional[str] = None,
    region: Optional[str] = None,
    language: Optional[str] = None
) -> str:
    """
    获取 Woodchuck News 静态网站的页面索引

    此工具返回所有可用的静态页面，便于向用户推荐相关内容。

    Args:
        page_type: 按页面类型过滤，可选值：
            - "home": 首页
            - "date": 按日期分类的页面
            - "region": 按地区分类的页面
            - "language": 按语言分类的页面
            - "source": 单个新闻源页面
            - "sources_index": 新闻源索引页
        region: 按地区过滤，可选值：europe, asia, americas, middle_east, eurasia, oceania, other
        language: 按语言过滤，可选值：en, de, zh, ja, ko, es, ar

    Returns:
        JSON格式的页面列表，包含：
        - path: 页面路径
        - title: 页面标题
        - type: 页面类型
        - description: 页面描述
        - headline_count: 新闻数量（如适用）

    Examples:
        - 获取所有页面: get_woodchuck_pages()
        - 获取日期页面: get_woodchuck_pages(page_type="date")
        - 获取欧洲新闻页面: get_woodchuck_pages(region="europe")
        - 获取中文新闻页面: get_woodchuck_pages(language="zh")
    """
    import os
    from pathlib import Path
    
    # Try to find pages_index.json
    possible_paths = [
        Path(os.path.dirname(__file__)).parent / "woodchuck-news" / "output" / "pages_index.json",
        Path("/app/woodchuck-news/output/pages_index.json"),
        Path("./woodchuck-news/output/pages_index.json"),
    ]
    
    index_path = None
    for p in possible_paths:
        if p.exists():
            index_path = p
            break
    
    if not index_path:
        return json.dumps({
            "success": False,
            "error": "pages_index.json not found. Run the Woodchuck News generator first.",
            "searched_paths": [str(p) for p in possible_paths]
        }, ensure_ascii=False, indent=2)
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        pages = index_data.get("pages", [])
        
        # Apply filters
        if page_type:
            pages = [p for p in pages if p.get("type") == page_type]
        if region:
            pages = [p for p in pages if p.get("region") == region]
        if language:
            pages = [p for p in pages if p.get("language") == language]
        
        return json.dumps({
            "success": True,
            "generated_at": index_data.get("generated_at"),
            "total_pages": len(pages),
            "pages": pages,
            "filters_applied": {
                "page_type": page_type,
                "region": region,
                "language": language
            }
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error reading pages_index.json: {str(e)}"
        }, ensure_ascii=False, indent=2)


# ==================== 启动入口 ====================

def run_server(
    project_root: Optional[str] = None,
    transport: str = 'stdio',
    host: str = '0.0.0.0',
    port: int = 3333
):
    """
    启动 MCP 服务器

    Args:
        project_root: 项目根目录路径
        transport: 传输模式，'stdio' 或 'http'
        host: HTTP模式的监听地址，默认 0.0.0.0
        port: HTTP模式的监听端口，默认 3333
    """
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # 记录服务器启动时间
    startup_time = datetime.now()
    logger.info(f"TrendRadar MCP Server starting at {startup_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化工具实例
    _get_tools(project_root)

    # 打印启动信息
    print()
    print("=" * 60)
    print("  TrendRadar MCP Server - FastMCP 2.0")
    print("=" * 60)
    print(f"  传输模式: {transport.upper()}")

    if transport == 'stdio':
        print("  协议: MCP over stdio (标准输入输出)")
        print("  说明: 通过标准输入输出与 MCP 客户端通信")
    elif transport == 'http':
        print(f"  协议: MCP over HTTP (生产环境)")
        print(f"  服务器监听: {host}:{port}")

    if project_root:
        print(f"  项目目录: {project_root}")
    else:
        print("  项目目录: 当前目录")

    print()
    print("  已注册的工具:")
    print("    === 日期解析工具（推荐优先调用）===")
    print("    0. resolve_date_range       - 解析自然语言日期为标准格式")
    print()
    print("    === 基础数据查询（P0核心）===")
    print("    1. get_latest_news        - 获取最新新闻")
    print("    2. get_news_by_date       - 按日期查询新闻（支持自然语言）")
    print("    3. get_trending_topics    - 获取趋势话题")
    print()
    print("    === 智能检索工具 ===")
    print("    4. search_news                  - 统一新闻搜索（关键词/模糊/实体）")
    print("    5. search_related_news_history  - 历史相关新闻检索")
    print()
    print("    === 高级数据分析 ===")
    print("    6. analyze_topic_trend      - 统一话题趋势分析（热度/生命周期/爆火/预测）")
    print("    7. analyze_data_insights    - 统一数据洞察分析（平台对比/活跃度/关键词共现）")
    print("    8. analyze_sentiment        - 情感倾向分析")
    print("    9. find_similar_news        - 相似新闻查找")
    print("    10. generate_summary_report - 每日/每周摘要生成")
    print()
    print("    === 深度搜索工具 ===")
    print("    11. deep_search             - 深度搜索（直接查询新闻网站）")
    print("    12. meta_search             - 元搜索（多平台综合研究）")
    print()
    print("    === 翻译工具（可选 - 需要LibreTranslate）===")
    print("    13. translate_text          - 翻译文本")
    print("    14. get_translation_languages - 获取支持的语言")
    print("    15. translate_headlines     - 翻译新闻标题")
    print()
    print("    === 配置与系统管理 ===")
    print("    16. get_current_config      - 获取当前系统配置")
    print("    17. get_system_status       - 获取系统运行状态")
    print("    18. trigger_crawl           - 手动触发爬取任务")
    print("=" * 60)
    print()

    # 设置信号处理器用于优雅关闭
    def signal_handler(signum, frame):
        shutdown_time = datetime.now()
        logger.info(f"TrendRadar MCP Server shutting down at {shutdown_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Server uptime: {shutdown_time - startup_time}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 根据传输模式运行服务器
        if transport == 'stdio':
            logger.info("Starting MCP server in stdio mode")
            mcp.run(transport='stdio')
        elif transport == 'http':
            # HTTP 模式（生产推荐）
            logger.info(f"Starting MCP server in HTTP mode on {host}:{port}")
            mcp.run(
                transport='http',
                host=host,
                port=port,
                path='/mcp'  # HTTP 端点路径
            )
        else:
            raise ValueError(f"不支持的传输模式: {transport}")
    except KeyboardInterrupt:
        shutdown_time = datetime.now()
        logger.info(f"TrendRadar MCP Server shutting down at {shutdown_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Server uptime: {shutdown_time - startup_time}")
    except Exception as e:
        shutdown_time = datetime.now()
        logger.error(f"TrendRadar MCP Server encountered error at {shutdown_time.strftime('%Y-%m-%d %H:%M:%S')}: {e}")
        logger.info(f"Server uptime before error: {shutdown_time - startup_time}")
        raise


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='TrendRadar MCP Server - 新闻热点聚合 MCP 工具服务器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
详细配置教程请查看: README-Cherry-Studio.md
        """
    )
    parser.add_argument(
        '--transport',
        choices=['stdio', 'http'],
        default='stdio',
        help='传输模式：stdio (默认) 或 http (生产环境)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='HTTP模式的监听地址，默认 0.0.0.0'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=3333,
        help='HTTP模式的监听端口，默认 3333'
    )
    parser.add_argument(
        '--project-root',
        help='项目根目录路径'
    )

    args = parser.parse_args()

    run_server(
        project_root=args.project_root,
        transport=args.transport,
        host=args.host,
        port=args.port
    )
