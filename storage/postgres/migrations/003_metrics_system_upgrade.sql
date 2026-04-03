-- ============================================================
-- 指标体系升级 — 新增 Page/HttpRequest + 全面指标体系
-- 基于 Golden Signals + OTel Semantic Conventions
-- ============================================================

-- 1. 新增实体类型：Page
INSERT INTO entity_type_def (type_name, display_name, category, icon, description, definition) VALUES
('Page', '前端页面', 'frontend', 'page', '浏览器页面/SPA路由',
'{
  "attributes": [
    {"key":"url_pattern","name":"URL模式","type":"string","required":true},
    {"key":"app_name","name":"所属应用","type":"string","required":false},
    {"key":"framework","name":"前端框架","type":"string","required":false},
    {"key":"team","name":"负责团队","type":"string","required":false}
  ],
  "metrics": [
    {"name":"page.load.time.p50","display":"P50加载时间","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":3000,"crit":6000}},
    {"name":"page.load.time.p99","display":"P99加载时间","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":8000,"crit":15000}},
    {"name":"page.fcp.time","display":"FCP","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":2000,"crit":4000}},
    {"name":"page.lcp.time","display":"LCP","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":2500,"crit":4000}},
    {"name":"page.cls.score","display":"CLS","type":"gauge","unit":"score","category":"stability","thresholds":{"warn":0.1,"crit":0.25}},
    {"name":"page.fid.time","display":"FID","type":"gauge","unit":"ms","category":"interactivity","thresholds":{"warn":100,"crit":300}},
    {"name":"page.view.count","display":"PV","type":"counter","unit":"count/min","category":"traffic"},
    {"name":"page.js.error.rate","display":"JS异常率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}}
  ],
  "relations": [
    {"type":"sends","direction":"out","target":"HttpRequest","dimension":"horizontal"}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"loading","metric":"page.load.time.p99","weight":0.35,"category":"performance"},
    {"name":"stability","metric":"page.cls.score","weight":0.20,"category":"stability"},
    {"name":"errors","metric":"page.js.error.rate","weight":0.25,"category":"error"},
    {"name":"interactivity","metric":"page.fid.time","weight":0.20,"category":"interactivity"}
  ]}}')
ON CONFLICT (type_name) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  definition = EXCLUDED.definition,
  description = EXCLUDED.description;

-- 2. 新增实体类型：HttpRequest
INSERT INTO entity_type_def (type_name, display_name, category, icon, description, definition) VALUES
('HttpRequest', '网络请求', 'frontend', 'request', '浏览器XHR/Fetch请求',
'{
  "attributes": [
    {"key":"url_pattern","name":"URL模式","type":"string","required":true},
    {"key":"http_method","name":"HTTP方法","type":"string","required":true},
    {"key":"target_service","name":"目标服务","type":"string","required":false},
    {"key":"business_domain","name":"业务域","type":"string","required":false},
    {"key":"business_action","name":"业务动作","type":"string","required":false},
    {"key":"geo_region","name":"用户地域","type":"string","required":false},
    {"key":"isp","name":"运营商","type":"string","required":false}
  ],
  "metrics": [
    {"name":"xhr.timing.total","display":"总耗时","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":2000,"crit":5000}},
    {"name":"xhr.timing.dns","display":"DNS解析","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":100,"crit":500}},
    {"name":"xhr.timing.tcp","display":"TCP握手","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":100,"crit":300}},
    {"name":"xhr.timing.ssl","display":"SSL握手","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":200,"crit":500}},
    {"name":"xhr.timing.ttfb","display":"TTFB","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":800,"crit":2000}},
    {"name":"xhr.timing.download","display":"下载耗时","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":1000,"crit":3000}},
    {"name":"xhr.timing.queue","display":"排队耗时","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":500,"crit":1000}},
    {"name":"xhr.request.count","display":"请求次数","type":"counter","unit":"count/min","category":"traffic"},
    {"name":"xhr.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}},
    {"name":"xhr.request.size","display":"请求体大小","type":"gauge","unit":"bytes","category":"payload"},
    {"name":"xhr.response.size","display":"响应体大小","type":"gauge","unit":"bytes","category":"payload"}
  ],
  "relations": [
    {"type":"calls","direction":"out","target":"Service.Endpoint","dimension":"horizontal"}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"latency","metric":"xhr.timing.total","weight":0.35,"category":"latency"},
    {"name":"ttfb","metric":"xhr.timing.ttfb","weight":0.25,"category":"latency"},
    {"name":"errors","metric":"xhr.request.error_rate","weight":0.25,"category":"error"},
    {"name":"dns","metric":"xhr.timing.dns","weight":0.15,"category":"latency"}
  ]}}')
ON CONFLICT (type_name) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  definition = EXCLUDED.definition,
  description = EXCLUDED.description;

-- 3. 新增关系类型
INSERT INTO relationship_type_def (type_name, end1_type, end1_name, end2_type, end2_name, description) VALUES
  ('sends', 'Page', 'page', 'HttpRequest', 'request', '页面发送网络请求'),
  ('loads', 'Page', 'from_page', 'Page', 'to_page', '页面跳转'),
  ('calls', 'HttpRequest', 'request', 'Endpoint', 'endpoint', '请求调用接口端点')
ON CONFLICT (type_name) DO NOTHING;
