-- ============================================================
-- CMDB 指标体系 + 属性元数据增强 — Step 1
-- 日期: 2026-04-01
-- 目标: 每种实体类型有完整的指标维度定义 + 属性元数据约束
-- ============================================================

-- ---- 1. Service — 微服务 (四维度指标体系) ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"language","name":"编程语言","type":"string","required":false,"description":"服务开发语言"},
    {"key":"framework","name":"框架","type":"string","required":false,"description":"Web框架"},
    {"key":"port","name":"服务端口","type":"int","required":true,"default":8080,"min":1,"max":65535,"description":"监听端口"},
    {"key":"team","name":"负责团队","type":"string","required":false,"description":"服务归属团队"},
    {"key":"version","name":"版本号","type":"string","required":false,"description":"当前部署版本"}
  ],
  "templates": ["base_software"],
  "metrics": [
    {"name":"http.server.request.duration.p99","display":"P99延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":500,"crit":2000},"description":"HTTP请求P99响应时间"},
    {"name":"http.server.request.duration.p50","display":"P50延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":200,"crit":800},"description":"HTTP请求P50响应时间"},
    {"name":"http.server.request.duration.avg","display":"平均延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":300,"crit":1000},"description":"HTTP请求平均响应时间"},
    {"name":"http.server.request.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance","description":"每秒请求数"},
    {"name":"http.server.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5},"description":"HTTP请求错误率(5xx)"},
    {"name":"http.server.request.5xx_count","display":"5xx错误数","type":"counter","unit":"count/min","category":"error","thresholds":{"rate_warn":10,"rate_crit":50},"description":"每分钟5xx错误数"},
    {"name":"http.server.request.4xx_count","display":"4xx错误数","type":"counter","unit":"count/min","category":"error","thresholds":{"rate_warn":50,"rate_crit":200},"description":"每分钟4xx错误数"},
    {"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":70,"crit":90},"description":"主机CPU使用率"},
    {"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":95},"description":"主机内存使用率"},
    {"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":90},"description":"主机磁盘使用率"},
    {"name":"jvm.heap.usage","display":"JVM堆内存","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":75,"crit":90},"description":"JVM堆内存使用率(Java服务)"},
    {"name":"threadpool.active","display":"活跃线程数","type":"gauge","unit":"count","category":"resource","description":"线程池活跃线程数"},
    {"name":"business.order.success_rate","display":"业务成功率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":99,"crit":95},"description":"业务订单成功率"}
  ],
  "relations": [
    {"type":"calls","direction":"out","target":"Service","dimension":"horizontal","description":"服务间调用"},
    {"type":"depends_on","direction":"out","target":"Database","dimension":"horizontal","description":"依赖数据库"},
    {"type":"depends_on","direction":"out","target":"Redis","dimension":"horizontal","description":"依赖缓存"},
    {"type":"runs_on","direction":"out","target":"Host","dimension":"vertical","description":"运行在主机上"},
    {"type":"has_endpoint","direction":"out","target":"Endpoint","dimension":"vertical","description":"提供接口"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"performance","display":"性能","metric":"http.server.request.duration.p99","weight":0.30,"category":"performance"},
      {"name":"error","display":"错误","metric":"http.server.request.error_rate","weight":0.25,"category":"error"},
      {"name":"resource","display":"资源","metric":"system.cpu.usage","weight":0.20,"category":"resource"},
      {"name":"business","display":"业务","metric":"business.order.success_rate","weight":0.25,"category":"business"}
    ]
  },
  "discovery": {
    "auto_match": ["service.name"],
    "reconcile_priority": ["qualified_name", "name"]
  }
}' WHERE type_name = 'Service';

