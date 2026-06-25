import urllib.request
import json
import sys

def main():
    if len(sys.argv) < 4:
        print("Usage: python test_zabbix.py <ZABBIX_API_URL> <USER> <PASSWORD>")
        print("Example: python test_zabbix.py http://127.0.0.1/zabbix/api_jsonrpc.php Admin zabbix")
        return

    url, user, password = sys.argv[1], sys.argv[2], sys.argv[3]
    
    def rpc_call(method, params, auth=None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
            "auth": auth
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json-rpc"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    print(f"[*] Authenticating to {url}...")
    auth_res = rpc_call("user.login", {"username": user, "password": password})
    
    if "error" in auth_res:
        print("[-] Auth failed:", auth_res["error"])
        return
        
    token = auth_res.get("result")
    if not token:
        print("[-] No token received")
        return
        
    print("[+] Auth success!")
    
    print("[*] Fetching hosts...")
    hosts_res = rpc_call("host.get", {
        "output": ["hostid", "host", "name", "status", "available", "snmp_available", "ipmi_available", "jmx_available", "error"],
        "selectInterfaces": "extend"
    }, auth=token)
    
    if "error" in hosts_res:
        print("[-] host.get failed:", hosts_res["error"])
        return
        
    hosts = hosts_res.get("result", [])
    print(f"[+] Found {len(hosts)} hosts\n")
    
    for h in hosts:
        print(f"Host: {h.get('name')}")
        print(f"  status: {h.get('status')}")
        print(f"  available (old field): {h.get('available')}")
        
        interfaces = h.get("interfaces", [])
        print(f"  interfaces: {len(interfaces)} found")
        for i, iface in enumerate(interfaces):
            print(f"    [{i}] type={iface.get('type')}, ip={iface.get('ip')}, available={iface.get('available')}")
        print("-" * 40)

if __name__ == "__main__":
    main()
