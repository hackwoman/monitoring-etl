-- ============================================================
-- 指标体系升级 — 更新现有实体类型的指标定义
-- 重点：NetworkDevice 增加动态感知指标，所有类型对齐 Golden Signals
-- ============================================================

-- NetworkDevice: 增加 TCP 连接/重传/端口级指标
UPDATE entity_type_def SET definition = jsonb_set(definition, '{metrics}', '[
  {"name":"network.packet.loss","display":"丢包率","type":"gauge","unit":"percent","category":"quality","thresholds":{"warn":0.1,"crit":1.0}},
  {"name":"network.latency","display":"网络延迟","type":"gauge","unit":"ms","category":"quality","thresholds":{"warn":10,"crit":50}},
  {"name":"network.error.rate","display":"错误率","type":"gauge","unit":"percent","category":"quality","thresholds":{"warn":0.01,"crit":0.1}},
  {"name":"network.bandwidth.utilization","display":"带宽利用率","type":"gauge","unit":"percent","category":"capacity","thresholds":{"warn":70,"crit":90}},
  {"name":"network.tcp.new_connections.rate","display":"新建连接速率","type":"gauge","unit":"count/s","category":"dynamic","thresholds":{"warn":1000,"crit":5000}},
  {"name":"network.tcp.established.count","display":"活跃TCP连接","type":"gauge","unit":"count","category":"dynamic","thresholds":{"warn":10000,"crit":50000}},
  {"name":"network.tcp.time_wait.count","display":"TIME_WAIT连接","type":"gauge","unit":"count","category":"dynamic","thresholds":{"warn":5000,"crit":20000}},
  {"name":"network.tcp.retransmit.rate","display":"TCP重传率","type":"gauge","unit":"percent","category":"quality","thresholds":{"warn":1,"crit":5}},
  {"name":"network.port.status","display":"端口状态","type":"gauge","unit":"bool","category":"status"},
  {"name":"network.port.throughput.in","display":"端口入流量","type":"gauge","unit":"MB/s","category":"capacity"},
  {"name":"network.port.throughput.out","display":"端口出流量","type":"gauge","unit":"MB/s","category":"capacity"},
  {"name":"network.device.cpu","display":"设备CPU","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":70,"crit":90}},
  {"name":"network.device.memory","display":"设备内存","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":95}}
]') WHERE type_name = 'NetworkDevice';

-- Service: 增加饱和度指标
UPDATE entity_type_def SET definition = jsonb_set(definition, '{metrics}', '[
  {"name":"http.server.request.duration.p50","display":"P50延迟","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":200,"crit":800}},
  {"name":"http.server.request.duration.p99","display":"P99延迟","type":"gauge","unit":"ms","category":"latency","thresholds":{"warn":500,"crit":2000}},
  {"name":"http.server.request.qps","display":"QPS","type":"gauge","unit":"count/s","category":"traffic"},
  {"name":"http.server.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}},
  {"name":"http.server.request.5xx_count","display":"5xx错误数","type":"counter","unit":"count/min","category":"error","thresholds":{"rate_warn":10,"rate_crit":50}},
  {"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"saturation","thresholds":{"warn":70,"crit":90}},
  {"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"saturation","thresholds":{"warn":80,"crit":95}},
  {"name":"system.load.1m","display":"1分钟负载","type":"gauge","unit":"ratio","category":"saturation","thresholds":{"warn":0.7,"crit":1.0}},
  {"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","category":"saturation","thresholds":{"warn":70,"crit":90}},
  {"name":"business.order.success_rate","display":"业务成功率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":99,"crit":95}}
]') WHERE type_name = 'Service';

-- Host: 增加 load average（饱和度核心指标）
UPDATE entity_type_def SET definition = jsonb_set(definition, '{metrics}', '[
  {"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"compute","thresholds":{"warn":70,"crit":90}},
  {"name":"system.cpu.load.1m","display":"1分钟负载","type":"gauge","unit":"ratio","category":"saturation","thresholds":{"warn":0.7,"crit":1.0}},
  {"name":"system.cpu.load.5m","display":"5分钟负载","type":"gauge","unit":"ratio","category":"saturation"},
  {"name":"system.cpu.load.15m","display":"15分钟负载","type":"gauge","unit":"ratio","category":"saturation"},
  {"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":80,"crit":95}},
  {"name":"system.memory.available","display":"可用内存","type":"gauge","unit":"GB","category":"memory"},
  {"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":80,"crit":90}},
  {"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":70,"crit":90}},
  {"name":"system.network.bytes_recv","display":"网络入流量","type":"gauge","unit":"MB/s","category":"network"},
  {"name":"system.network.bytes_sent","display":"网络出流量","type":"gauge","unit":"MB/s","category":"network"},
  {"name":"system.network.packet.loss","display":"网络丢包率","type":"gauge","unit":"percent","category":"network","thresholds":{"warn":0.1,"crit":1.0}},
  {"name":"system.process.count","display":"进程数","type":"gauge","unit":"count","category":"resource","thresholds":{"warn":500,"crit":1000}},
  {"name":"system.file_descriptor.usage","display":"FD使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":95}}
]') WHERE type_name = 'Host';
