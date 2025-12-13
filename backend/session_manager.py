"""
N8枢纽控制中心 - Session管理模块
提供Session的创建、验证、刷新、删除功能
支持72小时会话有效期
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor


class SessionManager:
    """Session管理器"""
    
    # 默认会话有效期：72小时
    DEFAULT_SESSION_HOURS = 72
    
    def __init__(self, database_url: str):
        """
        初始化Session管理器
        
        Args:
            database_url: PostgreSQL数据库连接URL
        """
        self.database_url = database_url
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)
    
    def generate_session_token(self) -> str:
        """
        生成随机Session Token
        
        Returns:
            128字符的随机Session Token
        """
        return secrets.token_urlsafe(96)[:128]
    
    def create_session(
        self,
        api_key_id: int,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_hours: int = DEFAULT_SESSION_HOURS
    ) -> Dict[str, Any]:
        """
        创建新的Session
        
        Args:
            api_key_id: API Key ID
            device_id: 设备ID（可选）
            ip_address: IP地址（可选）
            user_agent: User Agent（可选）
            session_hours: 会话有效期（小时）
            
        Returns:
            创建的Session信息（包含session_token和expires_at）
            
        Raises:
            ValueError: 参数验证失败
            psycopg2.Error: 数据库操作失败
        """
        # 生成Session Token
        session_token = self.generate_session_token()
        
        # 计算过期时间
        expires_at = datetime.now() + timedelta(hours=session_hours)
        
        # 插入数据库
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO sessions (session_token, api_key_id, device_id, ip_address, user_agent, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, session_token, api_key_id, device_id, expires_at, created_at
                    """,
                    (session_token, api_key_id, device_id, ip_address, user_agent, expires_at)
                )
                result = dict(cur.fetchone())
                conn.commit()
                return result
        finally:
            conn.close()
    
    def verify_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """
        验证Session Token
        
        Args:
            session_token: Session Token
            
        Returns:
            验证成功返回Session信息（包含API Key信息），失败返回None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 查询Session并关联API Key信息
                cur.execute(
                    """
                    SELECT 
                        s.id, s.session_token, s.api_key_id, s.device_id, 
                        s.ip_address, s.user_agent, s.expires_at, s.last_activity_at, s.created_at,
                        a.api_name, a.api_type, a.permissions, a.is_active
                    FROM sessions s
                    JOIN api_keys a ON s.api_key_id = a.id
                    WHERE s.session_token = %s
                    """,
                    (session_token,)
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                session_info = dict(row)
                
                # 检查API Key是否激活
                if not session_info['is_active']:
                    return None
                
                # 检查是否过期
                if session_info['expires_at'] < datetime.now():
                    return None
                
                # 更新最后活动时间
                cur.execute(
                    """
                    UPDATE sessions
                    SET last_activity_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (session_info['id'],)
                )
                conn.commit()
                
                return session_info
        finally:
            conn.close()
    
    def refresh_session(
        self,
        session_token: str,
        extend_hours: int = DEFAULT_SESSION_HOURS
    ) -> bool:
        """
        刷新Session，延长有效期
        
        Args:
            session_token: Session Token
            extend_hours: 延长的小时数
            
        Returns:
            是否刷新成功
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 计算新的过期时间
                new_expires_at = datetime.now() + timedelta(hours=extend_hours)
                
                cur.execute(
                    """
                    UPDATE sessions
                    SET expires_at = %s, last_activity_at = CURRENT_TIMESTAMP
                    WHERE session_token = %s AND expires_at > CURRENT_TIMESTAMP
                    """,
                    (new_expires_at, session_token)
                )
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()
    
    def delete_session(self, session_token: str) -> bool:
        """
        删除Session（登出）
        
        Args:
            session_token: Session Token
            
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions WHERE session_token = %s",
                    (session_token,)
                )
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()
    
    def delete_sessions_by_api_key(self, api_key_id: int) -> int:
        """
        删除指定API Key的所有Session
        
        Args:
            api_key_id: API Key ID
            
        Returns:
            删除的Session数量
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions WHERE api_key_id = %s",
                    (api_key_id,)
                )
                conn.commit()
                return cur.rowcount
        finally:
            conn.close()
    
    def list_sessions(
        self,
        api_key_id: Optional[int] = None,
        device_id: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出Sessions
        
        Args:
            api_key_id: 过滤API Key ID
            device_id: 过滤设备ID
            include_expired: 是否包含已过期的Session
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            Session列表
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 构建查询
                query = """
                    SELECT 
                        s.id, s.session_token, s.api_key_id, s.device_id, 
                        s.ip_address, s.user_agent, s.expires_at, s.last_activity_at, s.created_at,
                        a.api_name, a.api_type
                    FROM sessions s
                    JOIN api_keys a ON s.api_key_id = a.id
                    WHERE 1=1
                """
                params = []
                
                if api_key_id:
                    query += " AND s.api_key_id = %s"
                    params.append(api_key_id)
                
                if device_id:
                    query += " AND s.device_id = %s"
                    params.append(device_id)
                
                if not include_expired:
                    query += " AND s.expires_at > CURRENT_TIMESTAMP"
                
                query += " ORDER BY s.created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                results = [dict(row) for row in cur.fetchall()]
                return results
        finally:
            conn.close()
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理过期的Sessions
        
        Returns:
            清理的Session数量
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP"
                )
                conn.commit()
                return cur.rowcount
        finally:
            conn.close()
    
    def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取Session
        
        Args:
            session_id: Session ID
            
        Returns:
            Session信息，不存在返回None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT 
                        s.id, s.session_token, s.api_key_id, s.device_id, 
                        s.ip_address, s.user_agent, s.expires_at, s.last_activity_at, s.created_at,
                        a.api_name, a.api_type, a.permissions
                    FROM sessions s
                    JOIN api_keys a ON s.api_key_id = a.id
                    WHERE s.id = %s
                    """,
                    (session_id,)
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()
    
    def get_active_session_count(self, api_key_id: Optional[int] = None) -> int:
        """
        获取活跃Session数量
        
        Args:
            api_key_id: 过滤API Key ID（可选）
            
        Returns:
            活跃Session数量
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                if api_key_id:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM sessions 
                        WHERE api_key_id = %s AND expires_at > CURRENT_TIMESTAMP
                        """,
                        (api_key_id,)
                    )
                else:
                    cur.execute(
                        "SELECT COUNT(*) FROM sessions WHERE expires_at > CURRENT_TIMESTAMP"
                    )
                return cur.fetchone()[0]
        finally:
            conn.close()
