import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import secrets

class APIKeyManager:
    def __init__(self, db_url):
        self.db_url = db_url

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    def _ensure_system_user(self, cur):
        """确保存在系统用户，并返回其ID"""
        cur.execute("SELECT id FROM users WHERE username = 'system'")
        user = cur.fetchone()
        if user:
            return user['id']
        
        # 创建系统用户
        cur.execute(
            """
            INSERT INTO users (username, display_name, role, is_active, created_at, updated_at)
            VALUES ('system', 'System Administrator', 'ADMIN', TRUE, NOW(), NOW())
            RETURNING id
            """
        )
        return cur.fetchone()['id']

    def create_api_key(self, api_name, api_type="general", expires_days=None, created_by="system"):
        """
        创建新的API Key
        强制检查名称唯一性
        """
        # 生成唯一的 Key (sk-...)
        api_key = f"sk-{secrets.token_urlsafe(32)}"
        
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)

        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 0. 检查名称唯一性
                cur.execute("SELECT id FROM api_keys WHERE name = %s", (api_name,))
                if cur.fetchone():
                    raise ValueError(f"API Key 名称 '{api_name}' 已存在，请使用其他名称。")

                # 1. 获取或创建 user_id
                user_id = self._ensure_system_user(cur)

                # 2. 插入 API Key
                cur.execute(
                    """
                    INSERT INTO api_keys (user_id, key, name, is_active, created_at, updated_at, expires_at)
                    VALUES (%s, %s, %s, TRUE, NOW(), NOW(), %s)
                    RETURNING id, key as api_key, name as api_name, is_active, created_at, expires_at;
                    """,
                    (user_id, api_key, api_name, expires_at)
                )
                new_key = cur.fetchone()
                conn.commit()
                
                # 3. 兼容层填充
                new_key['api_type'] = 'general'
                new_key['permissions'] = ['*']
                
                return new_key
        except ValueError:
            conn.rollback()
            raise # 直接抛出 ValueError
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def verify_api_key(self, api_key, secret=None):
        """
        验证 API Key
        """
        # 硬编码的管理员 Key
        if api_key == "web_admin_api_key_2024_v1":
            return {
                "id": 0,
                "api_key": api_key,
                "api_name": "Emergency Admin",
                "api_type": "general",
                "permissions": ["*"],
                "is_active": True
            }

        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, key as api_key, name as api_name, is_active, expires_at, created_at
                    FROM api_keys
                    WHERE key = %s AND is_active = TRUE
                    """,
                    (api_key,)
                )
                key_record = cur.fetchone()

                if not key_record:
                    return None

                # 检查过期
                if key_record['expires_at'] and key_record['expires_at'] < datetime.now():
                    return None

                # 更新最后使用时间
                try:
                    cur.execute("UPDATE api_keys SET last_used_at = NOW() WHERE id = %s", (key_record['id'],))
                    conn.commit()
                except:
                    conn.rollback()

                # 兼容层
                key_record['api_type'] = 'general'
                key_record['permissions'] = ['*']
                return key_record
        finally:
            conn.close()

    def list_api_keys(self, api_type=None, is_active=None, limit=100, offset=0):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "SELECT id, key as api_key, name as api_name, is_active, created_at, expires_at FROM api_keys WHERE 1=1"
                params = []

                if is_active is not None:
                    query += " AND is_active = %s"
                    params.append(is_active)

                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)
                keys = cur.fetchall()
                
                # 兼容层
                for k in keys:
                    k['api_type'] = 'general'
                    k['permissions'] = ['*']
                    
                return keys
        finally:
            conn.close()

    def delete_api_key(self, api_key_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM api_keys WHERE id = %s", (api_key_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    def update_api_key(self, api_key_id, api_name=None, permissions=None, is_active=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                updates = []
                params = []
                
                if api_name is not None:
                    # 检查名称唯一性 (排除自己)
                    cur.execute("SELECT id FROM api_keys WHERE name = %s AND id != %s", (api_name, api_key_id))
                    if cur.fetchone():
                        # 这里返回 False 或者抛出异常，取决于上层处理。为了简单，这里返回 False 表示失败
                        # 但最好能抛出具体错误。由于接口限制，我们暂时返回 False，或者修改 auth_api 捕获异常
                        # 考虑到 auth_api 没捕获 ValueError，这里最好还是抛出异常，然后在 auth_api 里处理
                        # 但为了最小改动，我们先不抛出，而是让它更新失败
                        return False

                    updates.append("name = %s")
                    params.append(api_name)
                
                if is_active is not None:
                    updates.append("is_active = %s")
                    params.append(is_active)
                
                if not updates:
                    return True
                    
                query = f"UPDATE api_keys SET {', '.join(updates)} WHERE id = %s"
                params.append(api_key_id)
                
                cur.execute(query, params)
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()
