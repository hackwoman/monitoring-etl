-- ============================================================
-- Demo 数据生成 — 验证所有新功能
-- 14 种实体类型完整数据
-- ============================================================

-- 清空旧数据
DELETE FROM relationship;
DELETE FROM entity;
DELETE FROM alert_instance;

-- ============================================================
-- 实体类型定义 — 确保所有类型存在
-- ============================================================
DELETE FROM entity_type_def;

INSERT INTO entity_type_def (type_name, display_name, category, icon, description, definition) VALUES
('Business', '业务服务', 'business', 'apartment', '顶层业务服务', '{
  "attributes": [
    {"key":"business_domain","name":"业务域","type":"string","required":false},
    {"key":"team","name":"负责团队","type":"string","required":false}
  ],
  "metrics": [
    {"name":"business.conversion.rate","display":"转化率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":95,"crit":90}},
    {"name":"business.success.rate","display":"成功率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":99,"crit":95}},
    {"name":"business.throughput","display":"吞吐量","type":"gauge","unit":"count/min","category":"business"}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"business_domain","name":"业务域","source":"attribute","cardinality":"low","default":true}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"success","metric":"business.success.rate","weight":0.6,"category":"business"},
    {"name":"conversion","metric":"business.conversion.rate","weight":0.4,"category":"business"}
  ]}}'),

('Service', '微服务', 'application', 'api', '微服务', '{
  "attributes": [
    {"key":"language","name":"编程语言","type":"string","required":false},
    {"key":"framework","name":"框架","type":"string","required":false},
    {"key":"port","name":"端口","type":"number","required":false},
    {"key":"team","name":"团队","type":"string","required":false}
  ],
  "metrics": [
    {"name":"http.server.request.duration.p50","display":"P50延迟","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":200,"crit":800}},
    {"name":"http.server.request.duration.p99","display":"P99延迟","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":500,"crit":2000}},
    {"name":"http.server.request.qps","display":"QPS","type":"gauge","unit":"count/s","category":"traffic"},
    {"name":"http.server.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}},
    {"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"saturation","thresholds":{"warn":70,"crit":90}},
    {"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"saturation","thresholds":{"warn":80,"crit":95}},
    {"name":"system.load.1m","display":"1分钟负载","type":"gauge","unit":"ratio","category":"saturation","thresholds":{"warn":0.7,"crit":1.0}},
    {"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","category":"saturation","thresholds":{"warn":70,"crit":90}}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":true},
    {"key":"language","name":"编程语言","source":"attribute","cardinality":"low","default":false},
    {"key":"framework","name":"框架","source":"attribute","cardinality":"low","default":false}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"latency","metric":"http.server.request.duration.p99","weight":0.3,"category":"latency"},
    {"name":"error","metric":"http.server.request.error_rate","weight":0.3,"category":"error"},
    {"name":"cpu","metric":"system.cpu.usage","weight":0.2,"category":"saturation"},
    {"name":"memory","metric":"system.memory.usage","weight":0.2,"category":"saturation"}
  ]}}'),

('Endpoint', 'API端点', 'application', 'api', 'HTTP接口', '{
  "attributes": [
    {"key":"method","name":"HTTP方法","type":"string","required":true},
    {"key":"path","name":"路径","type":"string","required":true}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"method","name":"HTTP方法","source":"attribute","cardinality":"low","default":true}
  ]}'),