-- ---- 2. Host — 主机 (四维度指标体系) ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"ip","name":"IP地址","type":"string","required":true,"description":"主机IP地址"},
    {"key":"cpu_cores","name":"CPU核数","type":"int","required":true,"min":1,"max":256,"description":"CPU核心数"},
    {"key":"memory_gb","name":"内存(GB)","type":"int","required":true,"min":1,"max":4096,"description":"内存容量GB"},
    {"key":"disk_gb","name":"磁盘(GB)","type":"int","required":false,"description":"磁盘容量GB"},
    {"key":"os","name":"操作系统","type":"string","required":false,"description":"操作系统版本"},
    {"key":"sn","name":"序列号","type":"string","required":false,"description":"硬件序列号"},
    {"key":"vendor","name":"厂商","type":"string","required":false,"description":"服务器厂商"},
    {"key":"cloud_provider","name":"云厂商","type":"string","required":false,"description":"阿里云/AWS/腾讯云等"},
    {"key":"instance_type","name":"实例规格","type":"string","required":false,"description":"云主机规格"}
  ],
  "templates": ["base_hardware", "base_cloud"],
  "metrics": [
    {"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"compute","thresholds":{"warn":70,"crit":90},"description":"CPU使用率"},
    {"name":"system.cpu.load.1m","display":"1分钟负载","type":"gauge","unit":"count","category":"compute","description":"1分钟平均负载"},
    {"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":80,"crit":95},"description":"内存使用率"},
    {"name":"system.memory.available","display":"可用内存","type":"gauge","unit":"MB","category":"memory","description":"可用内存MB"},
    {"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":80,"crit":90},"description":"磁盘使用率"},
    {"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":70,"crit":90},"description":"磁盘IO利用率"},
    {"name":"system.disk.io.read_bytes","display":"磁盘读吞吐","type":"gauge","unit":"MB/s","category":"disk","description":"磁盘读取吞吐量"},
    {"name":"system.disk.io.write_bytes","display":"磁盘写吞吐","type":"gauge","unit":"MB/s","category":"disk","description":"磁盘写入吞吐量"},
    {"name":"system.network.bytes_recv","display":"网络入流量","type":"gauge","unit":"MB/s","category":"network","description":"网络接收字节"},
    {"name":"system.network.bytes_sent","display":"网络出流量","type":"gauge","unit":"MB/s","category":"network","description":"网络发送字节"},
    {"name":"system.network.packet.loss","display":"网络丢包率","type":"gauge","unit":"percent","category":"network","thresholds":{"warn":0.1,"crit":1.0},"description":"网络丢包率"},
    {"name":"system.process.count","display":"进程数","type":"gauge","unit":"count","category":"os","description":"运行进程数"},
    {"name":"system.uptime","display":"运行时间","type":"gauge","unit":"seconds","category":"os","description":"主机运行时间"}
  ],
  "relations": [
    {"type":"hosts","direction":"out","target":"Service","dimension":"vertical","description":"承载服务"},
    {"type":"hosts","direction":"out","target":"Database","dimension":"vertical","description":"承载数据库"},
    {"type":"hosts","direction":"out","target":"Redis","dimension":"vertical","description":"承载缓存"},
    {"type":"connected_to","direction":"out","target":"NetworkDevice","dimension":"vertical","description":"连接网络设备"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"cpu","display":"CPU","metric":"system.cpu.usage","weight":0.30,"category":"compute"},
      {"name":"memory","display":"内存","metric":"system.memory.usage","weight":0.25,"category":"memory"},
      {"name":"disk","display":"磁盘","metric":"system.disk.usage","weight":0.25,"category":"disk"},
      {"name":"disk_io","display":"磁盘IO","metric":"system.disk.io.util","weight":0.20,"category":"disk"}
    ]
  },
  "discovery": {
    "auto_match": ["host.name", "host.ip"],
    "reconcile_priority": ["qualified_name", "attributes.sn", "attributes.ip", "name"]
  }
}' WHERE type_name = 'Host';

