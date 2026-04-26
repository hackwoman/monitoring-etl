"""
Phase 5: 智能 ETL API 端点
提供数据格式识别、字段解析、实体推断的 REST API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter()

# 导入智能 ETL 引擎
from app.smart_etl_engine import SmartETLEngine

engine = SmartETLEngine()


class DataSampleRequest(BaseModel):
    data: str
    source_system: str = "unknown"


class BatchProcessRequest(BaseModel):
    data_samples: list  # [{"data": "...", "source_system": "..."}]
    auto_register: bool = False


@router.post("/etl/identify")
async def identify_format(body: DataSampleRequest):
    """识别数据格式"""
    result = engine.process(body.data, body.source_system)
    return {
        "format": result["format"],
        "confidence": result["confidence"],
        "description": result["description"],
        "entities_found": len(result["entities"]),
        "metrics_count": result["metrics_count"],
    }


@router.post("/etl/parse")
async def parse_data(body: DataSampleRequest):
    """解析数据并推断实体"""
    result = engine.process(body.data, body.source_system)
    return {
        "format": result["format"],
        "confidence": result["confidence"],
        "entities": result["entities"],
        "metrics_count": result["metrics_count"],
        "labels": result["labels"],
        "sample_records": result["raw_records"],
    }


@router.post("/etl/batch")
async def batch_process(body: BatchProcessRequest):
    """批量处理多个数据源"""
    results = []
    for sample in body.data_samples:
        result = engine.process(sample["data"], sample.get("source_system", "unknown"))
        results.append({
            "source_system": sample.get("source_system", "unknown"),
            "format": result["format"],
            "confidence": result["confidence"],
            "entities": result["entities"],
            "metrics_count": result["metrics_count"],
        })
    
    # 汇总统计
    total_entities = sum(len(r["entities"]) for r in results)
    total_metrics = sum(r["metrics_count"] for r in results)
    formats_found = list(set(r["format"] for r in results))
    
    return {
        "total_sources": len(results),
        "total_entities": total_entities,
        "total_metrics": total_metrics,
        "formats_found": formats_found,
        "results": results,
    }



@router.get("/etl/supported-formats")
async def list_supported_formats():
    """列出支持的数据格式"""
    return {
        "formats": [
            {"name": "prometheus", "description": "Prometheus 指标格式", "extensions": [".prom", ".prometheus"]},
            {"name": "json_lines", "description": "JSON Lines 格式", "extensions": [".jsonl", ".log"]},
            {"name": "csv", "description": "CSV/TSV 表格格式", "extensions": [".csv", ".tsv"]},
            {"name": "logfmt", "description": "Logfmt 键值对格式", "extensions": [".log"]},
            {"name": "syslog", "description": "Syslog 标准格式", "extensions": [".log"]},
            {"name": "key_value", "description": "Key:Value 键值对格式", "extensions": [".log", ".txt"]},
        ]
    }