('Host', '主机', 'infrastructure', 'desktop', '物理/虚拟主机', '{
  "attributes": [
    {"key":"os","name":"操作系统","type":"string","required":false},
    {"key":"ip","name":"IP","type":"string","required":false},
    {"key":"cloud_provider","name":"云厂商","type":"string","required":false},
    {"key":"instance_type","name":"实例规格","type":"string","required":false}
  ],
  "metrics": [
    {"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"compute","thresholds":{"warn":70,"crit":90}},
    {"name":"system.cpu.load.1m","display":"1分钟负载","type":"gauge","unit":"ratio","category":"saturation","thresholds":{"warn":0.7,"crit":1.0}},
    {"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":80,"crit":95}},
    {"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":80,"crit":90}},
    {"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":70,"crit":90}},
    {"name":"system.network.bytes_recv","display":"网络入流量","type":"gauge","unit":"MB/s","category":"network"},
    {"name":"system.network.packet.loss","display":"网络丢包率","type":"gauge","unit":"percent","category":"network","thresholds":{"warn":0.1,"crit":1.0}},
    {"name":"system.process.count","display":"进程数","type":"gauge","unit":"count","category":"resource","thresholds":{"warn":500,"crit":1000}},
    {"name":"system.file_descriptor.usage","display":"FD使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":95}}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"os","name":"操作系统","source":"attribute","cardinality":"low","default":false},
    {"key":"cloud_provider","name":"云厂商","source":"attribute","cardinality":"low","default":false}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"cpu","metric":"system.cpu.usage","weight":0.3,"category":"compute"},
    {"name":"memory","metric":"system.memory.usage","weight":0.3,"category":"memory"},
    {"name":"disk","metric":"system.disk.usage","weight":0.2,"category":"disk"},
    {"name":"fd","metric":"system.file_descriptor.usage","weight":0.2,"category":"resource"}
  ]}}'),

('NetworkDevice', '网络设备', 'infrastructure', 'cloud-server', '交换机/路由器/防火墙', '{
  "metrics": [
    {"name":"network.packet.loss","display":"丢包率","type":"gauge","unit":"percent","category":"quality","thresholds":{"warn":0.1,"crit":1.0}},
    {"name":"network.latency","display":"网络延迟","type":"gauge","unit":"ms","category":"quality","thresholds":{"warn":10,"crit":50}},
    {"name":"network.tcp.new_connections.rate","display":"新建连接速率","type":"gauge","unit":"count/s","category":"dynamic","thresholds":{"warn":1000,"crit":5000}},
    {"name":"network.tcp.retransmit.rate","display":"TCP重传率","type":"gauge","unit":"percent","category":"quality","thresholds":{"warn":1,"crit":5}},
    {"name":"network.device.cpu","display":"设备CPU","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":70,"crit":90}}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"vendor","name":"厂商","source":"attribute","cardinality":"low","default":true},
    {"key":"device_role","name":"设备角色","source":"attribute","cardinality":"low","default":true}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"packet_loss","metric":"network.packet.loss","weight":0.35,"category":"quality"},
    {"name":"latency","metric":"network.latency","weight":0.25,"category":"quality"},
    {"name":"error_rate","metric":"network.error.rate","weight":0.2,"category":"quality"},
    {"name":"utilization","metric":"network.bandwidth.utilization","weight":0.2,"category":"capacity"}
  ]}}'),

('MySQL', 'MySQL', 'middleware', 'database', 'MySQL数据库', '{
  "attributes": [
    {"key":"port","name":"端口","type":"number","required":false},
    {"key":"version","name":"版本","type":"string","required":false}
  ],
  "metrics": [
    {"name":"mysql.connections.active","display":"活跃连接","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":100,"crit":200}},
    {"name":"mysql.connections.usage_rate","display":"连接池使用率","type":"gauge","unit":"percent","category":"connections","thresholds":{"warn":80,"crit":95}},
    {"name":"mysql.queries.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},
    {"name":"mysql.queries.slow","display":"慢查询","type":"counter","unit":"count/min","category":"performance","thresholds":{"rate_warn":5,"rate_crit":20}},
    {"name":"mysql.replication.lag","display":"主从延迟","type":"gauge","unit":"seconds","category":"replication","thresholds":{"warn":10,"crit":60}},
    {"name":"mysql.innodb.row_lock.waited","display":"行锁等待","type":"gauge","unit":"ms","category":"locks","thresholds":{"warn":100,"crit":500}},
    {"name":"mysql.buffer_pool.hit_rate","display":"Buffer Pool命中率","type":"gauge","unit":"percent","category":"cache","thresholds":{"warn":95,"crit":90}}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":false}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"connections","metric":"mysql.connections.usage_rate","weight":0.25,"category":"connections"},
    {"name":"slow","metric":"mysql.queries.slow","weight":0.3,"category":"performance"},
    {"name":"replication","metric":"mysql.replication.lag","weight":0.25,"category":"replication"},
    {"name":"locks","metric":"mysql.innodb.row_lock.waited","weight":0.2,"category":"locks"}
  ]}}'),

