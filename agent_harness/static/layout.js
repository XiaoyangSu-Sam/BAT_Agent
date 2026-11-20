"use strict";
function showEditor(open=true){
 $("editorPanel").classList.toggle("hidden",!open);$("editorResize").classList.toggle("hidden",!open);
 $("filesActivity").setAttribute("aria-expanded",String(open));
 if(!open){$("workArea").classList.remove("editor-maximized");$("expandEditor").textContent="Expand";$("expandEditor").setAttribute("aria-pressed","false");$("prompt").focus();}
 requestAnimationFrame(()=>window.dispatchEvent(new Event("resize")));
}
function initLayoutEvents(){
 $("filesActivity").onclick=()=>{showEditor($("editorPanel").classList.contains("hidden"));if(!$("editorPanel").classList.contains("hidden"))$("fileFilter").focus();};
 $("closeEditor").onclick=()=>showEditor(false);
 $("expandEditor").onclick=()=>{const expanded=$("workArea").classList.toggle("editor-maximized");$("expandEditor").textContent=expanded?"Split view":"Expand";$("expandEditor").setAttribute("aria-pressed",String(expanded));requestAnimationFrame(()=>window.dispatchEvent(new Event("resize")));};
 $("chatActivity").onclick=()=>{if(window.innerWidth<=760)$("workArea").classList.toggle("history-open");else $("workArea").classList.toggle("history-hidden");};
 $("sessionFilter").oninput=renderSessions;
 const handle=$("editorResize");const size=value=>{const width=Math.max(330,Math.min(window.innerWidth*.68,value));document.documentElement.style.setProperty("--editor-width",width+"px");};
 handle.onpointerdown=e=>{handle.setPointerCapture(e.pointerId);handle.onpointermove=event=>size(window.innerWidth-event.clientX);handle.onpointerup=handle.onpointercancel=()=>{handle.onpointermove=null;};};
 handle.onkeydown=e=>{if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();size($("editorPanel").getBoundingClientRect().width+(e.key==="ArrowLeft"?30:-30));}};
 $("resetExecution").onclick=async()=>{if(!sessionId)return;$("resetExecution").disabled=true;try{await api("/sessions/"+sessionId+"/execution-approval",{allow_all:false});await listSessions();}catch(e){error(e.message);}finally{$("resetExecution").disabled=false;}};
}
