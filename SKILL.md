---
name: industry-graph-research
description: >
  Local industry knowledge-graph survey. Maximize public company coverage,
  enrich fields, then generate Markdown reports: 产业政策解读 + 产业样本洞察.
---

# 产业图谱调研 Skill

## 目标

1. **尽可能多**入库公开源企业  
2. 补全 **sub_industry / role**  
3. **`generate_insight_report`** → Markdown 主报告（政策解读模板 + 产业洞察）

## 流程

1. `survey_plan_tool` → `discover_companies(maximize=True)` → `graph_upsert_companies_batch`  
2. 缺字段：`graph_enrich_fields(scope)`  
3. 可选：`search_policies` 后把结果传入 `policies_json`  
4. **`generate_insight_report(scope, region, industry)`** → `REPORT.md`

## 报告模板（契约）

融合国内产业政策解读 + 产业/招商研究常用模块：

0. 执行摘要与口径  
1. 政策概述（机关/文件/链接/摘要表）  
2. 政策背景与意图（Why）  
3. 政策核心内容（措施/目标/支持/约束）  
4. 区域产业样本全景（统计图 + Mermaid + 知识图谱）  
5. 影响分析（政策 × 样本细分/企业/空间）  
6. 代表企业与赛道速览  
7. 应对建议（战略/行动/风险/下一步）  
附录：方法、口径、政策清单  

产物：`D:\industry-graph-mcp\reports\{scope}\*_insight\REPORT.md`

## 口径

公开检索 ≠ 工商全量；政策摘要须核对原文；名称推断 ≠ 官方分类。
