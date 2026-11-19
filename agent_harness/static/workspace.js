"use strict";
let activePath=null,filePaths=[],editor,dialogAction=null;
const documents=new Map(),expandedFolders=new Set();
function normalize(text){return text.replace(/\r\n/g,"\n");}
function extensionLabel(path){return ({py:"Python",js:"JavaScript",ts:"TypeScript",json:"JSON",yaml:"YAML",yml:"YAML",md:"Markdown",html:"HTML",css:"CSS",toml:"TOML"})[path?.split(".").pop()]||"Plain Text";}
function fileIcon(path){return ({py:"py",js:"JS",ts:"TS",json:"{}",md:"M↓",yaml:"Y",yml:"Y",html:"<>",css:"#",toml:"⚙"})[path.split(".").pop()]||"≡";}
function initEditor(){editor=BATEditor.create($("editorHost"),text=>{const doc=documents.get(activePath);if(doc){doc.content=text;doc.dirty=text!==doc.base;renderTabs();updateEditorStatus();}},
 (line,col)=>{$("cursorStatus").textContent="Ln "+line+", Col "+col;},()=>saveActive().catch(e=>error(e.message)));window.editorReady=true;}
function hasDirty(){return [...documents.values()].some(d=>d.dirty);}
function updateEditorStatus(){const doc=documents.get(activePath);$("saveFile").disabled=!doc||!doc.dirty||busy;$("editorHint").textContent=doc?(doc.dirty?"Unsaved":busy?"Agent is working · Read only":"Saved"):"";$("fileConflict").classList.toggle("hidden",!doc?.conflict);$("languageStatus").textContent=extensionLabel(activePath);$("encodingStatus").textContent=doc?"UTF-8 · "+doc.line_ending:"UTF-8";}
function renderTabs(){
 $("editorTabs").replaceChildren();for(const [name,doc] of documents){
 const tab=el("div",undefined,"editor-tab"+(name===activePath?" active":""));tab.setAttribute("role","tab");tab.setAttribute("aria-selected",String(name===activePath));tab.tabIndex=0;tab.title=name;
 tab.append(el("span",fileIcon(name),"file-icon"),el("span",name.split("/").pop()),el("span",doc.dirty?"●":"","dirty"));const close=el("button","×","tab-close");close.setAttribute("aria-label","Close "+name);close.onclick=e=>{e.stopPropagation();closeFile(name);};tab.append(close);
 tab.onclick=()=>activate(name);tab.onkeydown=e=>{if(e.key==="Enter")activate(name);};$("editorTabs").append(tab);
 }if(!documents.size)$("editorTabs").append(el("span","Welcome","empty-tab"));updateEditorStatus();
}
function activate(name){activePath=name;const doc=documents.get(name);$("editorEmpty").classList.toggle("hidden",!!doc);$("editorHost").classList.toggle("hidden",!doc);
 if(doc){editor.load(doc.content,name,busy);$("breadcrumbs").textContent=name.replaceAll("/","  ›  ");}else $("breadcrumbs").textContent=config.workspace;
 renderTabs();renderFileTree();updateContext();
}
async function openFile(name){if(!documents.has(name)){const data=await api("/workspace/file?path="+encodeURIComponent(name));const text=normalize(data.content);documents.set(name,{...data,base:text,content:text,dirty:false,conflict:false});}activate(name);}
function closeFile(name){const doc=documents.get(name);if(doc?.dirty&&!confirm("“"+name+"” has unsaved changes. Close and discard them?"))return;documents.delete(name);if(activePath===name)activate(documents.keys().next().value||null);else renderTabs();}
async function saveActive(){
 const name=activePath,doc=documents.get(name);if(!doc||!doc.dirty||busy)return;error("");let content=doc.content;
 if(doc.line_ending==="CRLF")content=content.replace(/\n/g,"\r\n");if(doc.bom)content="\ufeff"+content;
 const savedText=doc.content;
 try{const result=await api("/workspace/file",{path:name,content,expected_sha256:doc.sha256});Object.assign(doc,{sha256:result.sha256,base:savedText,dirty:doc.content!==savedText,conflict:false});renderTabs();await refreshFiles();}
 catch(e){if(e.code==="file_conflict"){doc.conflict=true;updateEditorStatus();}throw e;}
}
async function reloadActive(){const doc=documents.get(activePath);if(!doc)return;if(doc.dirty&&!confirm("Reloading will discard unsaved changes in this file. Continue?"))return;
 const data=await api("/workspace/file?path="+encodeURIComponent(activePath));const text=normalize(data.content);documents.set(activePath,{...data,base:text,content:text,dirty:false,conflict:false});activate(activePath);error("");}
