#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查Redis中的会话数据"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.cache.redis_cache import redis_client
from app.services.ai_service import (
    get_user_sessions_key, 
    get_session_history_key,
    get_user_sessions
)

def check_redis_sessions():
    print("=" * 60)
    print("检查Redis中的会话数据")
    print("=" * 60)
    
    # 检查anonymous用户的会话
    user_id = "anonymous"
    
    # 1. 获取用户会话列表的key
    sessions_key = get_user_sessions_key(user_id)
    print(f"\n1. 用户会话列表key: {sessions_key}")
    
    # 2. 获取原始数据
    raw_sessions = redis_client.get(sessions_key)
    print(f"\n2. Redis中的原始数据:")
    if raw_sessions:
        print(json.dumps(raw_sessions, ensure_ascii=False, indent=2))
    else:
        print("   无数据")
    
    # 3. 使用API获取会话列表
    print(f"\n3. 使用API获取的会话列表:")
    sessions = get_user_sessions(user_id)
    print(f"   会话数量: {len(sessions)}")
    for i, s in enumerate(sessions):
        print(f"   [{i+1}] session_id: {s.get('session_id', 'N/A')}")
        print(f"       title: {s.get('title', 'N/A')}")
        
        # 4. 检查每个会话的消息数据
        session_id = s.get('session_id')
        if session_id:
            session_key = get_session_history_key(user_id, session_id)
            session_data = redis_client.get(session_key)
            print(f"       消息数量: {len(session_data) if session_data else 0}")
    
    print("\n" + "=" * 60)
    print("数据检查完成")
    print("=" * 60)

if __name__ == "__main__":
    check_redis_sessions()