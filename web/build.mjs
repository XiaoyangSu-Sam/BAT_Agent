import {build} from 'esbuild';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import path from 'node:path';
await build({entryPoints:['editor.js'],bundle:true,minify:true,format:'iife',target:'es2020',
 outfile:'../agent_harness/static/editor.bundle.js',legalComments:'inline'});
await build({entryPoints:['markdown.js'],bundle:true,minify:true,format:'iife',target:'es2020',
 outfile:'../agent_harness/static/markdown.bundle.js',legalComments:'inline'});
const modules=['marked','dompurify','codemirror','@codemirror','@lezer','@marijn','crelt','style-mod','w3c-keyname'];
const licenses=[];
async function license(folder){
 try{const pkg=JSON.parse(await readFile(path.join(folder,'package.json'),'utf8'));
 for(const name of ['LICENSE','LICENSE.md','LICENSE.txt']){
 try{licenses.push(pkg.name+' '+pkg.version+'\n'+await readFile(path.join(folder,name),'utf8'));return;}catch{}
 }}catch{}
}
for(const name of modules){const folder=path.join('node_modules',name);
 if(name.startsWith('@')){try{for(const sub of await readdir(folder))await license(path.join(folder,sub));}catch{}}
 else await license(folder);
}
await writeFile('../docs/editor-licenses.txt',licenses.join('\n\n--------------------------------\n\n'));