('Redis', 'Redis', 'middleware', 'database', 'Redis缓存', '{
  "attributes": [
    {"key":"port","name":"端口","type":"number","required":false},
    {"key":"cluster_mode","name":"集群模式","type":"boolean","required":false}
  ],
  "metrics": [
    {"name":"redis.memory.usage","display":"内存使用","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":80,"crit":95}},
    {"name":"redis.commands.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},
    {"name":"redis.commands.avg_latency","display":"平均延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":1,"crit":5}},
    {"name":"redis.clients.connected","display":"已连接客户端","type":"gauge","unit":"count","category":"connections"},
    {"name":"redis.memory.fragmentation_ratio","display":"内存碎片率","type":"gauge","unit":"ratio","category":"memory","thresholds":{"warn":1.5,"crit":2.0}}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":false}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"memory","metric":"redis.memory.usage","weight":0.35,"category":"memory"},
    {"name":"latency","metric":"redis.commands.avg_latency","weight":0.35,"category":"performance"},
    {"name":"fragmentation","metric":"redis.memory.fragmentation_ratio","weight":0.3,"category":"memory"}
  ]}}'),

('Page', '前端页面', 'frontend', 'page', '浏览器页面/SPA路由', '{
  "attributes": [
    {"key":"url_pattern","name":"URL模式","type":"string","required":true},
    {"key":"app_name","name":"所属应用","type":"string","required":false},
    {"key":"framework","name":"前端框架","type":"string","required":false}
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
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"browser","name":"浏览器","source":"context","cardinality":"low","default":false},
    {"key":"device_type","name":"设备类型","source":"context","cardinality":"low","default":false}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"loading","metric":"page.load.time.p99","weight":0.35,"category":"performance"},
    {"name":"stability","metric":"page.cls.score","weight":0.2,"category":"stability"},
    {"name":"errors","metric":"page.js.error.rate","weight":0.25,"category":"error"},
    {"name":"interactivity","metric":"page.fid.time","weight":0.2,"category":"interactivity"}
  ]}}'),

('HttpRequest', '网络请求', 'frontend', 'request', '浏览器XHR/Fetch请求', '{
  "attributes": [
    {"key":"url_pattern","name":"URL模式","type":"string","required":true},
    {"key":"http_method","name":"HTTP方法","type":"string","required":true},
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
    {"name":"xhr.request.count","display":"请求次数","type":"counter","unit":"count/min","category":"traffic"},
    {"name":"xhr.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}}
  ],
  "dimensions": [
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"url_pattern","name":"URL模式","source":"attribute","cardinality":"medium","default":true},
    {"key":"http_method","name":"HTTP方法","source":"span_field","cardinality":"low","default":true},
    {"key":"geo_region","name":"用户地域","source":"attribute","cardinality":"medium","default":false},
    {"key":"isp","name":"运营商","source":"attribute","cardinality":"low","default":false},
    {"key":"business_domain","name":"业务域","source":"attribute","cardinality":"low","default":false}
  ],
  "health":{"method":"weighted_avg","dimensions":[
    {"name":"latency","metric":"xhr.timing.total","weight":0.35,"category":"latency"},
    {"name":"ttfb","metric":"xhr.timing.ttfb","weight":0.25,"category":"latency"},
    {"name":"errors","metric":"xhr.request.error_rate","weight":0.25,"category":"error"},
    {"name":"dns","metric":"xhr.timing.dns","weight":0.15,"category":"latency"}
  ]}}'),

('Database', '数据库', 'database', 'database', '通用数据库', '{}'),
('Middleware', '中间件', 'middleware', 'cloud-server', '通用中间件', '{}'),
('K8sCluster', 'K8s集群', 'runtime', 'cluster', 'Kubernetes集群', '{}'),
('K8sPod', 'K8s Pod', 'runtime', 'container', 'Kubernetes Pod', '{}'),
('IP', 'IP地址', 'infrastructure', 'global', 'IP地址', '{}');