async function syncOpenFiles(){
 for(const [name,doc] of documents){try{const data=await api("/workspace/file?path="+encodeURIComponent(name));if(data.sha256!==doc.sha256){
 if(doc.dirty)doc.conflict=true;else{const text=normalize(data.content);Object.assign(doc,data,{base:text,content:text,conflict:false});if(activePath===name)editor.load(text,name,busy);}}}catch(e){doc.conflict=true;}}
 renderTabs();
}
async function syncChangedFile(name){await refreshFiles();if(documents.has(name))await syncOpenFiles();else await openFile(name);}
async function refreshFiles(){const data=await api("/workspace/tree");filePaths=data.files;$("fileLimit").classList.toggle("hidden",!data.possibly_truncated);renderFileTree();}
function renderFileTree(){
 const filter=$("fileFilter").value.toLowerCase();const paths=filePaths.filter(p=>p.toLowerCase().includes(filter));const tree=new Map();
 for(const name of paths){const parts=name.split("/");let cursor=tree;parts.forEach((part,i)=>{if(!cursor.has(part))cursor.set(part,i===parts.length-1?name:new Map());cursor=cursor.get(part);});}
 const host=$("fileTree");host.replaceChildren();
 function draw(branch,parent,depth,prefix=""){for(const [name,value] of [...branch].sort((a,b)=>(a[1] instanceof Map?0:1)-(b[1] instanceof Map?0:1)||a[0].localeCompare(b[0]))){
 if(value instanceof Map){const full=prefix+name;const folder=el("details",undefined,"folder");folder.open=!!filter||expandedFolders.has(full);const summary=el("summary",name,"file-row");summary.style.paddingLeft=(12+depth*13)+"px";folder.append(summary);draw(value,folder,depth+1,full+"/");folder.ontoggle=()=>{folder.open?expandedFolders.add(full):expandedFolders.delete(full);};parent.append(folder);}
 else{const button=el("button",undefined,"file-row"+(value===activePath?" selected":""));button.style.paddingLeft=(15+depth*13)+"px";button.title=value;button.append(el("span",fileIcon(name),"file-icon"),el("span",name));button.onclick=()=>openFile(value).catch(e=>error(e.message));parent.append(button);}
 }}
 draw(tree,host,0);if(!paths.length)host.append(el("p",filter?"No matching files":"This folder is empty. Create a file to begin.","skills-intro"));
}
function updateContext(){const host=$("contextChips");host.replaceChildren();if(activePath&&$("attachFile").checked)host.append(el("span",fileIcon(activePath)+" "+activePath,"context-chip"));for(const id of selectedSkills){const chip=el("button","✧ "+id+" ×","context-chip");chip.type="button";chip.onclick=()=>{selectedSkills.delete(id);updateContext();loadSkills().catch(e=>error(e.message));};host.append(chip);}}
function openTextDialog(title,hint,value,action){dialogAction=action;$("textDialogTitle").textContent=title;$("textDialogHint").textContent=hint;$("textDialogInput").value=value;$("textDialogError").classList.add("hidden");$("textDialog").showModal();$("textDialogInput").focus();}
function chooseFolder(){if(busy)return;openTextDialog("Open workspace","Enter the full path of an existing folder on this computer. The agent and editor will use this folder.",config.workspace,async value=>{
 if(hasDirty())throw new Error("Save or close all unsaved files first.");
 config=await api("/workspace/open",{path:value});documents.clear();activate(null);showConfig();await loadSession(null);await refreshFiles();
 });}
function createFile(){if(busy)return;openTextDialog("New file","Enter a path relative to the workspace, such as src/main.py.","",async value=>{
 if(filePaths.includes(value)||documents.has(value))throw new Error("This file already exists. Open it from the explorer.");
 await api("/workspace/file",{path:value,content:"",expected_sha256:""});await refreshFiles();await openFile(value);editor.focus();
 });}
function initWorkspaceEvents(){
 $("saveFile").onclick=()=>saveActive().catch(e=>error(e.message));$("reloadFile").onclick=()=>reloadActive().catch(e=>error(e.message));
 $("refreshFiles").onclick=async()=>{try{await refreshFiles();await syncOpenFiles();}catch(e){error(e.message);}};
 $("fileFilter").oninput=renderFileTree;$("attachFile").onchange=updateContext;$("newFile").onclick=createFile;
 for(const id of ["openFolder","folderActivity","emptyOpenFolder"])$(id).onclick=chooseFolder;
 $("textDialogClose").onclick=()=>$("textDialog").close();
 $("textDialogForm").onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector(".primary");button.disabled=true;try{await dialogAction($("textDialogInput").value.trim());$("textDialog").close();}catch(err){$("textDialogError").textContent=err.message;$("textDialogError").classList.remove("hidden");}finally{button.disabled=false;}};
 window.addEventListener("beforeunload",e=>{if(hasDirty()){e.preventDefault();e.returnValue="";}});
 window.addEventListener("focus",()=>{if(config&&!$("workbench").classList.contains("hidden")&&!busy)syncOpenFiles().catch(()=>{});});
 document.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){e.preventDefault();saveActive().catch(err=>error(err.message));}});
 function resize(handle,move){handle.onpointerdown=e=>{handle.setPointerCapture(e.pointerId);const listener=event=>move(event);handle.onpointermove=listener;handle.onpointerup=()=>{handle.onpointermove=null;};};}
 resize($("sidebarResize"),e=>document.documentElement.style.setProperty("--sidebar-width",Math.max(280,Math.min(window.innerWidth*.5,e.clientX-48))+"px"));
 resize($("explorerResize"),e=>document.documentElement.style.setProperty("--explorer-height",Math.max(120,Math.min(window.innerHeight*.45,e.clientY-42))+"px"));
}
