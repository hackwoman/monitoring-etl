"""属性元数据定义 - Phase 4.2 属性增加类型约束、必填检查、默认值。"""
from typing import Any, Optional, List
from pydantic import BaseModel, Field


# 属性数据类型
ATTRIBUTE_TYPES = {
    "string": "字符串",
    "int": "整数",
    "float": "浮点数",
    "bool": "布尔值",
    "enum": "枚举",
    "list": "列表",
    "dict": "字典",
    "ip": "IP 地址",
    "url": "URL",
    "port": "端口号",
    "email": "邮箱",
    "datetime": "日期时间",
}


class AttributeMetadata(BaseModel):
    """属性元数据定义。"""
    key: str = Field(..., description="属性键名")
    name: str = Field(..., description="显示名称")
    type: str = Field(default="string", description="数据类型")
    required: bool = Field(default=False, description="是否必填")
    default: Optional[Any] = Field(None, description="默认值")
    description: Optional[str] = Field(None, description="属性描述")
    
    # 约束条件
    min: Optional[float] = Field(None, description="最小值 (数值类型)")
    max: Optional[float] = Field(None, description="最大值 (数值类型)")
    min_length: Optional[int] = Field(None, description="最小长度 (字符串)")
    max_length: Optional[int] = Field(None, description="最大长度 (字符串)")
    pattern: Optional[str] = Field(None, description="正则表达式 (字符串)")
    enum_values: Optional[List[str]] = Field(None, description="枚举值列表")
    
    # 填充规则
    fill_rule: str = Field(default="manual", description="填充方式: manual/auto_discover/api/inherited")
    editable: bool = Field(default=True, description="是否可编辑")
    visible: bool = Field(default=True, description="是否可见")
    
    # UI 配置
    group: Optional[str] = Field(None, description="分组名称")
    order: int = Field(default=0, description="排序权重")
    placeholder: Optional[str] = Field(None, description="输入提示")
    
    # 健康度相关
    health_factor: bool = Field(default=False, description="是否参与健康度计算")
    threshold_scale_key: bool = Field(default=False, description="是否可作为指标阈值的缩放因子")


def validate_attribute_value(metadata: AttributeMetadata, value: Any) -> tuple[bool, str]:
    """校验属性值是否符合元数据定义。"""
    if value is None:
        if metadata.required:
            return False, f"属性 '{metadata.name}' 是必填项"
        return True, ""
    
    # 类型校验
    if metadata.type == "string":
        if not isinstance(value, str):
            return False, f"属性 '{metadata.name}' 必须是字符串类型"
        if metadata.min_length and len(value) < metadata.min_length:
            return False, f"属性 '{metadata.name}' 长度不能小于 {metadata.min_length}"
        if metadata.max_length and len(value) > metadata.max_length:
            return False, f"属性 '{metadata.name}' 长度不能大于 {metadata.max_length}"
        if metadata.pattern:
            import re
            if not re.match(metadata.pattern, value):
                return False, f"属性 '{metadata.name}' 格式不正确"
    
    elif metadata.type in ("int", "port"):
        if not isinstance(value, int):
            return False, f"属性 '{metadata.name}' 必须是整数类型"
        if metadata.min is not None and value < metadata.min:
            return False, f"属性 '{metadata.name}' 不能小于 {metadata.min}"
        if metadata.max is not None and value > metadata.max:
            return False, f"属性 '{metadata.name}' 不能大于 {metadata.max}"
    
    elif metadata.type == "float":
        if not isinstance(value, (int, float)):
            return False, f"属性 '{metadata.name}' 必须是数字类型"
        if metadata.min is not None and value < metadata.min:
            return False, f"属性 '{metadata.name}' 不能小于 {metadata.min}"
        if metadata.max is not None and value > metadata.max:
            return False, f"属性 '{metadata.name}' 不能大于 {metadata.max}"
    
    elif metadata.type == "bool":
        if not isinstance(value, bool):
            return False, f"属性 '{metadata.name}' 必须是布尔类型"
    
    elif metadata.type == "enum":
        if metadata.enum_values and value not in metadata.enum_values:
            return False, f"属性 '{metadata.name}' 必须是以下值之一: {', '.join(metadata.enum_values)}"
    
    elif metadata.type == "ip":
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, str(value)):
            return False, f"属性 '{metadata.name}' 不是有效的 IP 地址"
    
    elif metadata.type == "url":
        import re
        url_pattern = r'^https?://'
        if not re.match(url_pattern, str(value)):
            return False, f"属性 '{metadata.name}' 不是有效的 URL"
    
    elif metadata.type == "email":
        import re
        email_pattern = r'^[^@]+@[^@]+\.[^@]+$'
        if not re.match(email_pattern, str(value)):
            return False, f"属性 '{metadata.name}' 不是有效的邮箱地址"
    
    return True, ""


