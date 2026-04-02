#!/usr/bin/env python3
"""
APM 堆栈快照 + 数据类型识别 Demo。

1. 注入堆栈快照数据（模拟 Java/Python 异常堆栈）
2. 注入 records（stack_snapshot 类型）
3. 演示数据类型自动识别逻辑
"""

import os
import uuid
import json
import random
from datetime import datetime, timedelta

import httpx

CH = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")

# ============================================================
# 堆栈快照模板
# ============================================================

JAVA_STACK = """java.sql.SQLException: Connection refused: payment-db:3306
  at com.mysql.cj.jdbc.exceptions.SQLError.createSQLException(SQLError.java:129)
  at com.mysql.cj.jdbc.exceptions.SQLError.createSQLException(SQLError.java:97)
  at com.mysql.cj.jdbc.exceptions.SQLExceptionsMapping.translateException(SQLExceptionsMapping.java:122)
  at com.mysql.cj.jdbc.ConnectionImpl.createNewIO(ConnectionImpl.java:836)
  at com.mysql.cj.jdbc.ConnectionImpl.<init>(ConnectionImpl.java:456)
  at com.mysql.cj.jdbc.ConnectionImpl.getInstance(ConnectionImpl.java:246)
  at com.mysql.cj.jdbc.NonRegisteringDriver.connect(NonRegisteringDriver.java:198)
  at java.sql.DriverManager.getConnection(DriverManager.java:677)
  at java.sql.DriverManager.getConnection(DriverManager.java:228)
  at com.zaxxer.hikari.pool.PoolBase.newConnection(PoolBase.java:364)
  at com.zaxxer.hikari.pool.PoolEntry.newPoolEntry(PoolEntry.java:126)
  at com.zaxxer.hikari.pool.HikariPool.createPoolEntry(HikariPool.java:476)
  at com.zaxxer.hikari.pool.HikariPool.access$100(HikariPool.java:71)
  at com.zaxxer.hikari.pool.HikariPool$PoolEntryCreator.call(HikariPool.java:728)
  at com.zaxxer.hikari.pool.HikariPool$PoolEntryCreator.call(HikariPool.java:714)
  at java.util.concurrent.FutureTask.run(FutureTask.java:264)
  at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1128)
  at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:628)
  at java.lang.Thread.run(Thread.java:829)
Caused by: java.net.ConnectException: Connection refused (Connection refused)
  at java.net.PlainSocketImpl.socketConnect(Native Method)
  at java.net.AbstractPlainSocketImpl.doConnect(AbstractPlainSocketImpl.java:350)
  at java.net.AbstractPlainSocketImpl.connectToAddress(AbstractPlainSocketImpl.java:206)
  at java.net.AbstractPlainSocketImpl.connect(AbstractPlainSocketImpl.java:188)
  at java.net.SocksSocketImpl.connect(SocksSocketImpl.java:392)
  at java.net.Socket.connect(Socket.java:607)
  at com.mysql.cj.protocol.StandardSocketFactory.connect(StandardSocketFactory.java:153)
  at com.mysql.cj.protocol.a.NativeSocketConnection.connect(NativeSocketConnection.java:63)
  ... 23 more"""

