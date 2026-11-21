"use strict";
let testedConnection=null,connectionVersion=0,testingConnection=false,discoveredModels=[];
const modelHealth = new Map();
const modelChecks = new Set();
const healthMaxAge = 120_000;

function showProvider() {
 const model = config.models.find(m => m.id === $("model").value);
 const badge = $("providerBadge");
 const result = modelHealth.get(model?.id);
 const state = model?.provider === "fake" ? "demo"
  : !model ? "unconfigured"
  : modelChecks.has(model.id) ? "checking"
  : result?.state || "unknown";
 const labels = {
  demo: "Offline demo", unconfigured: "Not connected", checking: "Checking",
  unknown: "Not checked", online: "Connected", offline: "Connection failed"
 };
 const label = labels[state];
 $("providerText").textContent = label;
 badge.dataset.state = state;
 badge.disabled = !model || model.provider === "fake";
 const lines = [model ? model.model + " · " + label : label];
 if (result) lines.push(result.detail, "Checked " + new Date(result.time).toLocaleTimeString());
 if (!badge.disabled) lines.push("Click to check again");
 badge.title = lines.join("\n");
 badge.setAttribute("aria-label", lines.join(". "));
}

function recordModelHealth(id, connected, detail, time = Date.now()) {
 const model = config.models.find(m => m.id === id);
 if (!model || model.provider === "fake" || (modelHealth.get(id)?.time ?? 0) > time) return;
 modelHealth.set(id, {state: connected ? "online" : "offline", detail, time});
 showProvider();
}

async function checkSelectedModel(force = false) {
 if (busy || document.hidden || !$("connectionScreen").classList.contains("hidden")) return;
 const id = $("model").value;
 const model = config?.models.find(m => m.id === id);
 if (!model?.ready || model.provider === "fake" || modelChecks.has(id)) return;
 if (!force && Date.now() - (modelHealth.get(id)?.time ?? 0) < healthMaxAge) return;
 const started = Date.now();
 modelChecks.add(id);
 showProvider();
 const isCurrentConfig = () => config.models.find(m => m.id === id) === model;
 try {
  const result = await api("/models/" + encodeURIComponent(id) + "/check", {});
  if (isCurrentConfig()) recordModelHealth(id, result.connected, result.message, started);
 } catch (e) {
  if (e.code !== "workspace_busy" && isCurrentConfig()) recordModelHealth(id, false, e.message, started);
 } finally {
  modelChecks.delete(id);
  showProvider();
  if (!isCurrentConfig() && $("model").value === id) checkSelectedModel();
 }
}

function activateModel(id) {
 $("model").value = id;
 localStorage.setItem("bat.model", id);
 $("diagnose").disabled = busy || !id;
 contextUsage = {};
 renderContext();
 communication("idle", "Ready · No request in progress");
 showProvider();
 checkSelectedModel();
}

