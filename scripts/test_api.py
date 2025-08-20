#!/usr/bin/env python3
"""
API 테스트 스크립트
사용법: python scripts/test_api.py
"""

import json
import gzip
import uuid
import time
import requests
import os
from datetime import datetime, timezone
from typing import List, Dict, Any


def get_auth_token():
    """Get authentication token from environment or use default"""
    return os.getenv("ANALYTICS_TOKEN", "your-secret-analytics-token")


def create_test_events(count: int = 10) -> List[Dict[str, Any]]:
    """테스트용 사용량 이벤트 생성"""
    events = []
    current_time = int(time.time())
    
    for i in range(count):
        event = {
            "event_id": str(uuid.uuid4()),
            "event_time_epoch": current_time - i * 60,  # 1분씩 차이나게
            "user_id": f"user_{i % 5}",
            "team": f"team_{i % 3}",
            "service": "chat_completion",
            "provider": "openai",
            "model": "gpt-4",
            "total_tokens": 100 + i * 10,
            "latency_ms": 500 + i * 50,
            "status_code": 200,
            "error_type": None,
            "prompt": f"Test prompt {i}",
            "extra": {"test": True, "iteration": i}
        }
        events.append(event)
    
    return events


def create_test_archives(count: int = 5) -> List[Dict[str, Any]]:
    """테스트용 메시지 아카이브 생성"""
    archives = []
    current_time = int(time.time())
    
    for i in range(count):
        archive = {
            "event_id": str(uuid.uuid4()),
            "user_id": f"user_{i % 5}",
            "service": "chat_completion",
            "prompt_full": f"This is a test prompt for archive {i}",
            "response_full": f"This is a test response for archive {i}",
            "stored_at": current_time - i * 60
        }
        archives.append(archive)
    
    return archives


def compress_data(data: Dict[str, Any]) -> bytes:
    """JSON 데이터를 gzip으로 압축"""
    json_str = json.dumps(data, separators=(',', ':'))
    return gzip.compress(json_str.encode('utf-8'))


def get_auth_headers(token: str = None):
    """Get authentication headers"""
    if token is None:
        token = get_auth_token()
    return {"Authorization": f"Bearer {token}"}


