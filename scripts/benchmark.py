#!/usr/bin/env python3
"""
성능 벤치마크 스크립트
사용법: python scripts/benchmark.py
"""

import json
import gzip
import uuid
import time
import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import argparse


def create_bulk_events(batch_size: int, total_events: int) -> List[Dict[str, Any]]:
    """벤치마크용 대량 이벤트 생성"""
    events = []
    current_time = int(time.time())
    
    for i in range(total_events):
        event = {
            "event_id": str(uuid.uuid4()),
            "event_time_epoch": current_time - i,
            "user_id": f"user_{i % 100}",
            "team": f"team_{i % 10}",
            "service": "chat_completion",
            "provider": "openai",
            "model": "gpt-4",
            "total_tokens": 100 + (i % 1000),
            "latency_ms": 500 + (i % 2000),
            "status_code": 200,
            "error_type": None,
            "prompt": f"Benchmark prompt {i}",
            "extra": {"benchmark": True, "iteration": i}
        }
        events.append(event)
    
    return events


def compress_data(data: Dict[str, Any]) -> bytes:
    """JSON 데이터를 gzip으로 압축"""
    json_str = json.dumps(data, separators=(',', ':'))
    return gzip.compress(json_str.encode('utf-8'))


def send_batch(base_url: str, events: List[Dict[str, Any]], use_gzip: bool = True) -> Tuple[float, int]:
    """단일 배치 전송 및 응답 시간 측정"""
    payload = {"items": events}
    
    start_time = time.time()
    
    try:
        if use_gzip:
            compressed_data = compress_data(payload)
            headers = {
                "Content-Type": "application/json",
                "Content-Encoding": "gzip"
            }
            response = requests.post(
                f"{base_url}/api/v1/ingest/requests:bulk",
                data=compressed_data,
                headers=headers,
                timeout=60
            )
        else:
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                f"{base_url}/api/v1/ingest/requests:bulk",
                json=payload,
                headers=headers,
                timeout=60
            )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        if response.status_code == 200:
            result = response.json()
            accepted = result.get('accepted', 0)
            return response_time, accepted
        else:
            print(f"❌ Request failed: {response.status_code} - {response.text}")
            return response_time, 0
            
    except Exception as e:
        end_time = time.time()
        print(f"❌ Request error: {e}")
        return end_time - start_time, 0


def benchmark_sequential(base_url: str, total_events: int, batch_size: int, use_gzip: bool = True):
    """순차적 벤치마크"""
    print(f"🔄 Sequential benchmark: {total_events} events, batch_size={batch_size}, gzip={use_gzip}")
    
    events = create_bulk_events(batch_size, total_events)
    batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]
    
    response_times = []
    total_accepted = 0
    
    for i, batch in enumerate(batches):
        print(f"  Batch {i+1}/{len(batches)} ({len(batch)} events)...")
        
        response_time, accepted = send_batch(base_url, batch, use_gzip)
        response_times.append(response_time)
        total_accepted += accepted
        
        # 간격을 두어 서버 부하 방지
        time.sleep(0.1)
    
    return response_times, total_accepted


def benchmark_concurrent(base_url: str, total_events: int, batch_size: int, max_workers: int, use_gzip: bool = True):
    """동시성 벤치마크"""
    print(f"⚡ Concurrent benchmark: {total_events} events, batch_size={batch_size}, workers={max_workers}, gzip={use_gzip}")
    
    events = create_bulk_events(batch_size, total_events)
    batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]
    
    response_times = []
    total_accepted = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 배치를 동시에 제출
        future_to_batch = {
            executor.submit(send_batch, base_url, batch, use_gzip): i 
            for i, batch in enumerate(batches)
        }
        
        # 결과 수집
        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                response_time, accepted = future.result()
                response_times.append(response_time)
                total_accepted += accepted
                print(f"  Batch {batch_idx+1} completed: {response_time:.2f}s, {accepted} accepted")
            except Exception as e:
                print(f"  Batch {batch_idx+1} failed: {e}")
    
    return response_times, total_accepted


def print_statistics(response_times: List[float], total_accepted: int, total_events: int):
    """통계 출력"""
    if not response_times:
        print("❌ No successful requests")
        return
    
    print("\n📊 Performance Statistics:")
    print("-" * 40)
    print(f"Total Events: {total_events}")
    print(f"Accepted Events: {total_accepted}")
    print(f"Success Rate: {(total_accepted/total_events)*100:.1f}%")
    print(f"Total Requests: {len(response_times)}")
    print(f"Total Time: {sum(response_times):.2f}s")
    print(f"Average Response Time: {statistics.mean(response_times):.3f}s")
    print(f"Median Response Time: {statistics.median(response_times):.3f}s")
    print(f"Min Response Time: {min(response_times):.3f}s")
    print(f"Max Response Time: {max(response_times):.3f}s")
    print(f"Std Dev Response Time: {statistics.stdev(response_times):.3f}s")
    print(f"Events per Second: {total_accepted/sum(response_times):.1f}")
    print(f"Requests per Second: {len(response_times)/sum(response_times):.1f}")


def main():
    """메인 벤치마크 함수"""
    parser = argparse.ArgumentParser(description="API Performance Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--events", type=int, default=1000, help="Total events to send")
    parser.add_argument("--batch-size", type=int, default=100, help="Events per batch")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--no-gzip", action="store_true", help="Disable gzip compression")
    parser.add_argument("--concurrent", action="store_true", help="Run concurrent benchmark")
    
    args = parser.parse_args()
    
    print("🚀 Starting API Performance Benchmark")
    print("=" * 60)
    print(f"Target URL: {args.url}")
    print(f"Total Events: {args.events}")
    print(f"Batch Size: {args.batch_size}")
    print(f"Gzip Compression: {not args.no_gzip}")
    print(f"Concurrent Workers: {args.workers}")
    print("=" * 60)
    
    use_gzip = not args.no_gzip
    
    # 헬스체크
    try:
        response = requests.get(f"{args.url}/healthz", timeout=10)
        if response.status_code != 200:
            print("❌ API is not healthy")
            return
        print("✅ API is healthy")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return
    
    # 벤치마크 실행
    if args.concurrent:
        response_times, total_accepted = benchmark_concurrent(
            args.url, args.events, args.batch_size, args.workers, use_gzip
        )
    else:
        response_times, total_accepted = benchmark_sequential(
            args.url, args.events, args.batch_size, use_gzip
        )
    
    # 결과 출력
    print_statistics(response_times, total_accepted, args.events)
    
    # 압축률 테스트 (gzip 사용시)
    if use_gzip:
        print("\n📦 Compression Test:")
        print("-" * 40)
        test_events = create_bulk_events(args.batch_size, args.batch_size)
        payload = {"items": test_events}
        
        json_size = len(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        compressed_size = len(compress_data(payload))
        compression_ratio = (1 - compressed_size / json_size) * 100
        
        print(f"JSON Size: {json_size:,} bytes")
        print(f"Compressed Size: {compressed_size:,} bytes")
        print(f"Compression Ratio: {compression_ratio:.1f}%")


if __name__ == "__main__":
    main()