function connectionValue(){
 const secret=$("apiKey").value,env=$("keyEnv").value.trim(),existing=config.models.find(m=>m.id===$("savedConnection").value);
 return {id:$("connectionId").value.trim(),endpoint:$("endpoint").value.trim(),model:$("modelName").value.trim(),
 create_only:!existing,
 endpoint_mode:$("endpointMode").value,
 auth_mode:secret?"session":env?"env":$("reuseKey").checked?"saved":"none",session_api_key:secret,api_key_env:env||"LLM_API_KEY",
 tool_mode:$("toolMode").value,temperature:existing?.temperature??0.2,timeout:existing?.timeout??180,
 connect_timeout:existing?.connect_timeout??10,max_retries:existing?.max_retries??2,max_tokens:existing?.max_tokens??4096,trust_env:existing?.trust_env??true,context_window:$("contextWindow").value?Number($("contextWindow").value):null};
}
function invalidateConnection(){connectionVersion++;testedConnection=null;$("enterWorkspace").disabled=true;$("connectionResult").classList.add("hidden");$("useSavedModel").disabled=true;}
function fillConnection(current){
 invalidateConnection();const real=current?.provider!=="fake";
 $("endpoint").value=real?current?.endpoint||"":"";
 $("endpointMode").value=real?current?.endpoint_mode||"auto":"auto";
 $("modelName").value=real?current?.model||"":"";
 let availableId = "default";
 for (let n = 2; config.models.some(m => m.id === availableId); n++) availableId = "connection-" + n;
 $("connectionId").value=real?current?.id||availableId:availableId;
 $("connectionId").readOnly=!!current && real;
 $("apiKey").value="";$("keyEnv").value=current?.credential_env||"";$("toolMode").value=current?.tool_mode||"native";
 $("contextWindow").value=current?.context_window||"";
 $("reuseKey").checked=!!current?.ready&&!!current?.credential_configured&&!current?.credential_env;
 $("reuseKeyLabel").classList.toggle("hidden",!$("reuseKey").checked);
 $("savedConnection").value=real?current?.id||"":"";
 $("useSavedModel").classList.toggle("hidden", !current?.ready || !real);
 $("useSavedModel").disabled = !current?.ready || !real;
 $("enterWorkspace").firstChild.textContent = current && real ? "Save changes & use " : "Save & use model ";
 $("discoveredModels").replaceChildren();$("discoveredModels").classList.add("hidden");
 $("discoveryHelp").textContent="Find models fills a dropdown from your service. You can also enter a name.";
}
function showConnection(required=false){
 const current=config.models.find(m=>m.id===$("model").value)||config.models.find(m=>m.id===config.default_model);
 $("savedConnection").replaceChildren(el("option","New connection…"));$("savedConnection").firstChild.value="";
 for(const m of config.models.filter(m=>m.provider!=="fake")){const option=el("option",m.model+" · "+m.id);option.value=m.id;$("savedConnection").append(option);}
 $("previewWorkspace").classList.toggle("hidden",!config.setup_required);document.querySelector(".preview-note").classList.toggle("hidden",!config.setup_required);
 fillConnection(current);$("connectionTitle").textContent=required?"Connect your model":"Model connection settings";
 $("connectionClose").classList.toggle("hidden",required);$("connectionScreen").classList.remove("hidden");
 if(required)$("workbench").classList.add("hidden");$("endpoint").focus();
}
function connectionResult(text,kind){$("connectionResult").textContent=text;$("connectionResult").className="connection-result "+kind;}
function renderConnectionReport(result,failed=false){
 const host=$("connectionResult");host.replaceChildren();host.className="connection-result "+(failed?"failure":"success");
 host.append(el("strong",failed?"Connection failed — "+result.message:"Connected to "+result.model+" · "+result.elapsed_ms+" ms"));
 if(result.http_status)host.append(el("div","HTTP "+result.http_status));
 if(result.checks?.length){const list=el("ul");for(const c of result.checks)list.append(el("li",c.message));host.append(list);}
 if(failed){const actions=result.suggestions||["Check the endpoint and model name, then try again."];
 const list=el("ul");for(const action of actions)list.append(el("li",action));host.append(list);}
 const detail=el("details");detail.append(el("summary","Technical details"),
 el("pre",JSON.stringify(result,null,2)));host.append(detail);
}
function initConnectionEvents(){
 $("previewWorkspace").onclick=async()=>{
 connectionVersion++;$("apiKey").value="";sessionStorage.setItem("bat.preview","true");
 $("connectionScreen").classList.add("hidden");
 try{await enterWorkbench();}catch(e){error(e.message);}
 };
 $("connectFromWorkspace").onclick=()=>showConnection(false);
 $("connectionForm").oninput=e=>{if(e.target.id!=="savedConnection")invalidateConnection();};
 $("connectionForm").onchange=e=>{if(e.target.id!=="savedConnection")invalidateConnection();};
 $("endpoint").addEventListener("input",()=>{$("discoveredModels").classList.add("hidden");$("discoveryHelp").textContent="Endpoint changed. Find models again to refresh the list.";$("reuseKey").checked=false;$("reuseKeyLabel").classList.add("hidden");});
 $("connectionId").addEventListener("input",()=>{$("reuseKey").checked=false;$("reuseKeyLabel").classList.add("hidden");});
 $("savedConnection").onchange=()=>fillConnection(config.models.find(m=>m.id===$("savedConnection").value));
 $("addModel").onclick=()=>{fillConnection();$("connectionId").focus();};
 $("useSavedModel").onclick=async()=>{
  const id = $("savedConnection").value;
  if (!config.models.some(m => m.id === id && m.ready)) return;
  $("connectionScreen").classList.add("hidden");
  activateModel(id);
  try { await enterWorkbench(); } catch (e) { error(e.message); }
 };
 $("discoveredModels").onchange=()=>{const item=discoveredModels.find(m=>m.id===$("discoveredModels").value);if(item){$("modelName").value=item.id;$("contextWindow").value=item.context_window||"";}invalidateConnection();};
 $("findModels").onclick=async()=>{
 if(!$("endpoint").reportValidity())return;
 const value=connectionValue();value.model=value.model||"discovery";
 const version=connectionVersion;$("findModels").disabled=true;$("discoveryHelp").textContent="Requesting available models…";
 try{const result=await api("/models/discover",value);if(version!==connectionVersion)return;
 discoveredModels=result.models;$("discoveredModels").replaceChildren();const option=el("option","Choose an available model…");option.value="";$("discoveredModels").append(option);
 for(const m of discoveredModels){const option=el("option",m.id);option.value=m.id;$("discoveredModels").append(option);}
 $("discoveredModels").classList.toggle("hidden",!discoveredModels.length);
 $("discoveryHelp").textContent=discoveredModels.length?"Select a model below. The service supplied this list.":"No models were listed. Enter the model name from your service owner.";
 }catch(e){if(version===connectionVersion)$("discoveryHelp").textContent=e.message+" You can still enter a model name and test it.";}
 finally{$("findModels").disabled=false;}
 };
 $("connectionClose").onclick=()=>{connectionVersion++;$("apiKey").value="";$("connectionScreen").classList.add("hidden");checkSelectedModel();};
 $("testConnection").onclick=async()=>{
 if(testingConnection||!$("connectionForm").reportValidity())return;
 const value=connectionValue(),fingerprint=JSON.stringify(value),version=++connectionVersion;
 if (value.create_only && config.models.some(m => m.id === value.id)) {
  connectionResult("Choose a unique connection name.", "failure");
  return;
 }
 testingConnection=true;testedConnection=null;$("testConnection").disabled=true;$("testConnection").textContent="Connecting…";$("enterWorkspace").disabled=true;
 connectionResult("Testing your endpoint… This may take up to 30 seconds.","pending");
 try{const result=await api("/models/test",value);if(version!==connectionVersion||fingerprint!==JSON.stringify(connectionValue()))return;
 testedConnection=fingerprint;renderConnectionReport(result);$("enterWorkspace").disabled=false;
 }catch(e){if(version===connectionVersion)renderConnectionReport(e.details||{message:e.message},true);}
 finally{testingConnection=false;$("testConnection").disabled=false;$("testConnection").textContent="Test connection";}
 };
 $("connectionForm").onsubmit=async e=>{
 e.preventDefault();const value=connectionValue();if(testedConnection!==JSON.stringify(value))return;
 $("enterWorkspace").disabled=true;
 try {
  config = await api("/models", value);
  $("apiKey").value = "";
  testedConnection = null;
  showConfig();
  recordModelHealth(value.id, true, "Connection test passed");
  $("connectionScreen").classList.add("hidden");
  activateModel(value.id);
  await enterWorkbench();
 }
 catch(err){connectionResult(err.message,"");}
 };
 $("settingsButton").onclick=()=>showConnection(false);
}
