--
-- PostgreSQL database dump
--

\restrict txIMcD2ybmLP37FQD6i5yXXArnGfGIZS8taRzWYw12H29A9s9p1V009CFeeOaiX

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: attribute_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribute_template (
    template_name character varying(128) NOT NULL,
    category character varying(64),
    attributes jsonb DEFAULT '[]'::jsonb NOT NULL,
    description text,
    is_builtin boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: cmdb_event_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cmdb_event_log (
    event_id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_type character varying(64) NOT NULL,
    entity_guid uuid,
    payload jsonb,
    published_at timestamp with time zone DEFAULT now(),
    status character varying(16) DEFAULT 'pending'::character varying
);


--
-- Name: cmdb_event_subscription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cmdb_event_subscription (
    subscription_id uuid DEFAULT gen_random_uuid() NOT NULL,
    subscriber character varying(256) NOT NULL,
    event_types character varying(64)[] NOT NULL,
    filter jsonb DEFAULT '{}'::jsonb,
    callback_url character varying(512),
    callback_mode character varying(16) DEFAULT 'webhook'::character varying,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: data_check_rule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.data_check_rule (
    rule_id uuid DEFAULT gen_random_uuid() NOT NULL,
    rule_name character varying(256) NOT NULL,
    rule_type character varying(32) NOT NULL,
    target_type character varying(128),
    check_sql text NOT NULL,
    expected_result character varying(32) DEFAULT 'empty'::character varying,
    severity character varying(16) DEFAULT 'warning'::character varying,
    check_schedule character varying(64) DEFAULT '0 2 * * *'::character varying,
    is_builtin boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: data_quality_snapshot; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.data_quality_snapshot (
    snapshot_id uuid DEFAULT gen_random_uuid() NOT NULL,
    snapshot_time timestamp with time zone DEFAULT now(),
    overall_score integer,
    total_entities integer,
    total_rules integer,
    passed_rules integer,
    failed_rules integer,
    type_scores jsonb DEFAULT '{}'::jsonb,
    issues jsonb DEFAULT '[]'::jsonb
);


--
-- Name: entity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity (
    guid uuid DEFAULT gen_random_uuid() NOT NULL,
    type_name character varying(128) NOT NULL,
    name character varying(512) NOT NULL,
    qualified_name character varying(1024) NOT NULL,
    attributes jsonb DEFAULT '{}'::jsonb,
    labels jsonb DEFAULT '{}'::jsonb,
    status character varying(32) DEFAULT 'active'::character varying,
    source character varying(64) DEFAULT 'manual'::character varying,
    expected_metrics jsonb DEFAULT '[]'::jsonb,
    expected_relations jsonb DEFAULT '[]'::jsonb,
    health_score integer,
    health_level character varying(16),
    health_detail jsonb,
    last_observed timestamp with time zone,
    biz_service character varying(256),
    risk_score integer,
    propagation_hops integer,
    blast_radius integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: COLUMN entity.health_score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.entity.health_score IS '健康评分 0-100';


--
-- Name: COLUMN entity.health_level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.entity.health_level IS 'healthy>=80 / warning>=60 / critical>=30 / down<30';


--
-- Name: COLUMN entity.risk_score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.entity.risk_score IS '业务风险度 0-100 (健康度差 × 业务权重 × 影响范围)';


--
-- Name: COLUMN entity.propagation_hops; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.entity.propagation_hops IS '到用户端点的最短传播跳数';


--
-- Name: COLUMN entity.blast_radius; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.entity.blast_radius IS '该实体故障会影响的下游实体数量';


--
-- Name: entity_type_def; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_type_def (
    type_name character varying(128) NOT NULL,
    display_name character varying(256),
    category character varying(64) DEFAULT 'custom'::character varying,
    icon character varying(128),
    super_type character varying(128),
    super_types jsonb DEFAULT '[]'::jsonb,
    attribute_defs jsonb DEFAULT '{}'::jsonb,
    definition jsonb DEFAULT '{}'::jsonb,
    description text,
    is_custom boolean DEFAULT false,
    version integer DEFAULT 1,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: label_definition; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.label_definition (
    label_key character varying(128) NOT NULL,
    label_name character varying(256),
    value_type character varying(32) DEFAULT 'string'::character varying,
    enum_values jsonb,
    description text,
    created_by character varying(128),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: relationship; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.relationship (
    guid uuid DEFAULT gen_random_uuid() NOT NULL,
    type_name character varying(128) NOT NULL,
    end1_guid uuid,
    end2_guid uuid,
    from_guid uuid,
    to_guid uuid,
    attributes jsonb DEFAULT '{}'::jsonb,
    source character varying(64) DEFAULT 'manual'::character varying,
    confidence double precision DEFAULT 1.0,
    dimension character varying(16) DEFAULT 'vertical'::character varying,
    is_active boolean DEFAULT true,
    first_seen timestamp with time zone DEFAULT now(),
    last_seen timestamp with time zone DEFAULT now(),
    expired_at timestamp with time zone,
    verified_by character varying(128),
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    call_type character varying(16)
);


--
-- Name: relationship_type_def; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.relationship_type_def (
    type_name character varying(128) NOT NULL,
    end1_type character varying(128),
    end1_name character varying(128),
    end2_type character varying(128),
    end2_name character varying(128),
    description text
);


--
-- Data for Name: attribute_template; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.attribute_template (template_name, category, attributes, description, is_builtin, created_at) FROM stdin;
base_hardware	infrastructure	[{"key": "cpu_cores", "name": "CPU核数", "type": "int"}, {"key": "memory_gb", "name": "内存(GB)", "type": "int"}, {"key": "disk_gb", "name": "磁盘(GB)", "type": "int"}, {"key": "os", "name": "操作系统", "type": "string"}, {"key": "ip", "name": "IP地址", "type": "string"}, {"key": "sn", "name": "序列号", "type": "string"}]	基础硬件属性	t	2026-04-08 00:00:53.428045+00
base_network	infrastructure	[{"key": "vendor", "name": "厂商", "type": "string"}, {"key": "model", "name": "型号", "type": "string"}, {"key": "mgmt_ip", "name": "管理IP", "type": "string"}, {"key": "port_count", "name": "端口数", "type": "int"}, {"key": "firmware_version", "name": "固件版本", "type": "string"}]	网络设备属性	t	2026-04-08 00:00:53.428045+00
base_database	middleware	[{"key": "db_type", "name": "数据库类型", "type": "string"}, {"key": "db_version", "name": "版本", "type": "string"}, {"key": "port", "name": "端口", "type": "int"}, {"key": "max_connections", "name": "最大连接数", "type": "int"}, {"key": "replication_mode", "name": "复制模式", "type": "string"}]	数据库属性	t	2026-04-08 00:00:53.428045+00
base_container	runtime	[{"key": "cluster_name", "name": "集群名", "type": "string"}, {"key": "namespace", "name": "命名空间", "type": "string"}, {"key": "node_count", "name": "节点数", "type": "int"}, {"key": "k8s_version", "name": "K8s版本", "type": "string"}]	容器/K8s属性	t	2026-04-08 00:00:53.428045+00
base_cloud	infrastructure	[{"key": "cloud_provider", "name": "云厂商", "type": "string"}, {"key": "region", "name": "地域", "type": "string"}, {"key": "az", "name": "可用区", "type": "string"}, {"key": "instance_type", "name": "实例规格", "type": "string"}, {"key": "vpc_id", "name": "VPC ID", "type": "string"}]	云资源属性	t	2026-04-08 00:00:53.428045+00
base_software	application	[{"key": "language", "name": "编程语言", "type": "string"}, {"key": "framework", "name": "框架", "type": "string"}, {"key": "version", "name": "版本", "type": "string"}, {"key": "port", "name": "服务端口", "type": "int"}, {"key": "team", "name": "负责团队", "type": "string"}]	软件/应用属性	t	2026-04-08 00:00:53.428045+00
\.


--
-- Data for Name: cmdb_event_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cmdb_event_log (event_id, event_type, entity_guid, payload, published_at, status) FROM stdin;
\.


--
-- Data for Name: cmdb_event_subscription; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cmdb_event_subscription (subscription_id, subscriber, event_types, filter, callback_url, callback_mode, is_active, created_at) FROM stdin;
\.


--
-- Data for Name: data_check_rule; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.data_check_rule (rule_id, rule_name, rule_type, target_type, check_sql, expected_result, severity, check_schedule, is_builtin, created_at) FROM stdin;
\.


--
-- Data for Name: data_quality_snapshot; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.data_quality_snapshot (snapshot_id, snapshot_time, overall_score, total_entities, total_rules, passed_rules, failed_rules, type_scores, issues) FROM stdin;
\.


--
-- Data for Name: entity; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.entity (guid, type_name, name, qualified_name, attributes, labels, status, source, expected_metrics, expected_relations, health_score, health_level, health_detail, last_observed, biz_service, risk_score, propagation_hops, blast_radius, created_at, updated_at) FROM stdin;
176a52d7-7150-4afa-8015-e11e2b44c153	Business	在线支付	business:在线支付	{"tech_owner": "李四", "business_owner": "张三", "business_domain": "电商", "business_weight": 1.0, "slo_latency_p99": 200, "slo_availability": 99.9}	{"env": "prod", "business_line": "支付"}	active	demo	[]	[]	85	healthy	\N	\N	在线支付	15	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
a57cd333-c346-4081-bcb7-369f9dd7c87e	Business	用户注册	business:用户注册	{"tech_owner": "赵六", "business_owner": "王五", "business_domain": "电商", "business_weight": 0.6, "slo_latency_p99": 500, "slo_availability": 99.5}	{"env": "prod", "business_line": "用户"}	active	demo	[]	[]	92	healthy	\N	\N	用户注册	8	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
98d9c92c-3f71-4a60-b9c4-a791b009151c	Host	web-01	host:web-01	{"ip": "10.0.1.10", "os": "CentOS 7.9", "cpu_cores": 8, "memory_gb": 32}	{"env": "prod", "team": "infra", "region": "cn-east-1"}	active	demo	[]	[]	78	healthy	\N	\N	在线支付	22	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
0cd4becb-ee8d-4167-8845-67cabfd2be90	Host	web-02	host:web-02	{"ip": "10.0.1.11", "os": "CentOS 7.9", "cpu_cores": 8, "memory_gb": 32}	{"env": "prod", "team": "infra", "region": "cn-east-1"}	active	demo	[]	[]	85	healthy	\N	\N	在线支付	15	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
f729746a-9416-4b17-b4de-55688621630e	Host	app-01	host:app-01	{"ip": "10.0.1.20", "os": "CentOS 7.9", "cpu_cores": 16, "memory_gb": 64}	{"env": "prod", "team": "infra", "region": "cn-east-1"}	active	demo	[]	[]	92	healthy	\N	\N	在线支付	8	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
ecb21a4b-1a02-40c1-a885-0bb7516f6830	Host	app-02	host:app-02	{"ip": "10.0.1.21", "os": "CentOS 7.9", "cpu_cores": 16, "memory_gb": 64}	{"env": "prod", "team": "infra", "region": "cn-east-1"}	active	demo	[]	[]	88	healthy	\N	\N	在线支付	12	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	Host	db-master	host:db-master	{"ip": "10.0.1.30", "os": "CentOS 7.9", "cpu_cores": 32, "memory_gb": 128}	{"env": "prod", "team": "DBA", "region": "cn-east-1"}	active	demo	[]	[]	65	warning	\N	\N	在线支付	35	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
0d404cb3-a332-4f2e-bd08-fa711958b69f	Service	gateway	service:gateway	{"port": 80, "team": "架构组", "language": "Java", "framework": "SpringCloudGateway"}	{"env": "prod", "team": "架构组", "business_line": "支付"}	active	demo	[]	[]	95	healthy	\N	\N	在线支付	5	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	Service	order-service	service:order-service	{"port": 8081, "team": "订单组", "language": "Java", "framework": "SpringBoot"}	{"env": "prod", "team": "订单组", "business_line": "支付"}	active	demo	[]	[]	72	warning	\N	\N	在线支付	78	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
18702e75-6824-4a92-8fe2-c5c959ec485e	Service	payment-service	service:payment-service	{"port": 8080, "team": "支付组", "language": "Java", "framework": "SpringBoot"}	{"env": "prod", "team": "支付组", "business_line": "支付"}	active	demo	[]	[]	68	warning	\N	\N	在线支付	82	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
9449aef0-600e-4b7c-8ae8-16afead6b347	Service	user-service	service:user-service	{"port": 8083, "team": "用户组", "language": "Go", "framework": "Gin"}	{"env": "prod", "team": "用户组", "business_line": "用户"}	active	demo	[]	[]	88	healthy	\N	\N	用户注册	12	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
54b0a994-7727-44f4-acd7-63b1f79d88d0	MySQL	payment-db	mysql:payment-db	{"port": 3306, "db_type": "MySQL", "db_version": "8.0", "max_connections": 500}	{"env": "prod", "team": "DBA"}	active	demo	[]	[]	55	critical	\N	\N	在线支付	85	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
9dddd323-9390-436b-9f7f-f8632318084e	MySQL	order-db	mysql:order-db	{"port": 3306, "db_type": "MySQL", "db_version": "8.0", "max_connections": 500}	{"env": "prod", "team": "DBA"}	active	demo	[]	[]	78	healthy	\N	\N	在线支付	22	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
2f9f6d43-394f-43de-b9dc-7645f5195a0c	Redis	user-cache	redis:user-cache	{"port": 6379, "db_type": "Redis", "redis_version": "7.0"}	{"env": "prod", "team": "DBA"}	active	demo	[]	[]	92	healthy	\N	\N	在线支付	8	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
2d889e09-8867-47ea-ba94-e7be307cff3e	NetworkDevice	核心交换机-01	network:核心交换机-01	{"model": "C9300", "vendor": "Cisco", "mgmt_ip": "10.0.0.1", "port_count": 48}	{"env": "prod", "region": "cn-east-1"}	active	demo	[]	[]	95	healthy	\N	\N	\N	5	\N	\N	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00
\.


--
-- Data for Name: entity_type_def; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.entity_type_def (type_name, display_name, category, icon, super_type, super_types, attribute_defs, definition, description, is_custom, version, created_at, updated_at) FROM stdin;
Business	业务服务	business	business	\N	[]	{}	{"health": {"method": "children_avg"}, "metrics": [{"name": "business.success_rate", "type": "gauge", "unit": "percent", "display": "业务成功率", "category": "business", "thresholds": {"crit": 99.0, "warn": 99.5}}, {"name": "business.throughput", "type": "gauge", "unit": "count/min", "display": "业务吞吐量", "category": "business"}, {"name": "business.user_count", "type": "gauge", "unit": "count", "display": "在线用户数", "category": "business"}], "relations": [{"type": "includes", "target": "Service", "dimension": "vertical", "direction": "out"}], "attributes": [{"key": "business_domain", "name": "业务域", "type": "string", "required": false}, {"key": "business_owner", "name": "业务负责人", "type": "string", "required": false}, {"key": "tech_owner", "name": "技术负责人", "type": "string", "required": false}, {"key": "slo_availability", "name": "SLO可用性", "type": "float", "default": 99.9, "required": false}, {"key": "business_weight", "max": 3.0, "min": 0, "name": "业务权重", "type": "float", "default": 1.0, "required": true}]}	业务层实体	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
Service	微服务	application	service	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "performance", "metric": "http.server.request.duration.p99", "weight": 0.30, "category": "performance"}, {"name": "error", "metric": "http.server.request.error_rate", "weight": 0.25, "category": "error"}, {"name": "resource", "metric": "system.cpu.usage", "weight": 0.20, "category": "resource"}, {"name": "business", "metric": "business.order.success_rate", "weight": 0.25, "category": "business"}]}, "metrics": [{"name": "http.server.request.duration.p99", "type": "gauge", "unit": "ms", "display": "P99延迟", "category": "performance", "thresholds": {"crit": 2000, "warn": 500}}, {"name": "http.server.request.duration.p50", "type": "gauge", "unit": "ms", "display": "P50延迟", "category": "performance", "thresholds": {"crit": 800, "warn": 200}}, {"name": "http.server.request.qps", "type": "gauge", "unit": "count/s", "display": "QPS", "category": "performance"}, {"name": "http.server.request.error_rate", "type": "gauge", "unit": "percent", "display": "错误率", "category": "error", "thresholds": {"crit": 5, "warn": 1}}, {"name": "http.server.request.5xx_count", "type": "counter", "unit": "count/min", "display": "5xx错误数", "category": "error", "thresholds": {"rate_crit": 50, "rate_warn": 10}}, {"name": "system.cpu.usage", "type": "gauge", "unit": "percent", "display": "CPU使用率", "category": "resource", "thresholds": {"crit": 90, "warn": 70}}, {"name": "system.memory.usage", "type": "gauge", "unit": "percent", "display": "内存使用率", "category": "resource", "thresholds": {"crit": 95, "warn": 80}}, {"name": "system.disk.usage", "type": "gauge", "unit": "percent", "display": "磁盘使用率", "category": "resource", "thresholds": {"crit": 90, "warn": 80}}, {"name": "jvm.heap.usage", "type": "gauge", "unit": "percent", "display": "JVM堆内存", "category": "resource", "thresholds": {"crit": 90, "warn": 75}}, {"name": "business.order.success_rate", "type": "gauge", "unit": "percent", "display": "业务成功率", "category": "business", "thresholds": {"crit": 95, "warn": 99}}], "relations": [{"type": "calls", "target": "Service", "dimension": "horizontal", "direction": "out"}, {"type": "depends_on", "target": "Database", "dimension": "horizontal", "direction": "out"}, {"type": "depends_on", "target": "Redis", "dimension": "horizontal", "direction": "out"}, {"type": "runs_on", "target": "Host", "dimension": "vertical", "direction": "out"}, {"type": "has_endpoint", "target": "Endpoint", "dimension": "vertical", "direction": "out"}], "templates": ["base_software"], "attributes": [{"key": "language", "name": "编程语言", "type": "string", "required": false}, {"key": "framework", "name": "框架", "type": "string", "required": false}, {"key": "port", "max": 65535, "min": 1, "name": "服务端口", "type": "int", "default": 8080, "required": true}, {"key": "team", "name": "负责团队", "type": "string", "required": false}, {"key": "version", "name": "版本号", "type": "string", "required": false}]}	微服务实例	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
Middleware	中间件	middleware	middleware	\N	[]	{}	{}	中间件实例	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
IP	IP地址	infrastructure	ip	\N	[]	{}	{}	IP地址	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
Host	主机	infrastructure	host	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "cpu", "metric": "system.cpu.usage", "weight": 0.30, "display": "CPU", "category": "compute"}, {"name": "memory", "metric": "system.memory.usage", "weight": 0.25, "display": "内存", "category": "memory"}, {"name": "disk", "metric": "system.disk.usage", "weight": 0.25, "display": "磁盘", "category": "disk"}, {"name": "disk_io", "metric": "system.disk.io.util", "weight": 0.20, "display": "磁盘IO", "category": "disk"}]}, "metrics": [{"name": "system.cpu.usage", "type": "gauge", "unit": "percent", "display": "CPU使用率", "category": "compute", "thresholds": {"crit": 90, "warn": 70}}, {"name": "system.cpu.load.1m", "type": "gauge", "unit": "count", "display": "1分钟负载", "category": "compute"}, {"name": "system.memory.usage", "type": "gauge", "unit": "percent", "display": "内存使用率", "category": "memory", "thresholds": {"crit": 95, "warn": 80}}, {"name": "system.disk.usage", "type": "gauge", "unit": "percent", "display": "磁盘使用率", "category": "disk", "thresholds": {"crit": 90, "warn": 80}}, {"name": "system.disk.io.util", "type": "gauge", "unit": "percent", "display": "磁盘IO利用率", "category": "disk", "thresholds": {"crit": 90, "warn": 70}}, {"name": "system.network.bytes_recv", "type": "gauge", "unit": "MB/s", "display": "网络入流量", "category": "network"}, {"name": "system.network.bytes_sent", "type": "gauge", "unit": "MB/s", "display": "网络出流量", "category": "network"}, {"name": "system.network.packet.loss", "type": "gauge", "unit": "percent", "display": "网络丢包率", "category": "network", "thresholds": {"crit": 1.0, "warn": 0.1}}], "discovery": {"auto_match": ["host.name", "host.ip"], "reconcile_priority": ["qualified_name", "attributes.sn", "attributes.ip", "name"]}, "relations": [{"type": "hosts", "target": "Service", "dimension": "vertical", "direction": "out"}, {"type": "hosts", "target": "Database", "dimension": "vertical", "direction": "out"}, {"type": "hosts", "target": "Redis", "dimension": "vertical", "direction": "out"}, {"type": "connected_to", "target": "NetworkDevice", "dimension": "vertical", "direction": "out"}], "templates": ["base_hardware", "base_cloud"], "attributes": [{"key": "ip", "name": "IP地址", "type": "string", "required": true}, {"key": "cpu_cores", "max": 256, "min": 1, "name": "CPU核数", "type": "int", "required": true}, {"key": "memory_gb", "max": 4096, "min": 1, "name": "内存(GB)", "type": "int", "required": true}, {"key": "disk_gb", "name": "磁盘(GB)", "type": "int", "required": false}, {"key": "os", "name": "操作系统", "type": "string", "required": false}, {"key": "sn", "name": "序列号", "type": "string", "required": false}, {"key": "vendor", "name": "厂商", "type": "string", "required": false}, {"key": "cloud_provider", "name": "云厂商", "type": "string", "required": false}, {"key": "instance_type", "name": "实例规格", "type": "string", "required": false}]}	物理机/虚拟机	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
Database	数据库	middleware	database	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "connections", "weight": 0.3}, {"name": "slow_queries", "weight": 0.3}, {"name": "query_latency", "weight": 0.4}]}, "metrics": [{"name": "db.connections.active", "type": "gauge", "unit": "count", "display": "活跃连接数", "thresholds": {"crit": 95, "warn": 80}}, {"name": "db.queries.slow", "type": "counter", "unit": "count/min", "display": "慢查询数", "thresholds": {"rate_crit": 50, "rate_warn": 10}}], "relations": [{"type": "runs_on", "target": "Host", "direction": "out"}], "templates": ["base_database"], "attributes": [{"key": "db_type", "name": "数据库类型", "type": "string"}, {"key": "port", "name": "端口", "type": "int"}]}	数据库实例	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
MySQL	MySQL	middleware	mysql	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "connections", "metric": "mysql.connections.usage_rate", "weight": 0.20, "display": "连接", "category": "connections"}, {"name": "performance", "metric": "mysql.queries.avg_latency", "weight": 0.25, "display": "性能", "category": "performance"}, {"name": "slow_queries", "metric": "mysql.queries.slow", "weight": 0.20, "display": "慢查询", "category": "performance"}, {"name": "replication", "metric": "mysql.replication.lag", "weight": 0.15, "display": "复制", "category": "replication"}, {"name": "buffer_pool", "metric": "mysql.buffer_pool.hit_rate", "weight": 0.20, "display": "缓存", "category": "performance"}]}, "metrics": [{"name": "mysql.connections.active", "type": "gauge", "unit": "count", "display": "活跃连接数", "category": "connections", "thresholds": {"crit": 480, "warn": 400}}, {"name": "mysql.connections.usage_rate", "type": "gauge", "unit": "percent", "display": "连接使用率", "category": "connections", "thresholds": {"crit": 95, "warn": 80}}, {"name": "mysql.queries.qps", "type": "gauge", "unit": "count/s", "display": "QPS", "category": "performance"}, {"name": "mysql.queries.slow", "type": "counter", "unit": "count/min", "display": "慢查询数", "category": "performance", "thresholds": {"rate_crit": 20, "rate_warn": 5}}, {"name": "mysql.queries.avg_latency", "type": "gauge", "unit": "ms", "display": "平均查询延迟", "category": "performance", "thresholds": {"crit": 500, "warn": 100}}, {"name": "mysql.buffer_pool.hit_rate", "type": "gauge", "unit": "percent", "display": "Buffer Pool命中率", "category": "performance", "thresholds": {"crit": 90, "warn": 95}}, {"name": "mysql.replication.lag", "type": "gauge", "unit": "seconds", "display": "主从延迟", "category": "replication", "thresholds": {"crit": 30, "warn": 5}}, {"name": "mysql.replication.io_running", "type": "gauge", "unit": "bool", "display": "IO线程状态", "category": "replication"}, {"name": "mysql.innodb.row_lock.waited", "type": "counter", "unit": "count/min", "display": "行锁等待", "category": "locks", "thresholds": {"rate_crit": 50, "rate_warn": 10}}], "relations": [{"type": "runs_on", "target": "Host", "dimension": "vertical", "direction": "out"}], "templates": ["base_database"], "attributes": [{"key": "db_version", "name": "数据库版本", "type": "string", "required": false}, {"key": "port", "name": "端口", "type": "int", "default": 3306, "required": true}, {"key": "max_connections", "name": "最大连接数", "type": "int", "default": 500, "required": false}, {"key": "replication_mode", "name": "复制模式", "type": "string", "required": false}], "super_type": "Database"}	MySQL数据库	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
Redis	Redis	middleware	redis	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "memory", "metric": "redis.memory.usage", "weight": 0.25, "display": "内存", "category": "memory"}, {"name": "hit_rate", "metric": "redis.commands.hit_rate", "weight": 0.30, "display": "命中率", "category": "performance"}, {"name": "latency", "metric": "redis.commands.avg_latency", "weight": 0.25, "display": "延迟", "category": "performance"}, {"name": "connections", "metric": "redis.clients.connected", "weight": 0.20, "display": "连接", "category": "connections"}]}, "metrics": [{"name": "redis.memory.usage", "type": "gauge", "unit": "percent", "display": "内存使用率", "category": "memory", "thresholds": {"crit": 90, "warn": 75}}, {"name": "redis.memory.fragmentation_ratio", "type": "gauge", "unit": "ratio", "display": "内存碎片率", "category": "memory", "thresholds": {"crit": 3.0, "warn": 1.5}}, {"name": "redis.commands.qps", "type": "gauge", "unit": "count/s", "display": "命令QPS", "category": "performance"}, {"name": "redis.commands.avg_latency", "type": "gauge", "unit": "ms", "display": "平均延迟", "category": "performance", "thresholds": {"crit": 20, "warn": 5}}, {"name": "redis.commands.hit_rate", "type": "gauge", "unit": "percent", "display": "命中率", "category": "performance", "thresholds": {"crit": 80, "warn": 90}}, {"name": "redis.clients.connected", "type": "gauge", "unit": "count", "display": "连接客户端数", "category": "connections", "thresholds": {"crit": 1000, "warn": 500}}, {"name": "redis.clients.blocked", "type": "gauge", "unit": "count", "display": "阻塞客户端数", "category": "connections", "thresholds": {"crit": 50, "warn": 10}}, {"name": "redis.keyspace.keys", "type": "gauge", "unit": "count", "display": "键总数", "category": "data"}, {"name": "redis.replication.lag", "type": "gauge", "unit": "seconds", "display": "主从延迟", "category": "replication", "thresholds": {"crit": 30, "warn": 5}}], "relations": [{"type": "runs_on", "target": "Host", "dimension": "vertical", "direction": "out"}], "attributes": [{"key": "redis_version", "name": "Redis版本", "type": "string", "required": false}, {"key": "port", "name": "端口", "type": "int", "default": 6379, "required": true}, {"key": "max_memory", "name": "最大内存", "type": "string", "required": false}, {"key": "cluster_mode", "name": "集群模式", "type": "string", "required": false}]}	Redis缓存	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
NetworkDevice	网络设备	infrastructure	network	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "packet_loss", "weight": 0.35}, {"name": "latency", "weight": 0.25}, {"name": "utilization", "weight": 0.20}, {"name": "error_rate", "weight": 0.20}]}, "metrics": [{"name": "network.packet.loss", "type": "gauge", "unit": "percent", "display": "丢包率", "category": "reliability", "thresholds": {"crit": 1.0, "warn": 0.1}}, {"name": "network.latency", "type": "gauge", "unit": "ms", "display": "网络延迟", "category": "performance", "thresholds": {"crit": 50, "warn": 10}}, {"name": "network.bandwidth.utilization", "type": "gauge", "unit": "percent", "display": "带宽利用率", "category": "capacity", "thresholds": {"crit": 90, "warn": 70}}, {"name": "network.error_rate", "type": "gauge", "unit": "percent", "display": "错误率", "category": "reliability", "thresholds": {"crit": 0.1, "warn": 0.01}}, {"name": "network.device.cpu", "type": "gauge", "unit": "percent", "display": "设备CPU", "category": "resource", "thresholds": {"crit": 90, "warn": 70}}], "relations": [{"type": "connected_to", "target": "Host", "dimension": "vertical", "direction": "out"}, {"type": "connected_to", "target": "NetworkDevice", "dimension": "vertical", "direction": "out"}], "templates": ["base_network"]}	网络设备	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
K8sCluster	K8s集群	runtime	k8s	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "cpu", "weight": 0.4}, {"name": "memory", "weight": 0.4}, {"name": "nodes", "weight": 0.2}]}, "metrics": [{"name": "k8s.cpu.utilization", "type": "gauge", "unit": "percent", "display": "CPU利用率", "thresholds": {"crit": 90, "warn": 70}}, {"name": "k8s.memory.utilization", "type": "gauge", "unit": "percent", "display": "内存利用率", "thresholds": {"crit": 95, "warn": 80}}], "relations": [{"type": "contains", "target": "K8sPod", "direction": "out"}], "templates": ["base_container"]}	Kubernetes集群	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
K8sPod	K8s Pod	runtime	pod	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "cpu", "weight": 0.3}, {"name": "memory", "weight": 0.3}, {"name": "restarts", "weight": 0.4}]}, "metrics": [{"name": "k8s.pod.cpu.usage", "type": "gauge", "unit": "millicores", "display": "CPU使用"}, {"name": "k8s.pod.restarts", "type": "counter", "unit": "count", "display": "重启次数", "thresholds": {"rate_crit": 10, "rate_warn": 3}}], "relations": [{"type": "runs", "target": "Service", "direction": "out"}, {"type": "scheduled_on", "target": "Host", "direction": "out"}], "attributes": [{"key": "namespace", "name": "命名空间", "type": "string"}]}	Kubernetes Pod	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
Endpoint	API端点	application	endpoint	\N	[]	{}	{"health": {"method": "weighted_avg", "dimensions": [{"name": "latency", "weight": 0.40}, {"name": "error_rate", "weight": 0.35}, {"name": "qps", "weight": 0.25}]}, "metrics": [{"name": "endpoint.request.duration.p99", "type": "gauge", "unit": "ms", "display": "P99延迟", "category": "performance", "thresholds": {"crit": 2000, "warn": 500}}, {"name": "endpoint.request.qps", "type": "gauge", "unit": "count/s", "display": "QPS", "category": "performance"}, {"name": "endpoint.request.error_rate", "type": "gauge", "unit": "percent", "display": "错误率", "category": "error", "thresholds": {"crit": 5, "warn": 1}}], "relations": [{"type": "belongs_to", "target": "Service", "dimension": "vertical", "direction": "in"}, {"type": "calls", "target": "Endpoint", "dimension": "horizontal", "direction": "out"}], "attributes": [{"key": "method", "name": "HTTP方法", "type": "string", "required": true}, {"key": "path", "name": "URL路径", "type": "string", "required": true}, {"key": "service", "name": "所属服务", "type": "string", "required": true}]}	API端点	f	1	2026-04-07 23:41:14.312968+00	2026-04-07 23:41:14.312968+00
ContainerGroup	容器组	runtime	container	\N	[]	{}	{"health": {"method": "children_avg"}, "relations": [{"type": "contains", "target": "LoadBalancer", "dimension": "vertical", "direction": "out"}, {"type": "contains", "target": "K8sPod", "dimension": "vertical", "direction": "out"}, {"type": "hosts", "target": "Service", "dimension": "vertical", "direction": "out"}], "templates": ["base_container"], "attributes": [{"key": "namespace", "name": "命名空间", "type": "string"}, {"key": "replicas", "name": "副本数", "type": "int", "default": 3}]}	容器组/部署单元	f	1	2026-04-23 07:03:15.665431+00	2026-04-23 07:03:15.665431+00
LoadBalancer	负载均衡器	runtime	cloud	\N	[]	{}	{"health": {"method": "weighted_avg"}, "relations": [{"type": "contains", "target": "ContainerInstance", "dimension": "vertical", "direction": "out"}], "templates": ["base_network"], "attributes": [{"key": "lb_type", "name": "类型", "type": "string"}, {"key": "algorithm", "name": "调度算法", "type": "string"}]}	负载均衡器	f	1	2026-04-23 07:03:15.665431+00	2026-04-23 07:03:15.665431+00
ContainerInstance	容器实例	runtime	container	\N	[]	{}	{"health": {"method": "weighted_avg"}, "relations": [{"type": "runs_on", "target": "Host", "dimension": "vertical", "direction": "out"}, {"type": "runs", "target": "Process", "dimension": "vertical", "direction": "out"}], "attributes": [{"key": "container_id", "name": "容器ID", "type": "string"}, {"key": "image", "name": "镜像", "type": "string"}]}	容器实例	f	1	2026-04-23 07:03:15.665431+00	2026-04-23 07:03:15.665431+00
Process	进程	runtime	code	\N	[]	{}	{"health": {"method": "weighted_avg"}, "metrics": [{"name": "process.cpu.usage", "type": "gauge", "unit": "percent", "display": "CPU使用率"}, {"name": "process.memory.usage", "type": "gauge", "unit": "percent", "display": "内存使用率"}], "relations": [{"type": "allocated_to", "target": "Host", "dimension": "vertical", "direction": "out"}], "attributes": [{"key": "pid", "name": "进程ID", "type": "int"}, {"key": "command", "name": "命令", "type": "string"}]}	进程实例	f	1	2026-04-23 07:03:15.665431+00	2026-04-23 07:03:15.665431+00
\.