def test_health_check(base_url: str = "http://localhost:8000"):
    """헬스체크 테스트"""
    print("🔍 Testing health check...")
    
    try:
        response = requests.get(f"{base_url}/healthz", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_api_info(base_url: str = "http://localhost:8000"):
    """API 정보 테스트"""
    print("\n📋 Testing API info...")
    
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ API info failed: {e}")
        return False


def test_ingest_requests(base_url: str = "http://localhost:8000", use_gzip: bool = True):
    """사용량 이벤트 수집 테스트"""
    print(f"\n📊 Testing usage events ingest (gzip: {use_gzip})...")
    
    # 테스트 데이터 생성
    events = create_test_events(5)
    payload = {"items": events}
    
    # 인증 헤더 추가
    headers = get_auth_headers()
    
    try:
        if use_gzip:
            # gzip 압축
            compressed_data = compress_data(payload)
            headers.update({
                "Content-Type": "application/json",
                "Content-Encoding": "gzip"
            })
            response = requests.post(
                f"{base_url}/api/v1/ingest/requests:bulk",
                data=compressed_data,
                headers=headers,
                timeout=30
            )
        else:
            # 일반 JSON
            headers.update({"Content-Type": "application/json"})
            response = requests.post(
                f"{base_url}/api/v1/ingest/requests:bulk",
                json=payload,
                headers=headers,
                timeout=30
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Usage events ingest failed: {e}")
        return False


def test_ingest_archives(base_url: str = "http://localhost:8000", use_gzip: bool = True):
    """메시지 아카이브 수집 테스트"""
    print(f"\n📁 Testing message archives ingest (gzip: {use_gzip})...")
    
    # 테스트 데이터 생성
    archives = create_test_archives(3)
    payload = {"items": archives}
    
    # 인증 헤더 추가
    headers = get_auth_headers()
    
    try:
        if use_gzip:
            # gzip 압축
            compressed_data = compress_data(payload)
            headers.update({
                "Content-Type": "application/json",
                "Content-Encoding": "gzip"
            })
            response = requests.post(
                f"{base_url}/api/v1/ingest/archives:bulk",
                data=compressed_data,
                headers=headers,
                timeout=30
            )
        else:
            # 일반 JSON
            headers.update({"Content-Type": "application/json"})
            response = requests.post(
                f"{base_url}/api/v1/ingest/archives:bulk",
                json=payload,
                headers=headers,
                timeout=30
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Message archives ingest failed: {e}")
        return False


def test_authentication(base_url: str = "http://localhost:8000"):
    """인증 테스트"""
    print("\n🔐 Testing authentication...")
    
    # 테스트 데이터
    events = create_test_events(1)
    payload = {"items": events}
    
    # 1. 인증 없이 요청 (실패해야 함)
    try:
        response = requests.post(
            f"{base_url}/api/v1/ingest/requests:bulk",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"No auth - Status: {response.status_code}")
        print(f"No auth - Response: {response.json()}")
    except Exception as e:
        print(f"No auth - Error: {e}")
    
    # 2. 잘못된 토큰으로 요청 (실패해야 함)
    try:
        headers = {"Authorization": "Bearer wrong-token", "Content-Type": "application/json"}
        response = requests.post(
            f"{base_url}/api/v1/ingest/requests:bulk",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Wrong token - Status: {response.status_code}")
        print(f"Wrong token - Response: {response.json()}")
    except Exception as e:
        print(f"Wrong token - Error: {e}")
    
    # 3. 올바른 토큰으로 요청 (성공해야 함)
    try:
        headers = get_auth_headers()
        headers.update({"Content-Type": "application/json"})
        response = requests.post(
            f"{base_url}/api/v1/ingest/requests:bulk",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Correct token - Status: {response.status_code}")
        print(f"Correct token - Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Correct token - Error: {e}")
        return False


def test_error_handling(base_url: str = "http://localhost:8000"):
    """에러 처리 테스트"""
    print("\n⚠️ Testing error handling...")
    
    # 인증 헤더
    headers = get_auth_headers()
    
    # 잘못된 JSON 테스트
    try:
        headers.update({"Content-Type": "application/json"})
        response = requests.post(
            f"{base_url}/api/v1/ingest/requests:bulk",
            data="invalid json",
            headers=headers,
            timeout=10
        )
        print(f"Invalid JSON - Status: {response.status_code}")
        print(f"Invalid JSON - Response: {response.json()}")
    except Exception as e:
        print(f"Invalid JSON test failed: {e}")
    
    # 너무 큰 배치 테스트
    try:
        large_events = create_test_events(2000)  # 기본 제한 초과
        payload = {"items": large_events}
        headers.update({"Content-Type": "application/json"})
        response = requests.post(
            f"{base_url}/api/v1/ingest/requests:bulk",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Large batch - Status: {response.status_code}")
        print(f"Large batch - Response: {response.json()}")
    except Exception as e:
        print(f"Large batch test failed: {e}")


def main():
    """메인 테스트 함수"""
    print("🚀 Starting API tests...")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # 기본 테스트
    tests = [
        ("Health Check", lambda: test_health_check(base_url)),
        ("API Info", lambda: test_api_info(base_url)),
        ("Authentication", lambda: test_authentication(base_url)),
        ("Usage Events (JSON)", lambda: test_ingest_requests(base_url, False)),
        ("Usage Events (gzip)", lambda: test_ingest_requests(base_url, True)),
        ("Message Archives (JSON)", lambda: test_ingest_archives(base_url, False)),
        ("Message Archives (gzip)", lambda: test_ingest_archives(base_url, True)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"✅ {test_name}: {'PASS' if success else 'FAIL'}")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # 에러 처리 테스트
    test_error_handling(base_url)
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed. Check the logs above.")


if __name__ == "__main__":
    main()
