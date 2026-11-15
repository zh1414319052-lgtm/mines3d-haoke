// All content is rendered as text, including administrator-provided schema descriptions.
const list=document.getElementById('endpoints'), status=document.getElementById('status');
let definitions=[];
function node(tag,text){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;}
function render(){
  const search=document.getElementById('filter').value.toLowerCase();list.replaceChildren();
  const visible=definitions.filter(d=>(d.method+' '+d.path+' '+d.operation.summary+' '+d.operation.tags?.join(' ')).toLowerCase().includes(search));
  status.textContent=`${visible.length} 个接口 · 需要的权限以服务端校验为准`;
  for(const d of visible){
    const detail=node('details'), summary=node('summary');
    summary.append(node('strong',d.method),node('code',d.path),node('small',d.operation.tags?.join(' / ')||''));detail.append(summary);
    detail.append(node('p',d.operation.description||d.operation.summary||''));
    detail.append(node('p',d.operation.security?'使用玩家会话或管理凭证；管理路径需要对应管理权限。':'公开接口 / 开发入口（后者仅本机开发环境开放）。'));
    if(d.operation.parameters?.length){detail.append(node('h3','路径、查询与请求头参数'),node('pre',JSON.stringify(d.operation.parameters,null,2)));}
    if(d.operation.requestBody){const body=d.operation.requestBody.content['application/json']?.schema;detail.append(node('h3','JSON 请求体'),node('pre',JSON.stringify(d.schemas[body?.$ref?.split('/').at(-1)]||body,null,2)));}
    const examples=`curl ${d.method==='GET'?'':'-X '+d.method+' '}"${location.origin}${d.path}"`+(d.operation.security?' -H "Authorization: Bearer <凭证>"':'')+(d.method!=='GET'&&d.path.startsWith('/api/admin/')?' -H "Idempotency-Key: <本次操作唯一ID>"':'')+(d.operation.requestBody?' -H "Content-Type: application/json" --data \'<按上方字段填写JSON>\'':'');
    detail.append(node('h3','调用结构'),node('pre',examples));list.append(detail);
  }
}
fetch('/api/openapi.json').then(r=>{if(!r.ok)throw Error('接口文档读取失败');return r.json()}).then(schema=>{
  definitions=Object.entries(schema.paths).flatMap(([path,methods])=>Object.entries(methods).filter(([method])=>['get','post','put','patch','delete'].includes(method)).map(([method,operation])=>({path,method:method.toUpperCase(),operation,schemas:schema.components.schemas})));
  render();document.getElementById('filter').addEventListener('input',render);
}).catch(e=>{status.textContent=e.message+'，请确认本地服务已启动后刷新。';});