--
-- Data for Name: label_definition; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.label_definition (label_key, label_name, value_type, enum_values, description, created_by, created_at) FROM stdin;
env	环境	enum	["prod", "staging", "dev", "test"]	部署环境	\N	2026-04-08 00:00:53.420545+00
team	团队	string	\N	负责团队	\N	2026-04-08 00:00:53.420545+00
business_line	业务线	string	\N	业务归属	\N	2026-04-08 00:00:53.420545+00
region	地域	string	\N	部署地域	\N	2026-04-08 00:00:53.420545+00
tenant	租户	string	\N	多租户隔离标识	\N	2026-04-08 00:00:53.420545+00
project	项目	string	\N	项目归属	\N	2026-04-08 00:00:53.420545+00
app_version	应用版本	string	\N	应用发布版本	\N	2026-04-08 00:00:53.420545+00
\.


--
-- Data for Name: relationship; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.relationship (guid, type_name, end1_guid, end2_guid, from_guid, to_guid, attributes, source, confidence, dimension, is_active, first_seen, last_seen, expired_at, verified_by, verified_at, created_at, call_type) FROM stdin;
c3be95b9-1b9d-4277-ab3c-a1c498c02448	runs_on	0d404cb3-a332-4f2e-bd08-fa711958b69f	98d9c92c-3f71-4a60-b9c4-a791b009151c	0d404cb3-a332-4f2e-bd08-fa711958b69f	98d9c92c-3f71-4a60-b9c4-a791b009151c	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
e0121c2a-2685-4769-8410-16e4a82ad5f3	runs_on	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	f729746a-9416-4b17-b4de-55688621630e	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	f729746a-9416-4b17-b4de-55688621630e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
4808ce4b-46c6-441a-9ec9-fe2485936e2f	runs_on	18702e75-6824-4a92-8fe2-c5c959ec485e	ecb21a4b-1a02-40c1-a885-0bb7516f6830	18702e75-6824-4a92-8fe2-c5c959ec485e	ecb21a4b-1a02-40c1-a885-0bb7516f6830	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
8e31bc5d-f271-4fd8-a182-2605b8013af2	runs_on	9449aef0-600e-4b7c-8ae8-16afead6b347	ecb21a4b-1a02-40c1-a885-0bb7516f6830	9449aef0-600e-4b7c-8ae8-16afead6b347	ecb21a4b-1a02-40c1-a885-0bb7516f6830	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
69338e00-df5a-4ba7-a0db-631bd7c3b984	runs_on	54b0a994-7727-44f4-acd7-63b1f79d88d0	da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	54b0a994-7727-44f4-acd7-63b1f79d88d0	da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
7e0e078f-9507-4529-9304-3461b305ead4	runs_on	9dddd323-9390-436b-9f7f-f8632318084e	da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	9dddd323-9390-436b-9f7f-f8632318084e	da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
04d86033-0d48-4659-9d38-d2c031a929f0	connected_to	98d9c92c-3f71-4a60-b9c4-a791b009151c	2d889e09-8867-47ea-ba94-e7be307cff3e	98d9c92c-3f71-4a60-b9c4-a791b009151c	2d889e09-8867-47ea-ba94-e7be307cff3e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
fc5fad5d-ca10-40eb-b2e7-ec0d310e6eb0	connected_to	f729746a-9416-4b17-b4de-55688621630e	2d889e09-8867-47ea-ba94-e7be307cff3e	f729746a-9416-4b17-b4de-55688621630e	2d889e09-8867-47ea-ba94-e7be307cff3e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
11e02b30-98f3-4763-9677-305ae7857c28	connected_to	ecb21a4b-1a02-40c1-a885-0bb7516f6830	2d889e09-8867-47ea-ba94-e7be307cff3e	ecb21a4b-1a02-40c1-a885-0bb7516f6830	2d889e09-8867-47ea-ba94-e7be307cff3e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
08a5dc42-b9c5-4713-993c-26a3924a999b	connected_to	da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	2d889e09-8867-47ea-ba94-e7be307cff3e	da9cb5b9-e8b8-41c0-b1f1-2c91dffe3b24	2d889e09-8867-47ea-ba94-e7be307cff3e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	\N
76acaadb-c3a8-4c9a-ad3c-d250447233df	includes	176a52d7-7150-4afa-8015-e11e2b44c153	0d404cb3-a332-4f2e-bd08-fa711958b69f	176a52d7-7150-4afa-8015-e11e2b44c153	0d404cb3-a332-4f2e-bd08-fa711958b69f	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
1d7ebb81-20b8-4ed4-a5d2-5f92c4a4bcd6	includes	176a52d7-7150-4afa-8015-e11e2b44c153	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	176a52d7-7150-4afa-8015-e11e2b44c153	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
44ea7e99-0357-4b6f-9648-733c433a15be	includes	176a52d7-7150-4afa-8015-e11e2b44c153	18702e75-6824-4a92-8fe2-c5c959ec485e	176a52d7-7150-4afa-8015-e11e2b44c153	18702e75-6824-4a92-8fe2-c5c959ec485e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
596acbbb-ebff-4790-b605-2426b532e135	includes	a57cd333-c346-4081-bcb7-369f9dd7c87e	9449aef0-600e-4b7c-8ae8-16afead6b347	a57cd333-c346-4081-bcb7-369f9dd7c87e	9449aef0-600e-4b7c-8ae8-16afead6b347	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
dda39e29-7980-4ad9-8e27-c2a64fa81555	calls	0d404cb3-a332-4f2e-bd08-fa711958b69f	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	0d404cb3-a332-4f2e-bd08-fa711958b69f	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
29ea8724-c46c-486a-9c8e-c5662bac9642	calls	0d404cb3-a332-4f2e-bd08-fa711958b69f	18702e75-6824-4a92-8fe2-c5c959ec485e	0d404cb3-a332-4f2e-bd08-fa711958b69f	18702e75-6824-4a92-8fe2-c5c959ec485e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
0f6194d4-d75d-459d-a447-76092e11d99f	depends_on	18702e75-6824-4a92-8fe2-c5c959ec485e	54b0a994-7727-44f4-acd7-63b1f79d88d0	18702e75-6824-4a92-8fe2-c5c959ec485e	54b0a994-7727-44f4-acd7-63b1f79d88d0	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
accfaf5b-954a-4048-95d4-e49fb822811b	depends_on	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	9dddd323-9390-436b-9f7f-f8632318084e	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	9dddd323-9390-436b-9f7f-f8632318084e	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
b5f6df24-0b86-4ae2-94d7-6198264c3e0f	depends_on	9449aef0-600e-4b7c-8ae8-16afead6b347	2f9f6d43-394f-43de-b9dc-7645f5195a0c	9449aef0-600e-4b7c-8ae8-16afead6b347	2f9f6d43-394f-43de-b9dc-7645f5195a0c	{}	demo	1	vertical	t	2026-04-08 00:07:47.90147+00	2026-04-08 00:07:47.90147+00	\N	\N	\N	2026-04-08 00:07:47.90147+00	sync
9419c3d5-c220-43b8-9be1-a7a470c90dc7	calls	\N	\N	18702e75-6824-4a92-8fe2-c5c959ec485e	0d404cb3-a332-4f2e-bd08-fa711958b69f	{}	demo	1	horizontal	t	2026-04-28 10:07:59.637821+00	2026-04-28 10:07:59.637821+00	\N	\N	\N	2026-04-28 10:07:59.637821+00	\N
24cba3fb-b77b-439c-992e-7b2bcde19061	calls	\N	\N	0d404cb3-a332-4f2e-bd08-fa711958b69f	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	{}	demo	1	horizontal	t	2026-04-28 10:07:59.903697+00	2026-04-28 10:07:59.903697+00	\N	\N	\N	2026-04-28 10:07:59.903697+00	\N
c5676b69-c6b7-4c40-b12d-b97ab5da6c3d	calls	\N	\N	0d404cb3-a332-4f2e-bd08-fa711958b69f	18702e75-6824-4a92-8fe2-c5c959ec485e	{}	demo	1	horizontal	t	2026-04-28 10:08:00.141727+00	2026-04-28 10:08:00.141727+00	\N	\N	\N	2026-04-28 10:08:00.141727+00	\N
664e7fbe-de57-403a-934e-3e97f5d222a8	calls	\N	\N	3f5cc6cc-faa6-4cec-ae6a-95e225d8f197	9dddd323-9390-436b-9f7f-f8632318084e	{}	demo	1	horizontal	t	2026-04-28 10:08:00.41855+00	2026-04-28 10:08:00.41855+00	\N	\N	\N	2026-04-28 10:08:00.41855+00	\N
7433be49-6364-4652-9d35-256a4be894bb	calls	\N	\N	18702e75-6824-4a92-8fe2-c5c959ec485e	54b0a994-7727-44f4-acd7-63b1f79d88d0	{}	demo	1	horizontal	t	2026-04-28 10:08:00.670497+00	2026-04-28 10:08:00.670497+00	\N	\N	\N	2026-04-28 10:08:00.670497+00	\N
9b9a7739-0ce7-430a-8345-a68e125ee8a7	calls	\N	\N	18702e75-6824-4a92-8fe2-c5c959ec485e	9449aef0-600e-4b7c-8ae8-16afead6b347	{}	demo	1	horizontal	t	2026-04-28 10:08:00.920555+00	2026-04-28 10:08:00.920555+00	\N	\N	\N	2026-04-28 10:08:00.920555+00	\N
998e82c7-7005-4a24-91eb-6dceaf4b87f3	calls	\N	\N	98d9c92c-3f71-4a60-b9c4-a791b009151c	0d404cb3-a332-4f2e-bd08-fa711958b69f	{}	demo	1	horizontal	t	2026-04-28 10:08:01.175841+00	2026-04-28 10:08:01.175841+00	\N	\N	\N	2026-04-28 10:08:01.175841+00	\N
53edea44-4d08-4c75-a6d3-3a3f8f1db063	calls	\N	\N	0cd4becb-ee8d-4167-8845-67cabfd2be90	0d404cb3-a332-4f2e-bd08-fa711958b69f	{}	demo	1	horizontal	t	2026-04-28 10:08:01.41019+00	2026-04-28 10:08:01.41019+00	\N	\N	\N	2026-04-28 10:08:01.41019+00	\N
b69c8098-687f-4e99-9be9-e4bc7014f70b	calls	\N	\N	f729746a-9416-4b17-b4de-55688621630e	0d404cb3-a332-4f2e-bd08-fa711958b69f	{}	demo	1	horizontal	t	2026-04-28 10:08:01.660207+00	2026-04-28 10:08:01.660207+00	\N	\N	\N	2026-04-28 10:08:01.660207+00	\N
14b2a9bc-f912-4963-a7b3-a300adf04d34	calls	\N	\N	ecb21a4b-1a02-40c1-a885-0bb7516f6830	0d404cb3-a332-4f2e-bd08-fa711958b69f	{}	demo	1	horizontal	t	2026-04-28 10:08:01.901485+00	2026-04-28 10:08:01.901485+00	\N	\N	\N	2026-04-28 10:08:01.901485+00	\N
\.