-- ---- 3. MySQL (三维度指标体系) ----
UPDATE entity_type_def SET definition = '{
  "super_type": "Database",
  "attributes": [
    {"key":"db_version","name":"数据库版本","type":"string","required":false,"description":"MySQL版本"},
    {"key":"port","name":"端口","type":"int","required":true,"default":3306,"min":1,"max":65535},
    {"key":"max_connections","name":"最大连接数","type":"int","required":false,"default":500},
    {"key":"replication_mode","name":"复制模式","type":"string","required":false,"description":"主从复制模式"}
  ],
  "templates": ["base_database"],
  "metrics": [
    {"name":"mysql.connections.active","display":"活跃连接数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":400,"crit":480},"description":"当前活跃连接数"},
    {"name":"mysql.connections.usage_rate","display":"连接使用率","type":"gauge","unit":"percent","category":"connections","thresholds":{"warn":80,"crit":95},"description":"连接数/最大连接数"},
    {"name":"mysql.connections.waiting","display":"等待连接数","type":"gauge","unit":"count","category":"connections","description":"等待获取连接的线程数"},
    {"name":"mysql.queries.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance","description":"每秒查询数"},
    {"name":"mysql.queries.slow","display":"慢查询数","type":"counter","unit":"count/min","category":"performance","thresholds":{"rate_warn":5,"rate_crit":20},"description":"每分钟慢查询数"},
    {"name":"mysql.queries.avg_latency","display":"平均查询延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":100,"crit":500},"description":"平均SQL执行时间"},
    {"name":"mysql.buffer_pool.hit_rate","display":"Buffer Pool命中率","type":"gauge","unit":"percent","category":"performance","thresholds":{"warn":95,"crit":90},"description":"InnoDB Buffer Pool命中率"},
    {"name":"mysql.replication.lag","display":"主从延迟","type":"gauge","unit":"seconds","category":"replication","thresholds":{"warn":5,"crit":30},"description":"主从复制延迟秒数"},
    {"name":"mysql.replication.io_running","display":"IO线程状态","type":"gauge","unit":"bool","category":"replication","description":"复制IO线程是否运行"},
    {"name":"mysql.replication.sql_running","display":"SQL线程状态","type":"gauge","unit":"bool","category":"replication","description":"复制SQL线程是否运行"},
    {"name":"mysql.table.locks.waited","display":"表锁等待","type":"counter","unit":"count/min","category":"locks","thresholds":{"rate_warn":5,"rate_crit":20},"description":"每分钟表锁等待数"},
    {"name":"mysql.innodb.row_lock.waited","display":"行锁等待","type":"counter","unit":"count/min","category":"locks","thresholds":{"rate_warn":10,"rate_crit":50},"description":"每分钟行锁等待数"}
  ],
  "relations": [
    {"type":"runs_on","direction":"out","target":"Host","dimension":"vertical","description":"运行在主机上"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"connections","display":"连接","metric":"mysql.connections.usage_rate","weight":0.20,"category":"connections"},
      {"name":"performance","display":"性能","metric":"mysql.queries.avg_latency","weight":0.25,"category":"performance"},
      {"name":"slow_queries","display":"慢查询","metric":"mysql.queries.slow","weight":0.20,"category":"performance"},
      {"name":"replication","display":"复制","metric":"mysql.replication.lag","weight":0.15,"category":"replication"},
      {"name":"buffer_pool","display":"缓存","metric":"mysql.buffer_pool.hit_rate","weight":0.20,"category":"performance"}
    ]
  }
}' WHERE type_name = 'MySQL';

-- ---- 4. Redis (三维度指标体系) ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"redis_version","name":"Redis版本","type":"string","required":false},
    {"key":"port","name":"端口","type":"int","required":true,"default":6379},
    {"key":"max_memory","name":"最大内存","type":"string","required":false,"description":"maxmemory配置"},
    {"key":"cluster_mode","name":"集群模式","type":"string","required":false,"description":"standalone/sentinel/cluster"}
  ],
  "metrics": [
    {"name":"redis.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":75,"crit":90},"description":"Redis内存使用率"},
    {"name":"redis.memory.used_bytes","display":"已用内存","type":"gauge","unit":"MB","category":"memory","description":"已使用内存字节"},
    {"name":"redis.memory.fragmentation_ratio","display":"内存碎片率","type":"gauge","unit":"ratio","category":"memory","thresholds":{"warn":1.5,"crit":3.0},"description":"内存碎片率"},
    {"name":"redis.commands.qps","display":"命令QPS","type":"gauge","unit":"count/s","category":"performance","description":"每秒执行命令数"},
    {"name":"redis.commands.avg_latency","display":"平均延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":5,"crit":20},"description":"命令平均执行时间"},
    {"name":"redis.commands.slow","display":"慢命令数","type":"counter","unit":"count/min","category":"performance","thresholds":{"rate_warn":5,"rate_crit":20},"description":"每分钟慢命令数"},
    {"name":"redis.commands.hit_rate","display":"命中率","type":"gauge","unit":"percent","category":"performance","thresholds":{"warn":90,"crit":80},"description":"缓存命中率"},
    {"name":"redis.commands.miss_rate","display":"Miss率","type":"gauge","unit":"percent","category":"performance","description":"缓存Miss率"},
    {"name":"redis.clients.connected","display":"连接客户端数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":500,"crit":1000},"description":"已连接客户端数"},
    {"name":"redis.clients.blocked","display":"阻塞客户端数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":10,"crit":50},"description":"阻塞等待的客户端数"},
    {"name":"redis.keyspace.keys","display":"键总数","type":"gauge","unit":"count","category":"data","description":"所有DB的键总数"},
    {"name":"redis.keyspace.expired","display":"过期键数","type":"gauge","unit":"count","category":"data","description":"设置了过期时间的键数"},
    {"name":"redis.persistence.rdb.last_save_status","display":"RDB状态","type":"gauge","unit":"bool","category":"persistence","description":"最近RDB保存是否成功"},
    {"name":"redis.replication.lag","display":"主从延迟","type":"gauge","unit":"seconds","category":"replication","thresholds":{"warn":5,"crit":30},"description":"主从复制延迟"}
  ],
  "relations": [
    {"type":"runs_on","direction":"out","target":"Host","dimension":"vertical","description":"运行在主机上"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"memory","display":"内存","metric":"redis.memory.usage","weight":0.25,"category":"memory"},
      {"name":"hit_rate","display":"命中率","metric":"redis.commands.hit_rate","weight":0.30,"category":"performance"},
      {"name":"latency","display":"延迟","metric":"redis.commands.avg_latency","weight":0.25,"category":"performance"},
      {"name":"connections","display":"连接","metric":"redis.clients.connected","weight":0.20,"category":"connections"}
    ]
  }
}' WHERE type_name = 'Redis';

