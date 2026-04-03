-- ============================================================
-- 维度体系定义 — 所有实体类型添加 dimensions
-- ============================================================

-- Page
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":false},
    {"key":"app_name","name":"所属应用","source":"attribute","cardinality":"medium","default":false},
    {"key":"browser","name":"浏览器","source":"context","cardinality":"low","default":false},
    {"key":"device_type","name":"设备类型","source":"context","cardinality":"low","default":false}
  ]') WHERE type_name = 'Page';

-- HttpRequest
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"url_pattern","name":"URL模式","source":"attribute","cardinality":"medium","default":true},
    {"key":"http_method","name":"HTTP方法","source":"span_field","cardinality":"low","default":true},
    {"key":"http_status","name":"状态码","source":"span_field","cardinality":"low","default":false},
    {"key":"geo_region","name":"用户地域","source":"attribute","cardinality":"medium","default":false},
    {"key":"isp","name":"运营商","source":"attribute","cardinality":"low","default":false},
    {"key":"network_type","name":"网络类型","source":"context","cardinality":"low","default":false},
    {"key":"business_domain","name":"业务域","source":"attribute","cardinality":"low","default":false},
    {"key":"browser","name":"浏览器","source":"context","cardinality":"low","default":false},
    {"key":"device_type","name":"设备类型","source":"context","cardinality":"low","default":false}
  ]') WHERE type_name = 'HttpRequest';

-- Service
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":true},
    {"key":"language","name":"编程语言","source":"attribute","cardinality":"low","default":false},
    {"key":"framework","name":"框架","source":"attribute","cardinality":"low","default":false},
    {"key":"version","name":"版本号","source":"label","cardinality":"medium","default":false},
    {"key":"http_method","name":"HTTP方法","source":"span_field","cardinality":"low","default":false},
    {"key":"endpoint","name":"接口路径","source":"span_field","cardinality":"high","default":false},
    {"key":"http_status","name":"状态码","source":"span_field","cardinality":"low","default":false}
  ]') WHERE type_name = 'Service';

-- Host
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":true},
    {"key":"os","name":"操作系统","source":"attribute","cardinality":"low","default":false},
    {"key":"cloud_provider","name":"云厂商","source":"attribute","cardinality":"low","default":false},
    {"key":"instance_type","name":"实例规格","source":"attribute","cardinality":"medium","default":false},
    {"key":"vendor","name":"厂商","source":"attribute","cardinality":"low","default":false}
  ]') WHERE type_name = 'Host';

-- NetworkDevice
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"vendor","name":"厂商","source":"attribute","cardinality":"low","default":true},
    {"key":"device_role","name":"设备角色","source":"attribute","cardinality":"low","default":true},
    {"key":"port","name":"端口号","source":"attribute","cardinality":"high","default":false},
    {"key":"firmware_version","name":"固件版本","source":"attribute","cardinality":"medium","default":false}
  ]') WHERE type_name = 'NetworkDevice';

-- MySQL
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":false},
    {"key":"db_version","name":"数据库版本","source":"attribute","cardinality":"low","default":false},
    {"key":"replication_mode","name":"复制模式","source":"attribute","cardinality":"low","default":false}
  ]') WHERE type_name = 'MySQL';

-- Redis
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":false},
    {"key":"redis_version","name":"Redis版本","source":"attribute","cardinality":"low","default":false},
    {"key":"cluster_mode","name":"集群模式","source":"attribute","cardinality":"low","default":false}
  ]') WHERE type_name = 'Redis';

-- Business
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"business_domain","name":"业务域","source":"attribute","cardinality":"low","default":true}
  ]') WHERE type_name = 'Business';

-- Endpoint
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"method","name":"HTTP方法","source":"attribute","cardinality":"low","default":true},
    {"key":"service","name":"所属服务","source":"attribute","cardinality":"medium","default":false},
    {"key":"http_status","name":"状态码","source":"span_field","cardinality":"low","default":false}
  ]') WHERE type_name = 'Endpoint';

-- Database / Middleware / K8sCluster / K8sPod / IP — 基础维度
UPDATE entity_type_def SET definition = jsonb_set(
  definition, '{dimensions}', '[
    {"key":"env","name":"环境","source":"label","cardinality":"low","default":true},
    {"key":"region","name":"地域","source":"label","cardinality":"low","default":true},
    {"key":"team","name":"团队","source":"label","cardinality":"low","default":false}
  ]') WHERE type_name IN ('Database', 'Middleware', 'K8sCluster', 'K8sPod', 'IP');