--
-- Data for Name: relationship_type_def; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.relationship_type_def (type_name, end1_type, end1_name, end2_type, end2_name, description) FROM stdin;
runs_on	Application	app	Host	host	应用运行在主机上
Host_runs	Host	host	Application	app	主机运行应用
includes	Business	biz	Service	service	业务包含服务
hosts	Host	host	Service	service	主机承载服务
connected_to	Host	host	NetworkDevice	device	主机连接网络设备
contains	K8sCluster	cluster	K8sPod	pod	集群包含Pod
scheduled_on	K8sPod	pod	Host	node	Pod调度到节点
runs	K8sPod	pod	Service	service	Pod运行服务
calls	Service	caller	Service	callee	服务间同步调用（横向）
depends_on	Service	service	Database	db	服务依赖数据库（横向）
has_endpoint	Service	service	Endpoint	endpoint	服务提供接口
belongs_to	Endpoint	endpoint	Service	service	接口归属服务
async_calls	Service	caller	Service	callee	服务间异步调用(MQ)
\.


--
-- Name: attribute_template attribute_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_template
    ADD CONSTRAINT attribute_template_pkey PRIMARY KEY (template_name);


--
-- Name: cmdb_event_log cmdb_event_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cmdb_event_log
    ADD CONSTRAINT cmdb_event_log_pkey PRIMARY KEY (event_id);