-- ---- 5. Business — 业务服务 (children_avg 聚合) ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"business_domain","name":"业务域","type":"string","required":false,"description":"所属业务域"},
    {"key":"business_owner","name":"业务负责人","type":"string","required":false},
    {"key":"tech_owner","name":"技术负责人","type":"string","required":false},
    {"key":"slo_availability","name":"SLO可用性","type":"float","required":false,"default":99.9,"description":"SLO可用性目标(%)"},
    {"key":"slo_latency_p99","name":"SLO延迟P99","type":"int","required":false,"description":"SLO P99延迟目标(ms)"},
    {"key":"business_weight","name":"业务权重","type":"float","required":true,"default":1.0,"min":0,"max":3.0,"description":"业务重要性权重"}
  ],
  "metrics": [
    {"name":"business.success_rate","display":"业务成功率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":99.5,"crit":99.0},"description":"业务整体成功率"},
    {"name":"business.throughput","display":"业务吞吐量","type":"gauge","unit":"count/min","category":"business","description":"每分钟业务处理量"},
    {"name":"business.user_count","display":"在线用户数","type":"gauge","unit":"count","category":"business","description":"当前在线用户数"},
    {"name":"business.revenue_per_minute","display":"每分钟营收","type":"gauge","unit":"yuan/min","category":"business","description":"每分钟业务营收"}
  ],
  "relations": [
    {"type":"includes","direction":"out","target":"Service","dimension":"vertical","description":"包含服务"}
  ],
  "health": {
    "method": "children_avg"
  }
}' WHERE type_name = 'Business';

-- ---- 6. Database — 通用数据库 ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"db_type","name":"数据库类型","type":"string","required":true,"description":"MySQL/PostgreSQL/MongoDB等"},
    {"key":"db_version","name":"版本","type":"string","required":false},
    {"key":"port","name":"端口","type":"int","required":true,"min":1,"max":65535},
    {"key":"max_connections","name":"最大连接数","type":"int","required":false}
  ],
  "templates": ["base_database"],
  "metrics": [
    {"name":"db.connections.active","display":"活跃连接数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":80,"crit":95}},
    {"name":"db.queries.slow","display":"慢查询数","type":"counter","unit":"count/min","category":"performance","thresholds":{"rate_warn":10,"rate_crit":50}},
    {"name":"db.queries.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},
    {"name":"db.storage.used","display":"存储使用量","type":"gauge","unit":"GB","category":"storage","description":"已使用存储空间"}
  ],
  "relations": [
    {"type":"runs_on","direction":"out","target":"Host","dimension":"vertical"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"connections","weight":0.3},
      {"name":"slow_queries","weight":0.3},
      {"name":"query_latency","weight":0.4}
    ]
  }
}' WHERE type_name = 'Database';

