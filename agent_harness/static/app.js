async function send(event){
  event?.preventDefault();if(busy)return;
  const prompt=$("prompt").value.trim();if(!prompt)return;
  error("");setBusy(true);
  try{
    if(!sessionId)await newSession(prompt.slice(0,40));
    const data=await api("/sessions/"+sessionId+"/runs",{prompt,model_id:$("model").value||null});
    addMessage("user",prompt);$("prompt").value="";runId=data.run_id;after=0;events=[];
    $("events").replaceChildren();const mine=++generation;await poll(mine);await listSessions();
  }catch(e){error(e.message);setBusy(false);}
}
async function decide(approved){
  $("approve").disabled=$("deny").disabled=true;
  try{await api("/runs/"+runId+"/approval",{approval_id:approvalId,approved});$("approval").classList.add("hidden");}
  catch(e){error(e.message);}
  finally{$("approve").disabled=$("deny").disabled=false;}
}
$("composer").onsubmit=send;
$("prompt").onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==="Enter")send(e);};
$("newSession").onclick=()=>newSession().catch(e=>error(e.message));
$("model").onchange=showProvider;
$("demo").onclick=()=>{$("prompt").value="运行离线编码演示，创建脚本、执行并读取结果。";send();};
$("approve").onclick=()=>decide(true);$("deny").onclick=()=>decide(false);
$("cancel").onclick=async()=>{try{await api("/runs/"+runId+"/cancel",{});}catch(e){error(e.message);}};
$("settingsButton").onclick=()=>$("settingsDialog").showModal();
$("closeSettings").onclick=()=>$("settingsDialog").close();
$("authMode").onchange=()=>{const mode=$("authMode").value;$("envField").classList.toggle("hidden",mode==="none");$("keyField").classList.toggle("hidden",mode!=="session");};
$("modelForm").onsubmit=async e=>{
  e.preventDefault();const f=new FormData(e.target);const data=Object.fromEntries(f);
  data.timeout=Number(data.timeout);data.temperature=Number(data.temperature);data.trust_env=f.has("trust_env");
  $("saveModel").disabled=true;$("formError").classList.add("hidden");
  try{config=await api("/models",data);showConfig();$("model").value=data.id;showProvider();e.target.elements.session_api_key.value="";$("settingsDialog").close();error("");}
  catch(e){$("formError").textContent=e.message;$("formError").classList.remove("hidden");}
  finally{$("saveModel").disabled=false;}
};
$("refreshSkills").onclick=async()=>{try{await api("/skills/refresh",{});await loadSkills();}catch(e){error(e.message);}};
$("diagnose").onclick=async()=>{
  if(!$("model").value){error("请先配置一个模型。");return;}
  $("diagnosticDialog").showModal();$("diagnosticResult").textContent="";$("diagnosticStatus").textContent="正在检测聊天和工具调用…";$("diagnose").disabled=true;
  try{const data=await api("/diagnostics/"+encodeURIComponent($("model").value),{});$("diagnosticStatus").textContent=data.tools==="passed"?"聊天及工具回传验证通过":"检测已结束，请查看结果";$("diagnosticResult").textContent=JSON.stringify(data,null,2);}
  catch(e){$("diagnosticStatus").textContent="检测失败";$("diagnosticResult").textContent=e.message;}
  finally{$("diagnose").disabled=false;}
};
$("closeDiagnostic").onclick=()=>$("diagnosticDialog").close();
$("export").onclick=()=>{
  const url=URL.createObjectURL(new Blob([JSON.stringify({run_id:runId,events},null,2)],{type:"application/json"}));
  const a=document.createElement("a");a.href=url;a.download="harness-run-"+(runId||"empty")+".json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
(async()=>{try{
  config=await api("/config");showConfig();await loadSkills();const sessions=await listSessions();
  const saved=localStorage.getItem("harness.session");
  if(sessions.some(s=>s.id===saved))await loadSession(saved);
  else if(sessions.length)await loadSession(sessions[0].id);
}catch(e){error(e.message);}})();
