#!/usr/bin/env python3
"""
Health check script for all MCP OCR services
"""
import requests
import sys
import time
from typing import Dict, List

# All MCP OCR services with their ports
SERVICES = {
    'tesseract': 8089,
    'easyocr': 8092,
    'paddle': 8090,
    'surya': 8091,
    'docling': 8093,
    'doctr': 8094,
    'deepseek': 8095,
    'qwen': 8096,
    'marker': 8097,
    'nanonets': 8098,
    'chandra': 8099
}

def check_service_health(service_name: str, port: int, timeout: int = 5) -> Dict:
    """Check health of a single service"""
    url = f"http://localhost:{port}/health"
    
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            return {
                'status': 'healthy',
                'service': service_name,
                'port': port,
                'response_time': response.elapsed.total_seconds(),
                'data': data
            }
        else:
            return {
                'status': 'unhealthy',
                'service': service_name,
                'port': port,
                'error': f"HTTP {response.status_code}",
                'response_time': response.elapsed.total_seconds()
            }
    except requests.exceptions.ConnectionError:
        return {
            'status': 'unreachable',
            'service': service_name,
            'port': port,
            'error': 'Connection refused'
        }
    except requests.exceptions.Timeout:
        return {
            'status': 'timeout',
            'service': service_name,
            'port': port,
            'error': f'Timeout after {timeout}s'
        }
    except Exception as e:
        return {
            'status': 'error',
            'service': service_name,
            'port': port,
            'error': str(e)
        }

def check_all_services(services: Dict[str, int], timeout: int = 5) -> List[Dict]:
    """Check health of all services"""
    results = []
    
    print("🔍 Checking MCP OCR Service Health")
    print("=" * 50)
    
    for service_name, port in services.items():
        print(f"Checking {service_name:12s} on port {port}...", end=" ")
        result = check_service_health(service_name, port, timeout)
        
        if result['status'] == 'healthy':
            print(f"✅ HEALTHY ({result['response_time']:.3f}s)")
        elif result['status'] == 'unhealthy':
            print(f"⚠️  UNHEALTHY - {result['error']}")
        elif result['status'] == 'unreachable':
            print(f"❌ UNREACHABLE - {result['error']}")
        elif result['status'] == 'timeout':
            print(f"⏰ TIMEOUT - {result['error']}")
        else:
            print(f"💥 ERROR - {result['error']}")
        
        results.append(result)
    
    return results

def print_summary(results: List[Dict]):
    """Print summary of health check results"""
    print("\n" + "=" * 50)
    print("HEALTH CHECK SUMMARY")
    print("=" * 50)
    
    healthy = [r for r in results if r['status'] == 'healthy']
    unhealthy = [r for r in results if r['status'] != 'healthy']
    
    print(f"Total services: {len(results)}")
    print(f"Healthy: {len(healthy)}")
    print(f"Unhealthy: {len(unhealthy)}")
    
    if healthy:
        print(f"\n✅ Healthy services ({len(healthy)}):")
        for result in healthy:
            rt = result.get('response_time', 0)
            print(f"   {result['service']:12s} - port {result['port']} ({rt:.3f}s)")
    
    if unhealthy:
        print(f"\n❌ Unhealthy services ({len(unhealthy)}):")
        for result in unhealthy:
            error = result.get('error', 'Unknown error')
            print(f"   {result['service']:12s} - port {result['port']} - {error}")
    
    print(f"\nOverall status: {'✅ ALL HEALTHY' if len(unhealthy) == 0 else '❌ SOME UNHEALTHY'}")

def wait_for_services(services: Dict[str, int], max_wait: int = 120, check_interval: int = 5):
    """Wait for services to become healthy"""
    print(f"⏳ Waiting up to {max_wait}s for services to become healthy...")
    print(f"   Checking every {check_interval}s")
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        results = check_all_services(services, timeout=2)
        healthy = [r for r in results if r['status'] == 'healthy']
        
        if len(healthy) == len(services):
            print(f"\n🎉 All services are healthy after {time.time() - start_time:.1f}s!")
            return True
        
        print(f"   {len(healthy)}/{len(services)} services healthy...")
        time.sleep(check_interval)
    
    print(f"\n⏰ Timeout: Not all services became healthy within {max_wait}s")
    return False

def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--wait":
            max_wait = int(sys.argv[2]) if len(sys.argv) > 2 else 120
            if wait_for_services(SERVICES, max_wait=max_wait):
                sys.exit(0)
            else:
                sys.exit(1)
        elif sys.argv[1] == "--timeout":
            timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            results = check_all_services(SERVICES, timeout=timeout)
        else:
            print("Usage:")
            print("  python health_check.py                  # Quick health check")
            print("  python health_check.py --wait [seconds] # Wait for services")
            print("  python health_check.py --timeout [sec]  # Custom timeout")
            sys.exit(1)
    else:
        results = check_all_services(SERVICES)
    
    print_summary(results)
    
    # Exit with error code if any service is unhealthy
    unhealthy = [r for r in results if r['status'] != 'healthy']
    sys.exit(1 if unhealthy else 0)

if __name__ == "__main__":
    main()