PYTHON_STACK = """Traceback (most recent call last):
  File "/app/services/user_service.py", line 142, in get_user_profile
    cached = redis_client.get(f"user:{user_id}")
  File "/usr/local/lib/python3.11/site-packages/redis/client.py", line 1590, in get
    return self.execute_command('GET', name)
  File "/usr/local/lib/python3.11/site-packages/redis/client.py", line 1258, in execute_command
    return self._execute_command(*args, **options)
  File "/usr/local/lib/python3.11/site-packages/redis/client.py", line 1264, in _execute_command
    connection = self.get_connection()
  File "/usr/local/lib/python3.11/site-packages/redis/client.py", line 1306, in get_connection
    raise ConnectionError(f"Error {err} connecting to {host}:{port}. {err_msg}")
redis.exceptions.ConnectionError: Error 111 connecting to user-cache:6379. Connection refused.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/app/services/user_service.py", line 148, in get_user_profile
    logger.error(f"Cache miss for user {user_id}, falling back to DB")
  File "/app/services/user_service.py", line 89, in _fallback_db
    user = db.query(User).filter(User.id == user_id).first()
  File "/usr/local/lib/python3.11/site-packages/sqlalchemy/orm/query.py", line 2872, in first
    return self.limit(1)._iter().first()
  File "/usr/local/lib/python3.11/site-packages/sqlalchemy/orm/query.py", line 2956, in _iter
    result = self.session.execute(
  File "/usr/local/lib/python3.11/site-packages/sqlalchemy/orm/session.py", line 1716, in execute
    result = conn._execute_20(statement, params or {}, execution_options)
  File "/usr/local/lib/python3.11/site-packages/sqlalchemy/engine/base.py", line 1705, in _execute_20
    meth = statement._execute_non_select(
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server: Connection refused
  Is the server running on host "user-db" (10.0.1.31) and accepting TCP/IP connections on port 5432?"""

SLOW_QUERY_STACK = """java.lang.RuntimeException: Slow query detected: execution time 4832ms
  at com.monitoring.etl.interceptor.SlowQueryInterceptor.afterQuery(SlowQueryInterceptor.java:67)
  at com.zaxxer.hikari.pool.HikariProxyPreparedStatement.executeQuery(HikariProxyPreparedStatement.java:94)
  at com.example.payment.repository.PaymentRepository.findByOrderId(PaymentRepository.java:89)
  at com.example.payment.service.PaymentService.processRefund(PaymentService.java:234)
  at com.example.payment.controller.PaymentController.refund(PaymentController.java:78)
  at jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
  at jdk.internal.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:62)
  at jdk.internal.reflect.DelegatingMethodAccessorImpl.invoke(DelegatingMethodAccessorImpl.java:43)
  at java.lang.reflect.Method.invoke(Method.java:566)
  at org.springframework.web.method.support.InvocableHandlerMethod.doInvoke(InvocableHandlerMethod.java:205)
  at org.springframework.web.method.support.InvocableHandlerMethod.invokeForRequest(InvocableHandlerMethod.java:150)
  at org.springframework.web.servlet.mvc.method.annotation.ServletInvocableHandlerMethod.invokeAndHandle(ServletInvocableHandlerMethod.java:117)
  at org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter.invokeHandlerMethod(RequestMappingHandlerAdapter.java:895)
  at org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter.handleInternal(RequestMappingHandlerAdapter.java:808)
  at org.springframework.web.servlet.mvc.method.annotation.AbstractHandlerMethodAdapter.handle(AbstractHandlerMethodAdapter.java:87)
  at org.springframework.web.servlet.DispatcherServlet.doDispatch(DispatcherServlet.java:1067)
  at org.springframework.web.servlet.DispatcherServlet.doService(DispatcherServlet.java:963)
  at org.springframework.web.servlet.FrameworkServlet.processRequest(FrameworkServlet.java:1006)
  at org.springframework.web.servlet.FrameworkServlet.doPost(FrameworkServlet.java:909)
  at javax.servlet.http.HttpServlet.service(HttpServlet.java:660)
  at javax.servlet.http.HttpServlet.service(HttpServlet.java:741)
  at org.apache.catalina.core.ApplicationFilterChain.internalDoFilter(ApplicationFilterChain.java:231)
  at org.apache.catalina.core.ApplicationFilterChain.doFilter(ApplicationFilterChain.java:166)

Query: SELECT p.* FROM payments p WHERE p.order_id = ? AND p.status IN ('pending', 'processing') FOR UPDATE
Parameters: [38291]
Duration: 4832ms
Rows: 1
Connection: payment-db:3306 (pool: 8/10 active)"""


# ============================================================
# 数据类型识别引擎
# ============================================================

