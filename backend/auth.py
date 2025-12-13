"""
N8 Control Center - 认证和权限中间件
"""
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from models_merged import User, APIKey, AuditLog, DevicePermission, UserRole
from grpc_server_secured import DatabaseManager

# ============================================
# 数据库依赖
# ============================================
def get_db():
    db = DatabaseManager.get_session()
    try:
        yield db
    finally:
        db.close()

# ============================================
# API Key认证
# ============================================
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """
    从HTTP Authorization头中提取API Key并验证
    
    使用方式：
    Authorization: Bearer sk-xxx
    """
    api_key = credentials.credentials
    
    # 查询API Key
    key_obj = db.query(APIKey).filter_by(key=api_key, is_active=True).first()
    
    if not key_obj:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    # 检查是否过期
    if key_obj.is_expired():
        raise HTTPException(status_code=401, detail="API Key expired")
    
    # 查询用户
    user = db.query(User).filter_by(id=key_obj.user_id, is_active=True).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    # 更新最后使用时间
    key_obj.last_used_at = datetime.utcnow()
    db.commit()
    
    return user

# ============================================
# 权限检查
# ============================================
def require_role(*allowed_roles: UserRole):
    """
    角色权限装饰器
    """
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}"
            )
        return user
    return role_checker

def check_device_permission(
    device_id: str,
    required_permission: DevicePermission,
    user: User,
    db: Session
) -> bool:
    """
    检查用户是否有设备的特定权限
    """
    # ADMIN拥有所有权限
    if user.role == UserRole.ADMIN:
        return True
    
    # 查询用户对该设备的权限
    from models_merged import UserDevicePermission
    
    permission = db.query(UserDevicePermission).filter_by(
        user_id=user.id,
        device_id=device_id,
        permission=required_permission
    ).first()
    
    return permission is not None

def require_device_permission(device_id: str, permission: DevicePermission):
    """
    设备权限检查装饰器
    """
    def permission_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        if not check_device_permission(device_id, permission, user, db):
            raise HTTPException(
                status_code=403,
                detail=f"No {permission.value} permission for device {device_id}"
            )
        return user
    return permission_checker

# ============================================
# 审计日志记录
# ============================================
async def log_audit(
    request: Request,
    user: User,
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    status_code: int,
    details: Optional[dict],
    db: Session
):
    """
    记录审计日志
    """
    log = AuditLog(
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status_code=status_code
    )
    db.add(log)
    db.commit()