-- ---- 7. NetworkDevice — 网络设备 ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"vendor","name":"厂商","type":"string","required":false,"description":"设备厂商"},
    {"key":"model","name":"型号","type":"string","required":false},
    {"key":"mgmt_ip","name":"管理IP","type":"string","required":true},
    {"key":"port_count","name":"端口数","type":"int","required":false},
    {"key":"firmware_version","name":"固件版本","type":"string","required":false}
  ],
  "templates": ["base_network"],
  "metrics": [
    {"name":"network.packet.loss","display":"丢包率","type":"gauge","unit":"percent","category":"reliability","thresholds":{"warn":0.1,"crit":1.0}},
    {"name":"network.latency","display":"网络延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":10,"crit":50}},
    {"name":"network.bandwidth.utilization","display":"带宽利用率","type":"gauge","unit":"percent","category":"capacity","thresholds":{"warn":70,"crit":90}},
    {"name":"network.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"reliability","thresholds":{"warn":0.01,"crit":0.1}},
    {"name":"network.device.cpu","display":"设备CPU","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":70,"crit":90}},
    {"name":"network.device.memory","display":"设备内存","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":95}}
  ],
  "relations": [
    {"type":"connected_to","direction":"out","target":"Host","dimension":"vertical"},
    {"type":"connected_to","direction":"out","target":"NetworkDevice","dimension":"vertical"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"packet_loss","weight":0.35},
      {"name":"latency","weight":0.25},
      {"name":"utilization","weight":0.20},
      {"name":"error_rate","weight":0.20}
    ]
  }
}' WHERE type_name = 'NetworkDevice';

-- ---- 8. Endpoint — API端点 ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"method","name":"HTTP方法","type":"string","required":true,"description":"GET/POST/PUT/DELETE"},
    {"key":"path","name":"URL路径","type":"string","required":true,"description":"接口路径"},
    {"key":"service","name":"所属服务","type":"string","required":true,"description":"归属服务名"},
    {"key":"description","name":"接口说明","type":"string","required":false}
  ],
  "metrics": [
    {"name":"endpoint.request.duration.p99","display":"P99延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":500,"crit":2000}},
    {"name":"endpoint.request.duration.avg","display":"平均延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":200,"crit":1000}},
    {"name":"endpoint.request.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},
    {"name":"endpoint.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}},
    {"name":"endpoint.request.count","display":"调用次数","type":"counter","unit":"count","category":"volume"}
  ],
  "relations": [
    {"type":"belongs_to","direction":"in","target":"Service","dimension":"vertical"},
    {"type":"calls","direction":"out","target":"Endpoint","dimension":"horizontal"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"latency","weight":0.40},
      {"name":"error_rate","weight":0.35},
      {"name":"qps","weight":0.25}
    ]
  }
}' WHERE type_name = 'Endpoint';

-- ---- 9. Middleware — 通用中间件 ----
UPDATE entity_type_def SET definition = '{
  "attributes": [
    {"key":"middleware_type","name":"中间件类型","type":"string","required":true,"description":"MQ/ES/ZK等"},
    {"key":"version","name":"版本","type":"string","required":false},
    {"key":"port","name":"端口","type":"int","required":false}
  ],
  "metrics": [
    {"name":"middleware.connections","display":"连接数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":500,"crit":1000}},
    {"name":"middleware.throughput","display":"吞吐量","type":"gauge","unit":"count/s","category":"performance"},
    {"name":"middleware.latency","display":"处理延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":100,"crit":500}},
    {"name":"middleware.queue_depth","display":"队列深度","type":"gauge","unit":"count","category":"capacity","thresholds":{"warn":10000,"crit":50000}}
  ],
  "relations": [
    {"type":"runs_on","direction":"out","target":"Host","dimension":"vertical"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name":"connections","weight":0.3},
      {"name":"latency","weight":0.3},
      {"name":"throughput","weight":0.4}
    ]
  }
}' WHERE type_name = 'Middleware';

-- ---- 10-13. K8sCluster, K8sPod, IP 保持不变或微调 ----
-- K8sCluster 和 K8sPod 已有较好的定义，暂不修改
-- IP 不需要指标

-- 完成
SELECT '指标体系更新完成' as status, count(*) as types_updated FROM entity_type_def WHERE definition != '{}';