def detect_data_types(raw_text: str) -> dict:
    """
    自动识别文本中包含的数据类型。

    返回: {
        "detected_types": ["stack_trace", "sql_query", "error", ...],
        "parsed": { ... },
        "confidence": 0.95
    }
    """
    detected = []
    parsed = {}
    confidence = 0.0

    # 1. Java 堆栈
    if "at " in raw_text and ("java." in raw_text or "org." in raw_text or "com." in raw_text):
        detected.append("java_stack_trace")
        # 提取异常类型
        lines = raw_text.strip().split("\n")
        for line in lines:
            if ":" in line and "at " not in line and not line.startswith("  "):
                parsed["exception_type"] = line.split(":")[0].strip()
                parsed["exception_message"] = ":".join(line.split(":")[1:]).strip()
                break
        # 提取最后调用位置
        for line in lines:
            if line.strip().startswith("at "):
                parsed["top_of_stack"] = line.strip()[3:]
                break
        confidence = max(confidence, 0.95)

    # 2. Python 堆栈
    if "Traceback (most recent call last):" in raw_text:
        detected.append("python_stack_trace")
        lines = raw_text.strip().split("\n")
        for line in reversed(lines):
            if line and not line.startswith("  ") and not line.startswith("Traceback"):
                parsed["exception_type"] = line.split(":")[0].strip()
                parsed["exception_message"] = ":".join(line.split(":")[1:]).strip()
                break
        # 提取文件和行号
        import re
        file_matches = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', raw_text)
        if file_matches:
            parsed["crash_location"] = f"{file_matches[-1][0]}:{file_matches[-1][1]} in {file_matches[-1][2]}"
        confidence = max(confidence, 0.95)

    # 3. SQL 查询
    import re
    sql_match = re.search(r'(SELECT|INSERT|UPDATE|DELETE|CREATE)\s+.+', raw_text, re.IGNORECASE)
    if sql_match:
        detected.append("sql_query")
        parsed["sql"] = sql_match.group(0).strip()[:200]
        confidence = max(confidence, 0.8)

    # 4. HTTP 请求
    http_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)', raw_text)
    if http_match:
        detected.append("http_request")
        parsed["http_method"] = http_match.group(1)
        parsed["http_path"] = http_match.group(2)
        confidence = max(confidence, 0.7)

    # 5. 连接错误
    if "Connection refused" in raw_text or "connection refused" in raw_text:
        detected.append("connection_error")
        conn_match = re.search(r'(\S+):(\d+)', raw_text)
        if conn_match:
            parsed["target_host"] = conn_match.group(1)
            parsed["target_port"] = conn_match.group(2)
        confidence = max(confidence, 0.9)

    # 6. 超时
    if "timeout" in raw_text.lower() or "Timeout" in raw_text:
        detected.append("timeout")
        timeout_match = re.search(r'(\d+)\s*ms', raw_text)
        if timeout_match:
            parsed["timeout_ms"] = int(timeout_match.group(1))
        confidence = max(confidence, 0.85)

    # 7. 慢查询
    if "Slow query" in raw_text or ("Duration:" in raw_text):
        detected.append("slow_query")
        dur_match = re.search(r'Duration:\s*(\d+)ms', raw_text)
        if dur_match:
            parsed["query_duration_ms"] = int(dur_match.group(1))
        confidence = max(confidence, 0.9)

    # 8. 指标数据 (key=value 模式)
    metric_matches = re.findall(r'(\w[\w.]*)\s*[=:]\s*([\d.]+)', raw_text)
    if len(metric_matches) >= 2:
        detected.append("metrics")
        parsed["metrics"] = {k: float(v) for k, v in metric_matches[:10]}
        confidence = max(confidence, 0.6)

    return {
        "detected_types": detected,
        "parsed": parsed,
        "confidence": round(confidence, 2),
        "text_length": len(raw_text),
    }