--
-- Name: cmdb_event_subscription cmdb_event_subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cmdb_event_subscription
    ADD CONSTRAINT cmdb_event_subscription_pkey PRIMARY KEY (subscription_id);


--
-- Name: data_check_rule data_check_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_check_rule
    ADD CONSTRAINT data_check_rule_pkey PRIMARY KEY (rule_id);


--
-- Name: data_quality_snapshot data_quality_snapshot_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_quality_snapshot
    ADD CONSTRAINT data_quality_snapshot_pkey PRIMARY KEY (snapshot_id);


--
-- Name: entity entity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity
    ADD CONSTRAINT entity_pkey PRIMARY KEY (guid);


--
-- Name: entity entity_qualified_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity
    ADD CONSTRAINT entity_qualified_name_key UNIQUE (qualified_name);


--
-- Name: entity_type_def entity_type_def_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_type_def
    ADD CONSTRAINT entity_type_def_pkey PRIMARY KEY (type_name);


--
-- Name: label_definition label_definition_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.label_definition
    ADD CONSTRAINT label_definition_pkey PRIMARY KEY (label_key);


--
-- Name: relationship relationship_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_pkey PRIMARY KEY (guid);


--
-- Name: relationship_type_def relationship_type_def_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.relationship_type_def
    ADD CONSTRAINT relationship_type_def_pkey PRIMARY KEY (type_name);


