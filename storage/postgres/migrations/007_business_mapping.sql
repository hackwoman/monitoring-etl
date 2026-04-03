-- ============================================================
-- 业务映射规则表 — URL 模式 → 业务标签
-- ============================================================

CREATE TABLE IF NOT EXISTS business_mapping (
    mapping_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url_pattern     VARCHAR(512) NOT NULL,          -- URL 模式（支持 * 通配符）
    http_method     VARCHAR(16),                    -- HTTP 方法（可选，NULL=所有方法）
    business_domain VARCHAR(128),                   -- 业务域：交易/用户/库存
    business_action VARCHAR(128),                   -- 业务动作：下单/支付/查询
    biz_service     VARCHAR(256),                   -- 关联业务服务
    priority        INT DEFAULT 0,                  -- 优先级（高的先匹配）
    enabled         BOOLEAN DEFAULT true,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 预置业务映射规则
INSERT INTO business_mapping (url_pattern, http_method, business_domain, business_action, biz_service, priority, description) VALUES
    ('/api/pay/*',     'POST', '交易', '支付',      '在线支付', 10, '支付接口'),
    ('/api/order/*',   'POST', '交易', '创建订单',   '在线支付', 10, '订单接口'),
    ('/api/user/*',    NULL,   '账户', '用户操作',   '用户注册', 5,  '用户相关接口'),
    ('/api/inventory/*', 'GET', '库存', '库存查询',   '在线支付', 5,  '库存查询接口'),
    ('/api/products/*',  NULL,  '商品', '商品操作',   '在线支付', 5,  '商品相关接口'),
    ('/api/auth/*',      NULL,  '账户', '认证',       '用户注册', 10, '认证接口'),
    ('/api/cart/*',      'POST', '交易', '加购',       '在线支付', 8,  '购物车接口'),
    ('/api/shipping/*',  NULL,  '物流', '物流操作',   '在线支付', 5,  '物流接口')
ON CONFLICT DO NOTHING;

-- 索引
CREATE INDEX IF NOT EXISTS idx_biz_mapping_pattern ON business_mapping (url_pattern, http_method);
CREATE INDEX IF NOT EXISTS idx_biz_mapping_enabled ON business_mapping (enabled);
