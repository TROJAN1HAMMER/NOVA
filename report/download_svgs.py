import base64
import urllib.request

for i in range(1, 4):
    with open(f'figure{i}.mmd', 'r') as f:
        code = f.read()
    
    # base64 encode using base64 string
    # mermaid config can be appended but it's optional.
    state = '{"code":"' + code.replace('\n', '\\n').replace('"', '\\"') + '","mermaid":"{\\"theme\\":\\"default\\"}"}'
    b64 = base64.urlsafe_b64encode(state.encode('utf-8')).decode('utf-8')
    url = f"https://mermaid.ink/svg/pako:{b64}" # mermaid ink expects pako compressed or raw b64?
    # actually raw base64 is supported at https://mermaid.ink/svg/{b64_of_code}
    b64_raw = base64.urlsafe_b64encode(code.encode('utf-8')).decode('utf-8')
    url = f"https://mermaid.ink/svg/{b64_raw}"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response, open(f'figure{i}.svg', 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        print(f"Downloaded figure{i}.svg")
    except Exception as e:
        print(f"Failed for figure{i}: {e}")