--
-- Name: idx_entity_biz; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_biz ON public.entity USING btree (biz_service) WHERE (biz_service IS NOT NULL);


--
-- Name: idx_entity_health; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_health ON public.entity USING btree (health_level) WHERE ((health_level)::text = ANY ((ARRAY['warning'::character varying, 'critical'::character varying, 'down'::character varying])::text[]));


--
-- Name: idx_entity_labels; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_labels ON public.entity USING gin (labels);


--
-- Name: idx_entity_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_name ON public.entity USING btree (name);


--
-- Name: idx_entity_risk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_risk ON public.entity USING btree (risk_score DESC) WHERE (risk_score > 50);


--
-- Name: idx_entity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_type ON public.entity USING btree (type_name);


--
-- Name: idx_event_log_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_log_status ON public.cmdb_event_log USING btree (status) WHERE ((status)::text = 'pending'::text);


--
-- Name: entity entity_type_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity
    ADD CONSTRAINT entity_type_name_fkey FOREIGN KEY (type_name) REFERENCES public.entity_type_def(type_name);


--
-- Name: relationship relationship_end1_guid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_end1_guid_fkey FOREIGN KEY (end1_guid) REFERENCES public.entity(guid);


--
-- Name: relationship relationship_end2_guid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_end2_guid_fkey FOREIGN KEY (end2_guid) REFERENCES public.entity(guid);


--
-- Name: relationship relationship_from_guid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_from_guid_fkey FOREIGN KEY (from_guid) REFERENCES public.entity(guid);


--
-- Name: relationship relationship_to_guid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_to_guid_fkey FOREIGN KEY (to_guid) REFERENCES public.entity(guid);


--
-- PostgreSQL database dump complete
--

\unrestrict txIMcD2ybmLP37FQD6i5yXXArnGfGIZS8taRzWYw12H29A9s9p1V009CFeeOaiX

