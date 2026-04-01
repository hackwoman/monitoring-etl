-- ============================================================
-- CMDB 关系模型增强 — Step 2+3
-- 日期: 2026-04-01
-- 目标: 关系增加过期/确认字段 + 关系类型约束完善
-- ============================================================

-- 关系表增加字段
ALTER TABLE relationship ADD COLUMN IF NOT EXISTS expired_at TIMESTAMPTZ;
ALTER TABLE relationship ADD COLUMN IF NOT EXISTS verified_by VARCHAR(128);
ALTER TABLE relationship ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

-- 完善关系类型定义（增加约束）
UPDATE relationship_type_def SET
    end1_type = 'Service', end2_type = 'Service',
    description = '服务间同步调用（横向）'
WHERE type_name = 'calls';

UPDATE relationship_type_def SET
    end1_type = 'Service', end2_type = 'Database',
    description = '服务依赖数据库（横向）'
WHERE type_name = 'depends_on' AND end2_type = 'Database';

-- 清理重复的 depends_on
DELETE FROM relationship_type_def WHERE type_name = 'depends_on' AND end2_type = 'db';

-- 插入缺失的关系类型定义
INSERT INTO relationship_type_def (type_name, end1_type, end2_type, end1_name, end2_name, description) VALUES
    ('has_endpoint', 'Service', 'Endpoint', 'service', 'endpoint', '服务提供接口'),
    ('belongs_to', 'Endpoint', 'Service', 'endpoint', 'service', '接口归属服务'),
    ('async_calls', 'Service', 'Service', 'caller', 'callee', '服务间异步调用(MQ)')
ON CONFLICT (type_name) DO NOTHING;

-- 为 dimension 列添加注释
COMMENT ON COLUMN relationship.dimension IS 'horizontal=横向调用链(Trace驱动), vertical=纵向归属树(CMDB驱动)';
COMMENT ON COLUMN relationship.source IS 'manual=人工创建, trace_discovered=Trace发现, imported=批量导入, auto_discovered=自动发现';
COMMENT ON COLUMN relationship.confidence IS '置信度: 1.0=人工确认/CMDB, 0.9=Trace确认, <0.9=自动推断';
COMMENT ON COLUMN relationship.expired_at IS '关系过期时间, 用于自动清理过期关系';
COMMENT ON COLUMN relationship.verified_by IS '人工确认关系存在的操作者';
COMMENT ON COLUMN relationship.verified_at IS '关系被人工确认的时间';

-- 实体表增加注释
COMMENT ON COLUMN entity.health_score IS '健康评分 0-100';
COMMENT ON COLUMN entity.health_level IS 'healthy>=80 / warning>=60 / critical>=30 / down<30';
COMMENT ON COLUMN entity.risk_score IS '业务风险度 0-100 (健康度差 × 业务权重 × 影响范围)';
COMMENT ON COLUMN entity.propagation_hops IS '到用户端点的最短传播跳数';
COMMENT ON COLUMN entity.blast_radius IS '该实体故障会影响的下游实体数量';

SELECT '关系模型增强完成' as status;
