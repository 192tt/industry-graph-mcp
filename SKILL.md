---
name: industry-graph-research
description: >
  Local industry knowledge-graph survey. Discover companies, enrich full profiles
  on ingest, export Beijing-style Chinese CSV, then write policy+insight reports.
---

# 产业图谱调研 Skill

## 目标

1. **尽可能多**入库公开源企业  
2. **入库时就补全档案**：电话、信用代码、法人、成立日期、注册资本、地址、产品、专利、资质等（公开网页能拿到的）  
3. 同步写出标准中文表头 CSV：`data/csv/{scope}.csv`  
4. **`generate_insight_report`** → Markdown 主报告（政策解读 + 产业洞察）

## 流程

1. `survey_plan_tool` → `discover_companies(maximize=True)`  
2. `graph_upsert_companies_batch(..., enrich_profile=True)`（默认开启：一家企业尽量补全字段）  
3. 旧数据：反复 `enrich_company_profiles(scope, limit=50)` 直到 `updated=0`  
4. `graph_export_csv(scope)` 可随时重导 CSV  
5. `generate_insight_report(scope, region, industry)` → `REPORT.md`

## 标准 CSV 表头

序号、企业名称、联系电话、统一社会信用代码、法人、成立日期、注册资本(万)、所属区县、注册街道、注册地址、核心技术/产品/服务、产业链、细分小类、所获专利、单位资质、获得荣誉、企业风险、分类理由、数据来源、筛选标记

## 口径

公开检索 ≠ 工商全量 / 付费企业库；字段可能仍为空；政策摘要须核对原文。
