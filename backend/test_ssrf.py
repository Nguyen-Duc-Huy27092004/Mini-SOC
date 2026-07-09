import sys
import os

# Add backend dir to python path
sys.path.insert(0, os.path.abspath('.'))

from app.core.security.validators import validate_safe_url, SSRFVulnerabilityError

def run_tests():
    test_urls = [
        ("http://192.168.1.1", False),
        ("https://169.254.169.254/latest/meta-data/", False),
        ("http://10.0.0.1", False),
        ("http://127.0.0.1:8000", False),
        ("http://localhost:5432", False),
        ("https://google.com", True),
        ("http://api.github.com/webhook", True),
    ]
    
    passed = 0
    for url, expected_safe in test_urls:
        try:
            validate_safe_url(url)
            is_safe = True
        except SSRFVulnerabilityError as e:
            is_safe = False
            print(f"Blocked (as expected): {url} -> {e}")
            
        if is_safe == expected_safe:
            passed += 1
            if is_safe:
                print(f"Allowed (as expected): {url}")
        else:
            print(f"FAILED for {url}. Expected safe={expected_safe}, got safe={is_safe}")
            
    print(f"\n{passed}/{len(test_urls)} tests passed.")

if __name__ == '__main__':
    run_tests()