def main():
    print("🧪 数据类型识别测试\n")

    test_cases = [
        ("Java 堆栈 (DB连接失败)", JAVA_STACK),
        ("Python 堆栈 (Redis+DB双失败)", PYTHON_STACK),
        ("慢查询堆栈", SLOW_QUERY_STACK),
    ]

    for name, text in test_cases:
        result = detect_data_types(text)
        print(f"--- {name} ---")
        print(f"  检测类型: {result['detected_types']}")
        print(f"  置信度: {result['confidence']}")
        print(f"  解析结果: {json.dumps(result['parsed'], ensure_ascii=False, indent=4)}")
        print()

    # 注入堆栈快照到 records 表
    print("📊 注入堆栈快照到 records 表...")

    now = datetime.now()
    snapshots = [
        {
            "stack": JAVA_STACK,
            "service": "payment-service",
            "trace_id": uuid.uuid4().hex[:32],
            "span_name": "POST /payments/charge",
            "time_offset": 25,  # 分钟前
        },
        {
            "stack": PYTHON_STACK,
            "service": "user-service",
            "trace_id": uuid.uuid4().hex[:32],
            "span_name": "GET /users/profile",
            "time_offset": 32,
        },
        {
            "stack": SLOW_QUERY_STACK,
            "service": "payment-service",
            "trace_id": uuid.uuid4().hex[:32],
            "span_name": "POST /payments/refund",
            "time_offset": 28,
        },
    ]

    def escape(v):
        s = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        return f"'{s}'"

    for snap in snapshots:
        ts = now - timedelta(minutes=snap["time_offset"])
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        detection = detect_data_types(snap["stack"])

        sql = f"""INSERT INTO records (
            record_id, record_type, source, timestamp,
            entity_name, entity_type,
            severity, title, content, fingerprint
        ) VALUES (
            '{uuid.uuid4()}', 'stack_snapshot', 'apm-agent', '{ts_str}',
            {escape(snap["service"])}, 'Service',
            'critical', {escape(f'{snap["service"]}: {detection["parsed"].get("exception_type", "error")}')},
            {escape(json.dumps({"trace_id": snap["trace_id"], "span_name": snap["span_name"], "stack": snap["stack"], "detection": detection}, ensure_ascii=False))},
            '{uuid.uuid4().hex[:16]}'
        )"""
        try:
            with httpx.Client(timeout=10) as client:
                r = client.post(CH, data=sql.encode("utf-8"))
                status = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
                print(f"  {status} {snap['service']}: {detection['parsed'].get('exception_type', '?')}")
        except Exception as e:
            print(f"  ⚠️ {e}")

    # 也更新 spans 的 status_message 带上堆栈摘要
    print("\n📊 更新 error spans 的 status_message（附堆栈摘要）...")
    for snap in snapshots:
        detection = detect_data_types(snap["stack"])
        summary = f"{detection['parsed'].get('exception_type', 'Error')}: {detection['parsed'].get('exception_message', '')[:80]}"
        crash = detection['parsed'].get('crash_location', detection['parsed'].get('top_of_stack', ''))
        if crash:
            summary += f" | at {crash[:60]}"

        sql = f"""ALTER TABLE traces.spans
        UPDATE
            status_message = {escape(summary)},
            attributes = {escape(json.dumps({"stack_trace": snap["stack"][:500], "detection": detection}, ensure_ascii=False))}
        WHERE trace_id = {escape(snap["trace_id"])}
          AND service_name = {escape(snap["service"])}
          AND status_code = 'error'"""
        try:
            with httpx.Client(timeout=10) as client:
                r = client.post(CH, data=sql.encode("utf-8"))
                status = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
                print(f"  {status} {snap['service']} span updated")
        except Exception as e:
            print(f"  ⚠️ {e}")

    print("\n🎉 完成！")
    print(f"  records 中新增 stack_snapshot 类型数据")
    print(f"  数据类型识别引擎可识别: java_stack_trace, python_stack_trace, sql_query, http_request, connection_error, timeout, slow_query, metrics")


if __name__ == "__main__":
    main()
