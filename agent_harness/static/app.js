"use strict";
let boardInitialized=false;
async function enterWorkbench(){
 $("workbench").classList.remove("hidden");showConfig();await refreshFiles();await loadSkills();
 if(!boardInitialized){boardInitialized=true;const sessions=await listSessions(),saved=localStorage.getItem("bat.session");
 if(sessions.some(s=>s.id===saved))await loadSession(saved);else if(sessions.length)await loadSession(sessions[0].id);
 if(filePaths.includes("README.md"))await openFile("README.md");}
 editor.readOnly(busy);
}
async function send(event){
 event?.preventDefault();if(busy)return;const prompt=$("prompt").value.trim();if(!prompt)return;
 if(hasDirty()){error("Save your open files so the agent can work with your latest changes.");return;}
 if(!$("model").value){showConnection(true);return;}
 error("");setBusy(true);communication("sending","Submitting your message…");
 try{if(!sessionId){const created=await api("/sessions",{title:prompt.slice(0,60)});sessionId=created.id;localStorage.setItem("bat.session",sessionId);}
 const context=[];if(activePath&&$("attachFile").checked)context.push("Current file："+activePath+". Use read_file to inspect its content.");
 if(selectedSkills.size)context.push("Use these registered Skills: "+[...selectedSkills].join(", ")+". Read their instructions first.");
 const full=prompt+(context.length?"\n\n[Workspace context]\n"+context.join("\n"):"");
 const data=await api("/sessions/"+sessionId+"/runs",{prompt:full,model_id:$("model").value});
 addMessage("user",prompt);$("prompt").value="";resetRun();runId=data.run_id;await listSessions();await poll(++generation);
 }catch(e){error(e.message);setBusy(false);communication("failed","Request failed · "+e.message);}
}
async function decide(approved){$("approve").disabled=$("deny").disabled=true;try{await api("/runs/"+runId+"/approval",{approval_id:approvalId,approved});$("approval").classList.add("hidden");}catch(e){error(e.message);}finally{$("approve").disabled=$("deny").disabled=false;}}
function toggleSkills(value){const open=value??$("skillsPanel").classList.contains("hidden");$("skillsPanel").classList.toggle("hidden",!open);$("skillsToggle").classList.toggle("active",open);}
function initAppEvents(){
 $("showReasoning").checked=localStorage.getItem("bat.reasoning")==="true";updateReasoning();
 $("showReasoning").onchange=()=>{localStorage.setItem("bat.reasoning",$("showReasoning").checked);updateReasoning();};
 $("contextGauge").onclick=()=>$("contextDetails").classList.toggle("hidden");
 $("composer").onsubmit=send;$("prompt").onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==="Enter")send(e);};
 $("newSession").onclick=()=>loadSession(null).catch(e=>error(e.message));
 $("sessions").onchange=e=>loadSession(e.target.value||null).catch(err=>error(err.message));$("model").onchange=()=>{showProvider();contextUsage={};renderContext();communication("idle","Ready · Selected model has not been tested in this task");};
 $("cancel").onclick=async()=>{try{$("cancel").disabled=true;await api("/runs/"+runId+"/cancel",{});}catch(e){error(e.message);}finally{$("cancel").disabled=false;}};
 $("approve").onclick=()=>decide(true);$("deny").onclick=()=>decide(false);
 $("skillsToggle").onclick=()=>toggleSkills();$("closeSkills").onclick=()=>toggleSkills(false);$("closeSkill").onclick=()=>$("skillDialog").close();
 $("refreshSkills").onclick=async()=>{try{await api("/skills/refresh",{});await loadSkills();}catch(e){error(e.message);}};
 $("filesActivity").onclick=()=>$("fileFilter").focus();$("chatActivity").onclick=()=>$("prompt").focus();
 for(const button of document.querySelectorAll("[data-prompt]"))button.onclick=()=>{$("prompt").value=button.dataset.prompt;$("prompt").focus();};
 for(const button of document.querySelectorAll("[data-panel]"))button.onclick=()=>{
 for(const other of document.querySelectorAll("[data-panel]"))other.classList.toggle("active",other===button);
 for(const id of ["output","changes","events"])$(id).classList.toggle("hidden",id!==button.dataset.panel);};
 $("diagnose").onclick=async()=>{
 if(!$("model").value)return;$("diagnosticDialog").showModal();$("diagnosticStatus").textContent="Testing chat and tool calls with real requests…";$("diagnosticResult").textContent="";$("diagnose").disabled=true;
 try{const data=await api("/diagnostics/"+encodeURIComponent($("model").value),{});$("diagnosticStatus").textContent=data.tools==="passed"?"Chat and tool round-trip passed":data.tools==="disabled"?"Chat works. Tools are disabled for this connection.":data.mode==="offline"?"Offline demo · No real model was tested":"Chat works, but tool support is not confirmed. Check the model service’s tool parser or select JSON protocol in connection settings.";$("diagnosticResult").textContent=JSON.stringify(data,null,2);}
 catch(e){$("diagnosticStatus").textContent="Check failed";$("diagnosticResult").textContent=e.message+"\n\n"+(e.details?.suggestions||[]).join("\n");}
 finally{$("diagnose").disabled=busy;}};
 $("closeDiagnostic").onclick=()=>$("diagnosticDialog").close();
 $("export").onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({run_id:runId,events},null,2)],{type:"application/json"}));const a=el("a");a.href=url;a.download="bat-run-"+(runId||"empty")+".json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
}
(async()=>{try{initEditor();initWorkspaceEvents();initConnectionEvents();initAppEvents();config=await api("/config");$("boot").classList.add("hidden");showConfig();
 if(config.setup_required)showConnection(true);else await enterWorkbench();
 }catch(e){$("boot").classList.remove("hidden");$("boot").textContent="Unable to open workspace: "+e.message;}})();
