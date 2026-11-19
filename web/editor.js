import {basicSetup} from 'codemirror';
import {EditorState, Compartment} from '@codemirror/state';
import {EditorView, keymap} from '@codemirror/view';
import {indentWithTab} from '@codemirror/commands';
import {oneDark} from '@codemirror/theme-one-dark';
import {python} from '@codemirror/lang-python';
import {javascript} from '@codemirror/lang-javascript';
import {json} from '@codemirror/lang-json';
import {html} from '@codemirror/lang-html';
import {css} from '@codemirror/lang-css';
import {markdown} from '@codemirror/lang-markdown';
import {yaml} from '@codemirror/lang-yaml';
function language(path) {
 const ext=path.split('.').pop().toLowerCase();
 return ({py:python,js:javascript,cjs:javascript,mjs:javascript,ts:()=>javascript({typescript:true}),
 jsx:()=>javascript({jsx:true}),tsx:()=>javascript({typescript:true,jsx:true}),
 json,html,css,md:markdown,yaml,yml:yaml}[ext]||(()=>[]))();
}
window.BATEditor={create(parent,onChange,onCursor,onSave){
 const lock=new Compartment(); let loading=false;
 const extensions=(path,readOnly)=>[basicSetup,oneDark,language(path),
 lock.of([EditorState.readOnly.of(readOnly),EditorView.editable.of(!readOnly)]),
 EditorView.contentAttributes.of({'aria-label':'代码编辑器'}),
 keymap.of([{key:'Mod-s',run:()=>{onSave();return true;}},indentWithTab]),
 EditorView.theme({'&':{height:'100%',backgroundColor:'#1e1f22',fontSize:'13px'},
 '.cm-scroller':{fontFamily:'Consolas, "SFMono-Regular", monospace',lineHeight:'1.75'},
 '.cm-gutters':{backgroundColor:'#1e1f22',border:'none',color:'#676c7b'},
 '.cm-activeLineGutter':{backgroundColor:'#282a31'},'.cm-content':{padding:'16px 0'},
 '.cm-line':{padding:'0 16px'}}),
 EditorView.updateListener.of(update=>{
 if(update.docChanged&&!loading)onChange(update.state.doc.toString());
 if(update.selectionSet||update.docChanged){const pos=update.state.selection.main.head;
 const line=update.state.doc.lineAt(pos);onCursor(line.number,pos-line.from+1);}
 })];
 const view=new EditorView({parent,state:EditorState.create({extensions:extensions('',true)})});
 return {load(content,path,readOnly=false){loading=true;view.setState(EditorState.create({doc:content,extensions:extensions(path,readOnly)}));loading=false;},
 readOnly(value){view.dispatch({effects:lock.reconfigure([EditorState.readOnly.of(value),EditorView.editable.of(!value)])});},
 text(){return view.state.doc.toString();},focus(){view.focus();}};
}};
