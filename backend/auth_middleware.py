"""
N8枢纽控制中心 - 认证中间件模块
提供FastAPI认证依赖注入、Session Token验证、API Key验证和权限检查功能
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import Header, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.extras import RealDictCursor

from api_key_manager import APIKeyManager
from session_manager import SessionManager


# HTTP Bearer认证方案
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """认证中间件"""
    
    def __init__(self, database_url: str):
        """
        初始化认证中间件
        
        Args:
            database_url: PostgreSQL数据库连接URL
        """
        self.database_url = database_url
        self.api_key_manager = APIKeyManager(database_url)
        self.session_manager = SessionManager(database_url)
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)
    
    async def verify_session_token(
        self,
        authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Dict[str, Any]:
        """
        验证Session Token（FastAPI依赖注入）
        
        Args:
            authorization: HTTP Authorization头（Bearer Token）
            
        Returns:
            Session信息（包含api_key信息）
            
        Raises:
            HTTPException: 认证失败
        """
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        session_token = authorization.credentials
        
        # 验证Session Token
        session_info = self.session_manager.verify_session(session_token)
        
        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return session_info
    
    async def verify_api_key(
        self,
        x_api_key: Optional[str] = Header(None),
        x_api_secret: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """
        验证API Key和Secret（FastAPI依赖注入）
        
        Args:
            x_api_key: API Key（HTTP Header: X-API-Key）
            x_api_secret: API Secret（HTTP Header: X-API-Secret）
            
        Returns:
            API Key信息
            
        Raises:
            HTTPException: 认证失败
        """
        if not x_api_key or not x_api_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key or Secret",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        # 获取API Key信息
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, api_key, api_name, api_type, secret_hash, 
                           permissions, is_active, expires_at, created_at, last_used_at
                    FROM api_keys
                    WHERE api_key = %s AND is_active = TRUE
                    """,
                    (x_api_key,)
                )
                api_key_info = cur.fetchone()
        finally:
            conn.close()
        
        if not api_key_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        # 检查是否过期
        if api_key_info['expires_at'] and datetime.now() > api_key_info['expires_at']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key expired",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        # 验证Secret
        if not self.api_key_manager.verify_secret(x_api_secret, api_key_info['secret_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Secret",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        # 更新最后使用时间
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE api_keys SET last_used_at = %s WHERE id = %s",
                    (datetime.now(), api_key_info['id'])
                )
                conn.commit()
        finally:
            conn.close()
        
        return dict(api_key_info)
    
    async def verify_session_or_api_key(
        self,
        authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
        x_api_key: Optional[str] = Header(None),
        x_api_secret: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """
        验证Session Token或API Key（二选一）
        
        Args:
            authorization: HTTP Authorization头（Bearer Token）
            x_api_key: API Key（HTTP Header: X-API-Key）
            x_api_secret: API Secret（HTTP Header: X-API-Secret）
            
        Returns:
            认证信息（Session或API Key）
            
        Raises:
            HTTPException: 认证失败
        """
        # 优先尝试Session Token
        if authorization:
            try:
                return await self.verify_session_token(authorization)
            except HTTPException:
                pass
        
        # 尝试API Key
        if x_api_key and x_api_secret:
            try:
                return await self.verify_api_key(x_api_key, x_api_secret)
            except HTTPException:
                pass
        
        # 都失败
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Session Token or API Key)",
            headers={"WWW-Authenticate": "Bearer, ApiKey"},
        )
    
    def check_permissions(
        self,
        auth_info: Dict[str, Any],
        required_permissions: List[str]
    ) -> bool:
        """
        检查权限
        
        Args:
            auth_info: 认证信息（Session或API Key）
            required_permissions: 需要的权限列表
            
        Returns:
            是否有权限
        """
        # 获取用户权限
        if 'api_key' in auth_info:
            # Session信息（包含api_key字段）
            user_permissions = auth_info['api_key'].get('permissions', [])
        else:
            # API Key信息
            user_permissions = auth_info.get('permissions', [])
        
        # 检查是否有所有需要的权限
        return all(perm in user_permissions for perm in required_permissions)
    
    def require_permissions(self, required_permissions: List[str]):
        """
        创建权限检查依赖（FastAPI依赖注入）
        
        Args:
            required_permissions: 需要的权限列表
            
        Returns:
            FastAPI依赖函数
        """
        async def permission_checker(
            auth_info: Dict[str, Any] = Depends(self.verify_session_or_api_key)
        ) -> Dict[str, Any]:
            """权限检查器"""
            if not self.check_permissions(auth_info, required_permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(required_permissions)}"
                )
            return auth_info
        
        return permission_checker
    
    def require_api_type(self, allowed_types: List[str]):
        """
        创建API类型检查依赖（FastAPI依赖注入）
        
        Args:
            allowed_types: 允许的API类型列表（web/external/internal）
            
        Returns:
            FastAPI依赖函数
        """
        async def api_type_checker(
            auth_info: Dict[str, Any] = Depends(self.verify_session_or_api_key)
        ) -> Dict[str, Any]:
            """API类型检查器"""
            # 获取API类型
            if 'api_key' in auth_info:
                # Session信息
                api_type = auth_info['api_key'].get('api_type')
            else:
                # API Key信息
                api_type = auth_info.get('api_type')
            
            if api_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API type '{api_type}' not allowed for this endpoint"
                )
            
            return auth_info
        
        return api_type_checker


# 全局认证中间件实例（需要在应用启动时初始化）
_auth_middleware: Optional[AuthMiddleware] = None


def init_auth_middleware(database_url: str):
    """
    初始化全局认证中间件实例
    
    Args:
        database_url: PostgreSQL数据库连接URL
    """
    global _auth_middleware
    _auth_middleware = AuthMiddleware(database_url)


def get_auth_middleware() -> AuthMiddleware:
    """
    获取全局认证中间件实例
    
    Returns:
        认证中间件实例
        
    Raises:
        RuntimeError: 未初始化
    """
    if _auth_middleware is None:
        raise RuntimeError("AuthMiddleware not initialized. Call init_auth_middleware() first.")
    return _auth_middleware


# FastAPI依赖注入函数
async def require_session(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    要求Session Token认证（FastAPI依赖注入）
    
    Args:
        authorization: HTTP Authorization头
        
    Returns:
        Session信息
    """
    auth = get_auth_middleware()
    return await auth.verify_session_token(authorization)


async def require_api_key(
    x_api_key: Optional[str] = Header(None),
    x_api_secret: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    要求API Key认证（FastAPI依赖注入）
    
    Args:
        x_api_key: API Key
        x_api_secret: API Secret
        
    Returns:
        API Key信息
    """
    auth = get_auth_middleware()
    return await auth.verify_api_key(x_api_key, x_api_secret)


async def require_auth(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None),
    x_api_secret: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    要求认证（Session Token或API Key）（FastAPI依赖注入）
    
    Args:
        authorization: HTTP Authorization头
        x_api_key: API Key
        x_api_secret: API Secret
        
    Returns:
        认证信息
    """
    auth = get_auth_middleware()
    return await auth.verify_session_or_api_key(authorization, x_api_key, x_api_secret)