def validate_entity_attributes(
    attributes: dict,
    metadata_list: List[AttributeMetadata],
) -> tuple[bool, List[str]]:
    """校验实体的所有属性。"""
    errors = []
    
    for metadata in metadata_list:
        value = attributes.get(metadata.key)
        valid, error = validate_attribute_value(metadata, value)
        if not valid:
            errors.append(error)
    
    return len(errors) == 0, errors


# ========== 预定义属性模板 ==========

# Service 属性模板
SERVICE_ATTRIBUTES = [
    AttributeMetadata(
        key="port", name="服务端口", type="port",
        required=True, default=8080,
        min=1, max=65535,
        description="服务监听端口",
        fill_rule="auto_discover", group="网络", order=1,
    ),
    AttributeMetadata(
        key="protocol", name="协议", type="enum",
        required=True, default="http",
        enum_values=["http", "https", "grpc", "tcp", "udp"],
        description="服务协议",
        fill_rule="auto_discover", group="网络", order=2,
    ),
    AttributeMetadata(
        key="version", name="版本", type="string",
        required=False,
        pattern=r'^\d+\.\d+\.\d+$',
        description="服务版本号",
        fill_rule="auto_discover", group="基本信息", order=3,
    ),
    AttributeMetadata(
        key="environment", name="环境", type="enum",
        required=True, default="production",
        enum_values=["development", "staging", "production"],
        description="部署环境",
        fill_rule="manual", group="基本信息", order=4,
    ),
    AttributeMetadata(
        key="team", name="负责团队", type="string",
        required=False,
        max_length=64,
        description="服务负责团队",
        fill_rule="manual", group="基本信息", order=5,
    ),
    AttributeMetadata(
        key="health_check_path", name="健康检查路径", type="string",
        required=False, default="/health",
        description="健康检查接口路径",
        fill_rule="manual", group="运维", order=6,
    ),
]

# Host 属性模板
HOST_ATTRIBUTES = [
    AttributeMetadata(
        key="ip", name="IP 地址", type="ip",
        required=True,
        description="主机 IP 地址",
        fill_rule="auto_discover", group="网络", order=1,
    ),
    AttributeMetadata(
        key="hostname", name="主机名", type="string",
        required=False,
        description="主机名",
        fill_rule="auto_discover", group="基本信息", order=2,
    ),
    AttributeMetadata(
        key="cpu_cores", name="CPU 核数", type="int",
        required=True,
        min=1, max=256,
        description="CPU 核心数",
        fill_rule="auto_discover", group="硬件", order=3,
    ),
    AttributeMetadata(
        key="memory_gb", name="内存 (GB)", type="int",
        required=True,
        min=1, max=2048,
        description="内存大小 (GB)",
        fill_rule="auto_discover", group="硬件", order=4,
    ),
    AttributeMetadata(
        key="disk_gb", name="磁盘 (GB)", type="int",
        required=False,
        min=1,
        description="磁盘大小 (GB)",
        fill_rule="auto_discover", group="硬件", order=5,
    ),
    AttributeMetadata(
        key="os", name="操作系统", type="string",
        required=False,
        description="操作系统类型",
        fill_rule="auto_discover", group="系统", order=6,
    ),
    AttributeMetadata(
        key="datacenter", name="数据中心", type="string",
        required=False,
        description="所在数据中心",
        fill_rule="manual", group="位置", order=7,
    ),
    AttributeMetadata(
        key="rack", name="机架", type="string",
        required=False,
        description="机架位置",
        fill_rule="manual", group="位置", order=8,
    ),
]

