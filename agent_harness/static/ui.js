"use strict";
const $=id=>document.getElementById(id), token=document.querySelector('meta[name="harness-token"]').content;
let config,sessionId=null,runId=null,after=0,generation=0,approvalId,events=[],busy=false,selectedSkills=new Set();
let sessionRecords=[];
let draftApprovalMode = null;
let savingApprovalMode = false;
const approvalDescriptions = {
 all: "Ask before editing files or running code",
 execution: "Allow workspace edits and ask before running code",
 trusted: "Allow workspace edits and execution in this conversation"
};
const toolCards=new Map(),requestedTools=new Map(),changedPaths=new Set();
const statuses={running:"Running",awaiting_approval:"Awaiting approval",completed:"Completed",failed:"Failed",cancelled:"Stopped",interrupted:"Previous task interrupted",cancelling:"Stopping"};
const toolLabels={write_skill_file:"Write Skill file",list_files:"Explore files",read_file:"Read file",search_files:"Search code",write_file:"Write file",edit_file:"Edit code",run_command:"Run command",run_python_script:"Run Python",run_notebook:"Run notebook",list_skills:"List Skills",read_skill:"Read Skill",read_skill_resource:"Read Skill resource"};
async function api(path,body){
 const r=await fetch("/api"+path,{method:body===undefined?"GET":"POST",headers:{"Content-Type":"application/json","X-Harness-Token":token},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await r.json();if(!r.ok){const e=new Error(data.error?.message||JSON.stringify(data.detail||data));e.details=data.error;e.code=data.error?.code;e.status=r.status;throw e;}return data;
}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function error(message){$("error").textContent=message;$("error").classList.toggle("hidden",!message);}
function addMessage(role,content,reasoning,elapsedMs){
 if(!content&&!reasoning&&!Number.isFinite(elapsedMs))return;const box=el("article",undefined,"message "+role);
 box.append(el("div",role==="user"?"●  You":"✧  BAT Agent","message-label"));const body=el("div",undefined,"message-body");
 content=(content||"").split("\n\n[Workspace context]\n")[0];
 if(role==="user")body.textContent=content;
 else BATMarkdown.render(body,content);
 if(role==="assistant"&&Number.isFinite(elapsedMs))box.append(modelTimeElement(elapsedMs));
 if(reasoning)box.append(reasoningElement(reasoning));
 box.append(body);$("messages").append(box);$("welcome").classList.add("hidden");scrollChat();
}
function scrollChat(){$("messages").scrollTop=$("messages").scrollHeight;}
function setBusy(value){
 busy=value;if(!value&&modelTimer){modelTimer.node.textContent="Model request ended · timing unavailable";stopModelTimer();}for(const id of ["send","model","newSession","sessions","settingsButton","newFile","openFolder","folderActivity","emptyOpenFolder","refreshSkills","diagnose"])$(id).disabled=value;
 for(const button of document.querySelectorAll(".session-item"))button.disabled=value;
 $("policy").disabled = value || savingApprovalMode;
 if (savingApprovalMode) $("send").disabled = true;
 $("cancel").classList.toggle("hidden",!value);$("thinking").classList.toggle("hidden",!value);if(window.editorReady)editor.readOnly(value);$("diagnose").disabled=value||!$("model").value;$("connectFromWorkspace").disabled=value;updateEditorStatus();
}
function showConfig(){
 const selected=$("model").value || localStorage.getItem("bat.model");$("model").replaceChildren();
 for(const m of config.models){const o=el("option",m.model+(m.id!=="default"?" · "+m.id:""));o.value=m.id;o.disabled=!m.ready;$("model").append(o);}
 const wanted=config.models.find(m=>m.id===selected&&m.ready)||config.models.find(m=>m.id===config.default_model&&m.ready)||config.models.find(m=>m.ready);
 if(!wanted){const option=el("option","No model connected");option.value="";$("model").prepend(option);}
 $("model").value=wanted?.id||"";$("modelNotice").classList.toggle("hidden",!!wanted);$("diagnose").disabled=busy||!wanted;
 const project=config.workspace.split(/[\\/]/).filter(Boolean).pop()||"workspace";
 $("projectName").textContent=project;$("workspaceLabel").textContent=project;$("workspaceLabel").title=config.workspace;
 renderApprovalMode();
 showProvider();
}
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
function renderSessions(){
 const host=$("sessions"),query=$("sessionFilter").value.trim().toLowerCase();host.replaceChildren();
 const matches=sessionRecords.filter(s=>s.title.toLowerCase().includes(query));
 for(const s of matches){const button=el("button",undefined,"session-item"+(s.id===sessionId?" active":""));button.dataset.sessionId=s.id;button.title=s.title;button.disabled=busy;
 button.setAttribute("aria-current",s.id===sessionId?"true":"false");button.append(el("span",s.title,"session-title"),el("span",new Date((s.updated||s.created)*1000).toLocaleDateString(undefined,{month:"short",day:"numeric"}),"session-date"));
 button.onclick=()=>loadSession(s.id).catch(e=>error(e.message));host.append(button);}
 if(!matches.length)host.append(el("p",query?"No matching conversations.":"Your conversations will appear here.","session-empty"));
 const current=sessionRecords.find(s=>s.id===sessionId);$("conversationTitle").textContent=current?.title||"New conversation";
 renderApprovalMode();
}
function renderApprovalMode() {
 const current = sessionRecords.find(s => s.id === sessionId);
 const mode = current?.approval_mode || draftApprovalMode || config.execution.approval_mode;
 const automatic = !!current?.allow_all_execution && mode !== "trusted";
 $("policy").value = mode;
 $("policy").title = approvalDescriptions[mode];
 $("executionPolicyLabel").textContent = automatic
  ? "Execution allowed in this conversation"
  : approvalDescriptions[mode];
 $("resetExecution").classList.toggle("hidden", !automatic);
}

async function changeApprovalMode() {
 const mode = $("policy").value;
 if (!sessionId) {
  draftApprovalMode = mode;
  renderApprovalMode();
  return;
 }
 const id = sessionId;
 savingApprovalMode = true;
 $("policy").disabled = true;
 $("send").disabled = true;
 try {
  const result = await api("/sessions/" + id + "/approval-mode", {approval_mode: mode});
  const current = sessionRecords.find(s => s.id === id);
  if (current) Object.assign(current, result);
 } catch (e) {
  error(e.message);
 } finally {
  savingApprovalMode = false;
  $("policy").disabled = busy;
  $("send").disabled = busy;
  renderApprovalMode();
 }
}
async function listSessions(){sessionRecords=await api("/sessions");renderSessions();return sessionRecords;}
function resetRun(){$("activityCount").textContent="";stopModelTimer();events=[];after=0;runId=null;toolCards.clear();requestedTools.clear();changedPaths.clear();$("changeCount").textContent="0";$("events").replaceChildren();$("changes").replaceChildren();$("output").textContent="Process output will appear here.";$("approval").classList.add("hidden");$("runStatus").textContent="Ready";contextUsage={};renderContext();communication("idle","Ready · No request in progress");}
function clearMessages(){for(const node of [...$("messages").children])if(node.id!=="welcome")node.remove();$("welcome").classList.remove("hidden");}
async function loadSession(id){if(busy&&id!==sessionId){error("Stop the current task before switching conversations.");return;}$("workArea").classList.remove("history-open");generation++;sessionId=id;localStorage.setItem("bat.session",id||"");clearMessages();resetRun();setBusy(false);error("");
 draftApprovalMode=null;
 renderSessions();if(!id){await listSessions();return;}const s=await api("/sessions/"+id);for(const m of s.messages)if(["user","assistant"].includes(m.role))addMessage(m.role,m.content,m._reasoning,m._model_elapsed_ms);await listSessions();
 if(s.runs.length){runId=s.runs[0].id;await poll(++generation,true);}}
function renderEvent(event,initial,modelId){
 events.push(event);$("activityCount").textContent=events.length+" events";after=Math.max(after,event.seq);const d=event.data;
 const detail=el("details",undefined,"event");detail.append(el("summary",(d.name||event.type)+" · "+new Date(event.time*1000).toLocaleTimeString()),el("pre",JSON.stringify(d,null,2)));$("events").append(detail);
 if(event.type==="model_wait_started")beginModelTimer(d,initial);
 if(event.type==="model_wait_finished")finishModelTimer(d,initial);
 if(event.type==="model_request")communication("sending","Sending request · "+d.model);
 if(event.type==="communication")communication(d.phase,d.message);
 if(event.type==="model_response"){
  communication("received","Response received");
  if (!initial) recordModelHealth(modelId, true, "Valid model reply received", event.time * 1000);
 }
 if(modelId === $("model").value && event.type==="context_usage"){contextUsage={...d};renderContext();}
 if(modelId === $("model").value && event.type==="token_usage"){contextUsage={...contextUsage,...d};renderContext();}
 if(event.type==="reasoning"&&!initial){if(d.available){$("messages").append(reasoningElement(d.content));scrollChat();}else reasoningUnavailable();}
 if(event.type==="run_started"){communication("sending","Starting · "+d.model);}
 if(event.type==="error"){
  communication("failed","Request failed · "+d.message);
  const connectionFailure = ["http", "network", "tls", "response"].includes(d.stage)
   || ["invalid_model_response", "invalid_json_response"].includes(d.code);
  if (!initial && connectionFailure) {
   recordModelHealth(modelId, false, d.message, event.time * 1000);
  }
 }
 if(event.type==="completed")communication("idle","Ready · Last task completed");
 if(event.type==="cancelled")communication("idle","Stopped · No request in progress");
 if(event.type==="model_retry")communication("retrying","Retrying connection…");
 if(event.type==="tool_requested"){requestedTools.set(d.call_id,d);const card=el("details",undefined,"tool-card");card.append(el("summary",(toolLabels[d.name]||d.name)+(d.arguments.path?" · "+d.arguments.path:"")),el("pre",JSON.stringify(d.arguments,null,2)));toolCards.set(d.call_id,card);$("messages").append(card);$("thinkingText").textContent=toolLabels[d.name]||d.name;scrollChat();}
 if(event.type==="tool_result"){
 const card=toolCards.get(d.call_id);if(card){card.classList.add(d.ok?"done":"failed");card.querySelector("summary").textContent=(d.ok?"✓ ":"× ")+card.querySelector("summary").textContent;card.append(el("pre",JSON.stringify(d.ok?d.result:d.error,null,2)));}
 const result=d.result||{};if("stdout" in result||"stderr" in result){if($("output").textContent==="Process output will appear here.")$("output").textContent="";$("output").textContent+="> "+d.name+"\n"+(result.stdout||"")+(result.stderr?"\n[stderr]\n"+result.stderr:"")+"\nExit code: "+result.exit_code+(result.timed_out?" · Timed out":"")+"\n\n";$("output").scrollTop=$("output").scrollHeight;}
 if(result.scope==="skill"){loadSkills().catch(e=>error(e.message));}
 if(result.diff!==undefined){const displayPath=result.scope==="skill"?"skills/"+result.skill_id+"/"+result.path:result.path;changedPaths.add(displayPath);$("changeCount").textContent=changedPaths.size;const change=el("details",undefined,"change");change.open=true;const summary=el("summary",displayPath);summary.onclick=()=>{if(result.scope==="skill")showSkill(result.skill_id);else openFile(result.path).catch(e=>error(e.message));};change.append(summary,el("pre",result.diff||"No text changes"));$("changes").append(change);if(result.scope!=="skill")syncChangedFile(result.path).catch(e=>error(e.message));}
 }
 if(event.type==="approval_required"){$("allowAll").classList.toggle("hidden",!(d.can_allow_all ?? (d.kind==="execute")));communication("approval","Waiting for your approval");approvalId=d.approval_id;$("approvalText").textContent=d.name+"\n"+JSON.stringify(d.arguments,null,2);$("approval").classList.remove("hidden");}
 if(event.type==="approval_policy_changed")listSessions().catch(e=>error(e.message));
 if(event.type==="approval_resolved")$("approval").classList.add("hidden");
}
async function poll(mine,initial=false){
 if(mine!==generation||!runId)return;
 try{const data=await api("/runs/"+runId+"?after="+after);if(mine!==generation)return;
 for(const event of data.events){renderEvent(event,initial,data.model_id);if(!initial&&event.type==="assistant")addMessage("assistant",event.data.content);}
 const active=["running","awaiting_approval","cancelling"].includes(data.status);setBusy(active);$("runStatus").textContent=statuses[data.status]||data.status;
 if(!active){$("approval").classList.add("hidden");await refreshFiles();await syncOpenFiles();}
 if(data.error)error(data.error.message+(data.error.suggestions?" "+data.error.suggestions.join(" "):""));
 if(active||data.events.length===200)setTimeout(()=>poll(mine,initial&&data.events.length===200),active?700:20);
 }catch(e){if(mine===generation){error("Unable to read task status: "+e.message);setTimeout(()=>poll(mine,initial),2200);}}
}

let contextUsage={};
function communication(phase,message){
 $("communicationStatus").textContent=message;$("communicationStatus").title=message;
 $("communicationDot").className="phase-"+phase;$("thinkingText").textContent=message;
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
 const {prompt_tokens, completion_tokens, model_context_window, characters, character_limit} = contextUsage;
 const tokensKnown = model_context_window > 0
  && Number.isFinite(prompt_tokens) && Number.isFinite(completion_tokens);
 const localKnown = character_limit > 0 && Number.isFinite(characters);
 const total = tokensKnown ? prompt_tokens + completion_tokens : characters;
 const limit = tokensKnown ? model_context_window : character_limit;
 const ratio = tokensKnown || localKnown ? Math.max(0, total / limit) : null;
 const percent = ratio === null ? null : Math.floor(Math.max(0, total * 100 / limit));
 const gauge = $("contextGauge");
 gauge.style.setProperty("--usage", ratio === null ? "0%" : Math.min(100, ratio * 100) + "%");
 gauge.dataset.level = ratio === null ? "unknown" : ratio >= 0.90 ? "critical" : ratio >= 0.70 ? "warning" : "normal";
 gauge.querySelector("span").textContent = percent === null ? "—" : percent + "%";
 $("contextBasis").classList.toggle("hidden", tokensKnown || !localKnown);
 const label = tokensKnown ? "Model context" : localKnown ? "Local input limit" : "Context usage";
 let detail;
 if (tokensKnown) {
  detail = `Last request used ${total.toLocaleString()} / ${limit.toLocaleString()} tokens (${percent}%). `
   + `Input ${prompt_tokens.toLocaleString()}, output ${completion_tokens.toLocaleString()}.`;
 } else if (localKnown) {
  detail = `Local input used ${characters.toLocaleString()} / ${character_limit.toLocaleString()} characters (${percent}%). `
   + "Model token usage or context capacity is unavailable.";
 } else {
  detail = "Context usage appears after a request. Set the model's confirmed context window in connection settings if it is unavailable.";
 }
 gauge.title = detail;
 gauge.setAttribute("aria-label", label + (percent === null ? " unknown" : " " + percent + " percent"));
 $("contextDetails").textContent = detail;
}

let modelTimer=null;
const modelTimeHelp="Elapsed model request time, including network and retries. Excludes tools and approval waits; not a measurement of internal reasoning alone.";
function formatModelTime(ms){const seconds=Math.max(0,ms)/1000;return seconds<60?seconds.toFixed(1)+" s":Math.floor(seconds/60)+" min "+Math.floor(seconds%60)+" s";}
function modelTimeElement(ms){const node=el("div","Model time · "+formatModelTime(ms),"model-time");node.title=modelTimeHelp;return node;}
function stopModelTimer(){if(modelTimer){clearInterval(modelTimer.interval);modelTimer.node.classList.remove("pending");modelTimer=null;}}
function beginModelTimer(data,initial){
 stopModelTimer();const node=modelTimeElement(0);node.classList.add("pending");$("messages").append(node);$("welcome").classList.add("hidden");
 const started=Number.isFinite(data.started_at)?data.started_at*1000:Date.now();
 const tick=()=>{node.textContent="Thinking · "+formatModelTime(Date.now()-started);};tick();
 modelTimer={node,step:data.step,interval:setInterval(tick,250)};if(!initial)scrollChat();
}
function finishModelTimer(data,initial){
 if(!modelTimer||modelTimer.step!==data.step)return;const node=modelTimer.node;stopModelTimer();
 if(initial&&data.outcome==="received"){node.remove();return;}
 const label=data.outcome==="received"?"Model time":data.outcome==="cancelled"?"Stopped after":"Request failed after";
 node.textContent=label+" · "+formatModelTime(data.elapsed_ms);
}
