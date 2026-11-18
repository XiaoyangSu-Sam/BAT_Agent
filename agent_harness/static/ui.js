"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="harness-token"]').content;
let config, sessionId, runId, after=0, generation=0, approvalId, events=[], busy=false;
const statuses={running:"执行中",awaiting_approval:"等待批准",completed:"已完成",failed:"执行失败",cancelled:"已停止",interrupted:"上次执行已中断",cancelling:"正在停止"};
const labels={run_started:"任务开始",step:"模型步骤",model_request:"请求模型",model_response:"收到模型回复",model_retry:"连接重试",tool_requested:"请求工具",tool_started:"工具开始执行",tool_result:"工具结果",approval_required:"等待批准",approval_resolved:"批准结果",assistant:"模型回复",error:"错误",completed:"任务完成",cancelled:"任务停止"};
async function api(path, body) {
  const response=await fetch("/api"+path,{method:body===undefined?"GET":"POST",
    headers:{"Content-Type":"application/json","X-Harness-Token":token},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) throw new Error(data.error ? data.error.code+": "+data.error.message : JSON.stringify(data.detail||data));
  return data;
}
function error(message){$("error").textContent=message;$("error").classList.toggle("hidden",!message);}
function addMessage(role,content){
  if(!content)return;
  const div=document.createElement("div");div.className="message "+role;
  const title=document.createElement("small");title.textContent=role==="user"?"YOU":"ASSISTANT";
  div.append(title,document.createTextNode(content));$("messages").append(div);
  $("welcome").classList.add("hidden");$("messages").scrollTop=$("messages").scrollHeight;
}
function setBusy(value){
  busy=value;$("send").disabled=value;$("model").disabled=value;
  $("cancel").classList.toggle("hidden",!value);
}
function showConfig(){
  const selected=$("model").value;
  $("model").replaceChildren();
  for(const m of config.models){const o=document.createElement("option");o.value=m.id;o.textContent=m.id+" · "+m.model;$("model").append(o);}
  if(config.models.some(m=>m.id===selected))$("model").value=selected;
  else $("model").value=config.default_model||"";
  $("workspace").textContent=config.workspace;
  $("policy").textContent={execution:"执行前批准 · 文件修改自动",all:"修改与执行前批准",trusted:"已启用自动执行"}[config.execution.approval_mode];
  showProvider();
}
function showProvider(){
  const model=config.models.find(m=>m.id===$("model").value);
  const demo=model?.provider==="fake";
  $("providerBadge").textContent=demo?"离线演示 · 非真实模型":model?"已配置 · "+model.tool_mode:"尚未配置";
  $("providerBadge").classList.toggle("demo",demo);
  $("demo").classList.toggle("hidden",!demo);
}
async function loadSkills(){
  const data=await api("/skills");$("skillCount").textContent=data.skills.length;$("skills").replaceChildren();
  for(const skill of data.skills){
    const div=document.createElement("div");div.className="skill";
    const name=document.createElement("strong");name.textContent=skill.id;
    div.append(name,document.createTextNode(skill.description));$("skills").append(div);
  }
  for(const warning of data.warnings){const p=document.createElement("p");p.textContent=JSON.stringify(warning);$("skills").append(p);}
}
async function listSessions(){
  const sessions=await api("/sessions");$("sessions").replaceChildren();
  for(const s of sessions){
    const button=document.createElement("button");button.className="session"+(s.id===sessionId?" active":"");
    button.textContent=s.title;button.title=s.title;button.onclick=()=>loadSession(s.id).catch(e=>error(e.message));$("sessions").append(button);
  }
  return sessions;
}
async function loadSession(id){
  generation++;sessionId=id;localStorage.setItem("harness.session",id);
  const s=await api("/sessions/"+id);
  $("messages").replaceChildren();$("welcome").classList.toggle("hidden",s.messages.length>0);
  for(const m of s.messages)if(m.role==="user"||m.role==="assistant")addMessage(m.role,m.content);
  $("events").replaceChildren();events=[];after=0;runId=null;
  $("approval").classList.add("hidden");setBusy(false);$("runStatus").textContent="就绪";
  await listSessions();
  if(s.runs.length){runId=s.runs[0].id;const mine=++generation;await poll(mine,true);}
}
async function newSession(title="新任务"){
  const s=await api("/sessions",{title});await loadSession(s.id);$("prompt").focus();
}
function renderEvent(event){
  events.push(event);after=Math.max(after,event.seq);
  const detail=document.createElement("details");detail.className="event"+(event.type==="error"?" error-event":"");
  const summary=document.createElement("summary");
  summary.textContent=(labels[event.type]||event.type)+(event.data.name?" · "+event.data.name:"");
  const stamp=document.createElement("time");stamp.textContent=new Date(event.time*1000).toLocaleTimeString();
  const pre=document.createElement("pre");pre.textContent=JSON.stringify(event.data,null,2);
  detail.append(summary,stamp,pre);$("events").append(detail);
  if(event.type==="error"||event.type==="tool_result")detail.open=true;
  if(event.type==="approval_required"){
    approvalId=event.data.approval_id;$("approvalText").textContent=event.data.name+"\n"+JSON.stringify(event.data.arguments,null,2);
    $("approval").classList.remove("hidden");
  }
  if(event.type==="approval_resolved")$("approval").classList.add("hidden");
}
async function poll(mine,initial=false){
  if(mine!==generation||!runId)return;
  try{
    const data=await api("/runs/"+runId+"?after="+after);
    if(mine!==generation)return;
    for(const event of data.events){
      renderEvent(event);
      if(!initial&&event.type==="assistant")addMessage("assistant",event.data.content);
    }
    const active=["running","awaiting_approval","cancelling"].includes(data.status);
    setBusy(active);$("runStatus").textContent=(statuses[data.status]||data.status)+(active?" · "+Math.floor(Date.now()/1000-data.created)+" 秒":"");
    if(!active)$("approval").classList.add("hidden");
    if(data.error)error(data.error.code+": "+data.error.message);
    if(active||data.events.length===200)setTimeout(()=>poll(mine,initial&&data.events.length===200),active?800:20);
  }catch(e){if(mine===generation){error("读取运行状态失败："+e.message);setTimeout(()=>poll(mine,initial),2500);}}
}