# MySQL 属性模板
MYSQL_ATTRIBUTES = [
    AttributeMetadata(
        key="host", name="主机", type="ip",
        required=True,
        description="数据库主机 IP",
        fill_rule="auto_discover", group="连接", order=1,
    ),
    AttributeMetadata(
        key="port", name="端口", type="port",
        required=True, default=3306,
        min=1, max=65535,
        description="数据库端口",
        fill_rule="auto_discover", group="连接", order=2,
    ),
    AttributeMetadata(
        key="version", name="版本", type="string",
        required=False,
        description="MySQL 版本",
        fill_rule="auto_discover", group="基本信息", order=3,
    ),
    AttributeMetadata(
        key="max_connections", name="最大连接数", type="int",
        required=False, default=151,
        min=1,
        description="最大连接数配置",
        fill_rule="auto_discover", group="配置", order=4,
    ),
    AttributeMetadata(
        key="role", name="角色", type="enum",
        required=True, default="master",
        enum_values=["master", "slave", "backup"],
        description="数据库角色",
        fill_rule="manual", group="拓扑", order=5,
    ),
]

# Redis 属性模板
REDIS_ATTRIBUTES = [
    AttributeMetadata(
        key="host", name="主机", type="ip",
        required=True,
        description="Redis 主机 IP",
        fill_rule="auto_discover", group="连接", order=1,
    ),
    AttributeMetadata(
        key="port", name="端口", type="port",
        required=True, default=6379,
        min=1, max=65535,
        description="Redis 端口",
        fill_rule="auto_discover", group="连接", order=2,
    ),
    AttributeMetadata(
        key="maxmemory", name="最大内存", type="string",
        required=False, default="1gb",
        description="最大内存配置",
        fill_rule="auto_discover", group="配置", order=3,
    ),
    AttributeMetadata(
        key="mode", name="模式", type="enum",
        required=True, default="standalone",
        enum_values=["standalone", "sentinel", "cluster"],
        description="Redis 部署模式",
        fill_rule="manual", group="拓扑", order=4,
    ),
]

# 属性模板映射
ATTRIBUTE_TEMPLATES = {
    "Service": SERVICE_ATTRIBUTES,
    "Host": HOST_ATTRIBUTES,
    "MySQL": MYSQL_ATTRIBUTES,
    "Redis": REDIS_ATTRIBUTES,
}


def get_attribute_template(type_name: str) -> List[AttributeMetadata]:
    """获取指定实体类型的属性模板。"""
    return ATTRIBUTE_TEMPLATES.get(type_name, [])


def get_attribute_schema(type_name: str) -> dict:
    """获取指定实体类型的属性 Schema（用于前端表单生成）。"""
    template = get_attribute_template(type_name)
    if not template:
        return {"type_name": type_name, "attributes": [], "groups": []}
    
    # 按分组组织
    groups = {}
    for attr in template:
        group = attr.group or "其他"
        if group not in groups:
            groups[group] = []
        groups[group].append(attr.model_dump())
    
    return {
        "type_name": type_name,
        "attributes": [attr.model_dump() for attr in template],
        "groups": [
            {"name": name, "attributes": attrs}
            for name, attrs in groups.items()
        ],
        "total": len(template),
    }
