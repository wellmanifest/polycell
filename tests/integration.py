"""Live checks against APP_URL, including persistence and MCP over stdio."""
import json, os, subprocess, sys, urllib.request, urllib.error
base=os.environ.get('APP_URL','http://127.0.0.1:8080')
def request(path, data=None):
 req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'content-type':'application/json'})
 try:
  response=urllib.request.urlopen(req,timeout=20)
 except urllib.error.HTTPError as e:
  response=e
 with response: return response.status,json.load(response)
with open('contracts/processes/checkout.process.yaml') as f:
 import yaml
 data=yaml.safe_load(f)['examples'][0]['input']
trs=os.environ.get('TEST_TRANSPORTS','http,grpc,stdio').split(',')
for tr in trs:
 status,r=request('/api/process/checkout?transport='+tr,data)
 assert status==200 and r['ok'] and r['output']['quote']['total']==221.4,(status,r)
 trace=r['receipt']['trace_id']
 assert len(r['receipt']['steps'])==3
 rows=request('/api/table/wm_invocations?limit=100')[1]
 assert len([x for x in rows if x['trace_id']==trace])==3
 print('Checkout + persisted 3 steps:',tr,'PASS')
invalid={**data,'customer':{**data['customer'],'email':'invalid'}}
status,r=request('/api/process/checkout',invalid)
assert status==422 and len(r['receipt']['steps'])==1 and 'guard failed' in r['error'],r
print('POA guard stops checkout: PASS')
for data in ({'name':None,'email':'x@y.pl','country':'PL'}, {'name':'Jan','email':'x@y.pl','country':'PL','unknown':True}):
 status,r=request('/api/cells/customer.validate',data)
 assert status==422 and 'input contract:' in r['error'],r
print('Live invalid-input checks: PASS')
status,logs=request('/api/logs?tail=5')
assert status==200 and len(logs)>1,logs
print('Collected log sources:',list(logs))
messages=[{'jsonrpc':'2.0','id':1,'method':'initialize'},{'jsonrpc':'2.0','id':2,'method':'tools/list'}, {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'pricing_quote','arguments':{'items':[{'sku':'A','qty':1,'unit_price':10}],'currency':'PLN'}}}]
p=subprocess.run([sys.executable,'-m','gateway.mcp'],input=''.join(json.dumps(m)+'\n' for m in messages),text=True,capture_output=True,env={**os.environ,'WM_GATEWAY_URL':base},timeout=30,check=True)
res=[json.loads(line) for line in p.stdout.splitlines()]
assert len(res)==3 and len(res[1]['result']['tools'])==5,res
assert res[2]['result']['isError'] is False,res
assert json.loads(res[2]['result']['content'][0]['text'])['output']['total']==12.3,res
print('MCP initialize/list/call: PASS')
