"use strict";
const $=id=>document.getElementById(id), token=document.querySelector('meta[name="harness-token"]').content;
let config,sessionId=null,runId=null,after=0,generation=0,approvalId,events=[],busy=false,selectedSkills=new Set();
const toolCards=new Map(),requestedTools=new Map(),changedPaths=new Set();
const statuses={running:"Running",awaiting_approval:"Awaiting approval",completed:"Completed",failed:"Failed",cancelled:"Stopped",interrupted:"Previous task interrupted",cancelling:"Stopping"};
const toolLabels={write_skill_file:"Write Skill file",list_files:"Explore files",read_file:"Read file",search_files:"Search code",write_file:"Write file",edit_file:"Edit code",run_command:"Run command",run_python_script:"Run Python",run_notebook:"Run notebook",list_skills:"List Skills",read_skill:"Read Skill",read_skill_resource:"Read Skill resource"};
async function api(path,body){
 const r=await fetch("/api"+path,{method:body===undefined?"GET":"POST",headers:{"Content-Type":"application/json","X-Harness-Token":token},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await r.json();if(!r.ok){const e=new Error(data.error?.message||JSON.stringify(data.detail||data));e.details=data.error;e.code=data.error?.code;e.status=r.status;throw e;}return data;
}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function error(message){$("error").textContent=message;$("error").classList.toggle("hidden",!message);}
function addMessage(role,content,reasoning){
 if(!content&&!reasoning)return;const box=el("article",undefined,"message "+role);
 box.append(el("div",role==="user"?"●  You":"✧  BAT Agent","message-label"));const body=el("div",undefined,"message-body");
 content=(content||"").split("\n\n[Workspace context]\n")[0].split("\n\n[工作区上下文]\n")[0];
 if(role==="user")body.textContent=content;
 else BATMarkdown.render(body,content);
 if(reasoning)box.append(reasoningElement(reasoning));
 box.append(body);$("messages").append(box);$("welcome").classList.add("hidden");scrollChat();
}
function scrollChat(){$("messages").scrollTop=$("messages").scrollHeight;}
function setBusy(value){
 busy=value;for(const id of ["send","model","newSession","sessions","settingsButton","newFile","openFolder","folderActivity","emptyOpenFolder","refreshSkills","diagnose"])$(id).disabled=value;
 $("cancel").classList.toggle("hidden",!value);$("thinking").classList.toggle("hidden",!value);if(window.editorReady)editor.readOnly(value);$("diagnose").disabled=value||!$("model").value;$("connectFromWorkspace").disabled=value;updateEditorStatus();
}
function showConfig(){
 const selected=$("model").value;$("model").replaceChildren();
 for(const m of config.models){const o=el("option",m.model+(m.id!=="default"?" · "+m.id:""));o.value=m.id;o.disabled=!m.ready;$("model").append(o);}
 const wanted=config.models.find(m=>m.id===selected&&m.ready)||config.models.find(m=>m.id===config.default_model&&m.ready)||config.models.find(m=>m.ready);
 if(!wanted){const option=el("option","No model connected");option.value="";$("model").prepend(option);}
 $("model").value=wanted?.id||"";$("modelNotice").classList.toggle("hidden",!!wanted);$("diagnose").disabled=busy||!wanted;
 const project=config.workspace.split(/[\\/]/).filter(Boolean).pop()||"workspace";
 $("projectName").textContent=project;$("workspaceLabel").textContent="⌄  "+project.toUpperCase();$("workspaceLabel").title=config.workspace;
 $("policy").textContent={execution:"Approve execution",all:"Approve changes and execution",trusted:"Auto-execute"}[config.execution.approval_mode];showProvider();
}
function showProvider(){const m=config.models.find(m=>m.id===$("model").value);const demo=m?.provider==="fake";$("providerBadge").textContent=demo?"Offline demo":m?.model||"Not connected";$("providerBadge").classList.toggle("demo",demo);}
async function loadSkills(){
 const data=await api("/skills");$("skillCount").textContent=data.skills.length;$("skills").replaceChildren();
 const ids=new Set(data.skills.map(s=>s.id));selectedSkills=new Set([...selectedSkills].filter(id=>ids.has(id)));updateContext();
 for(const s of data.skills){const card=el("article",undefined,"skill-card");card.append(el("h4",s.name),el("div","● Registered · "+s.id,"registered"),el("p",s.description));
 const actions=el("div");const view=el("button","View instructions","secondary");view.onclick=()=>showSkill(s.id);const use=el("button",selectedSkills.has(s.id)?"Added to chat":"Add to chat","secondary"+(selectedSkills.has(s.id)?" selected":""));
 use.onclick=()=>{selectedSkills.has(s.id)?selectedSkills.delete(s.id):selectedSkills.add(s.id);loadSkills().catch(e=>error(e.message));$("prompt").focus();};actions.append(view,use);card.append(actions);$("skills").append(card);}
 if(!data.skills.length)$("skills").append(el("p","No registered Skills yet. Add skills/<id>/SKILL.md and refresh, or ask the agent to create a Skill.","skills-intro"));
 for(const w of data.warnings)$("skills").append(el("p",(w.id||"")+": "+w.error,"inline-error"));
}
async function showSkill(id){try{const data=await api("/skills/"+encodeURIComponent(id));$("skillTitle").textContent=id;$("skillInstructions").textContent=data.instructions;$("skillDialog").showModal();}catch(e){error(e.message);}}
async function listSessions(){const sessions=await api("/sessions");$("sessions").replaceChildren();const option=el("option","New conversation");option.value="";$("sessions").append(option);
 for(const s of sessions){const o=el("option",s.title);o.value=s.id;$("sessions").append(o);}$("sessions").value=sessionId||"";return sessions;}
function resetRun(){events=[];after=0;runId=null;toolCards.clear();requestedTools.clear();changedPaths.clear();$("changeCount").textContent="0";$("events").replaceChildren();$("changes").replaceChildren();$("output").textContent="Process output will appear here.";$("approval").classList.add("hidden");$("runStatus").textContent="Ready";contextUsage={};renderContext();communication("idle","Ready · No request in progress");}
function clearMessages(){for(const node of [...$("messages").children])if(node.id!=="welcome")node.remove();$("welcome").classList.remove("hidden");}
async function loadSession(id){generation++;sessionId=id;localStorage.setItem("bat.session",id||"");clearMessages();resetRun();setBusy(false);error("");
 if(!id){await listSessions();return;}const s=await api("/sessions/"+id);for(const m of s.messages)if(["user","assistant"].includes(m.role))addMessage(m.role,m.content,m._reasoning);await listSessions();
 if(s.runs.length){runId=s.runs[0].id;await poll(++generation,true);}}
function renderEvent(event,initial=false){
 events.push(event);after=Math.max(after,event.seq);const d=event.data;
 const detail=el("details",undefined,"event");detail.append(el("summary",(d.name||event.type)+" · "+new Date(event.time*1000).toLocaleTimeString()),el("pre",JSON.stringify(d,null,2)));$("events").append(detail);
 if(event.type==="model_request")communication("sending","Sending request · "+d.model);
 if(event.type==="communication")communication(d.phase,d.message);
 if(event.type==="model_response")communication("received","Response received");
 if(event.type==="context_usage"){contextUsage={...d};renderContext();}
 if(event.type==="token_usage"){contextUsage={...contextUsage,...d};renderContext();}
 if(event.type==="reasoning"&&!initial){if(d.available){$("messages").append(reasoningElement(d.content));scrollChat();}else reasoningUnavailable();}
 if(event.type==="run_started"){communication("sending","Starting · "+d.model);}
 if(event.type==="error")communication("failed","Request failed · "+d.message);
 if(event.type==="completed")communication("idle","Ready · Last task completed");
 if(event.type==="cancelled")communication("idle","Stopped · No request in progress");
 if(event.type==="model_retry")communication("retrying","Retrying connection…");
 if(event.type==="tool_requested"){requestedTools.set(d.call_id,d);const card=el("details",undefined,"tool-card");card.append(el("summary",(toolLabels[d.name]||d.name)+(d.arguments.path?" · "+d.arguments.path:"")),el("pre",JSON.stringify(d.arguments,null,2)));toolCards.set(d.call_id,card);$("messages").append(card);$("thinkingText").textContent=toolLabels[d.name]||d.name;scrollChat();}
 if(event.type==="tool_result"){
 const card=toolCards.get(d.call_id);if(card){card.classList.add(d.ok?"done":"failed");card.querySelector("summary").textContent=(d.ok?"✓ ":"× ")+card.querySelector("summary").textContent;card.append(el("pre",JSON.stringify(d.ok?d.result:d.error,null,2)));}
 const result=d.result||{};if("stdout" in result||"stderr" in result){if($("output").textContent==="Process output will appear here.")$("output").textContent="";$("output").textContent+="> "+d.name+"\n"+(result.stdout||"")+(result.stderr?"\n[stderr]\n"+result.stderr:"")+"\nExit code: "+result.exit_code+(result.timed_out?" · Timed out":"")+"\n\n";$("output").scrollTop=$("output").scrollHeight;}
 if(result.scope==="skill"){loadSkills().catch(e=>error(e.message));}
 if(result.diff!==undefined){const displayPath=result.scope==="skill"?"skills/"+result.skill_id+"/"+result.path:result.path;changedPaths.add(displayPath);$("changeCount").textContent=changedPaths.size;const change=el("details",undefined,"change");change.open=true;const summary=el("summary",displayPath);summary.onclick=()=>{if(result.scope==="skill")showSkill(result.skill_id);else openFile(result.path).catch(e=>error(e.message));};change.append(summary,el("pre",result.diff||"No text changes"));$("changes").append(change);if(result.scope!=="skill")syncChangedFile(result.path).catch(e=>error(e.message));}
 if(d.ok&&d.name==="read_file"&&!activePath&&result.path)openFile(result.path).catch(()=>{});
 }
 if(event.type==="approval_required"){communication("approval","Waiting for your approval");approvalId=d.approval_id;$("approvalText").textContent=d.name+"\n"+JSON.stringify(d.arguments,null,2);$("approval").classList.remove("hidden");}
 if(event.type==="approval_resolved")$("approval").classList.add("hidden");
}
async function poll(mine,initial=false){
 if(mine!==generation||!runId)return;
 try{const data=await api("/runs/"+runId+"?after="+after);if(mine!==generation)return;
 for(const event of data.events){renderEvent(event,initial);if(!initial&&event.type==="assistant")addMessage("assistant",event.data.content);}
 const active=["running","awaiting_approval","cancelling"].includes(data.status);setBusy(active);$("runStatus").textContent=statuses[data.status]||data.status;
 if(!active){$("approval").classList.add("hidden");await refreshFiles();await syncOpenFiles();}
 if(data.error)error(data.error.message+(data.error.suggestions?" "+data.error.suggestions.join(" "):""));
 if(active||data.events.length===200)setTimeout(()=>poll(mine,initial),active?700:20);
 }catch(e){if(mine===generation){error("Unable to read task status: "+e.message);setTimeout(()=>poll(mine,initial),2200);}}
}

let contextUsage={};
function communication(phase,message){
 $("communicationStatus").textContent=message;$("communicationStatus").title=message;
 $("communicationDot").className=phase;$("thinkingText").textContent=message;
}
function reasoningElement(content){
 document.querySelector(".reasoning-unavailable")?.remove();
 const box=el("details",undefined,"reasoning");box.append(el("summary","Model reasoning"),el("p","Provided by the model service. This may be incomplete.","reasoning-caption"));
 const body=el("div",undefined,"message-body");BATMarkdown.render(body,content);box.append(body);box.classList.toggle("hidden",!$("showReasoning").checked);return box;
}
function reasoningUnavailable(){
 if(document.querySelector(".reasoning-unavailable"))return;
 const note=el("p","This response did not include separate model reasoning.","reasoning-unavailable");
 note.classList.toggle("hidden",!$("showReasoning").checked);$("messages").append(note);
}
function updateReasoning(){for(const box of document.querySelectorAll(".reasoning,.reasoning-unavailable"))box.classList.toggle("hidden",!$("showReasoning").checked);}
function renderContext(){
 const d=contextUsage,usage=d.prompt_tokens,limit=d.model_context_window;
 const actual=Number.isFinite(usage)&&Number.isFinite(d.completion_tokens)&&Number.isFinite(limit);
 const total=actual?usage+(d.completion_tokens||0):0,percent=actual?Math.round(total/limit*100):null;
 const gauge=$("contextGauge");gauge.style.setProperty("--usage",actual?Math.min(100,percent)+"%":"0%");
 gauge.classList.toggle("unknown",!actual);gauge.classList.toggle("high",actual&&percent>=80);
 gauge.querySelector("span").textContent=actual?percent+"%":"—";
 let description=actual?("Last request: "+total.toLocaleString()+" / "+limit.toLocaleString()+" tokens ("+percent+"%). Input "+usage.toLocaleString()+", output "+(d.completion_tokens||0).toLocaleString()+". Usage is reported by the endpoint; capacity is configured or discovered."):"Model context percentage unavailable. "+(Number.isFinite(usage)?"The endpoint reported "+usage.toLocaleString()+" input tokens. ":"")+(limit?"Waiting for endpoint token usage.":"The model’s context capacity is not known. Set a confirmed capacity in connection settings.");
 if(d.characters)description+=" Local input guard: "+Math.round(d.characters/d.character_limit*100)+"% ("+d.characters.toLocaleString()+" / "+d.character_limit.toLocaleString()+" characters). This is not a model token count.";
 if(d.model)description="Model: "+d.model+". "+description;
 description+=" Usage refers to the latest request, not a cumulative billing total. Start a new conversation when context becomes full.";
 gauge.title=description;gauge.setAttribute("aria-label",actual?"Context usage "+percent+" percent":"Context usage unknown");$("contextDetails").textContent=description;
}
