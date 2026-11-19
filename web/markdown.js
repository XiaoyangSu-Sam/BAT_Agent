import {marked} from 'marked';
import DOMPurify from 'dompurify';
window.BATMarkdown = {
 render(host, text) {
  host.innerHTML = DOMPurify.sanitize(marked.parse(text, {gfm:true, breaks:false}), {
   ALLOWED_TAGS:['p','br','strong','em','del','h1','h2','h3','h4','h5','h6','ul','ol','li','blockquote','pre','code','table','thead','tbody','tr','th','td','hr','a'],
   ALLOWED_ATTR:['href','title','start'], ALLOW_DATA_ATTR:false
  });
  for(const link of host.querySelectorAll('a')) {
   const href=link.getAttribute('href')||'';
   if(!/^(https?:\/\/|mailto:)/i.test(href)) link.removeAttribute('href');
   else {link.target='_blank';link.rel='noopener noreferrer';}
  }
  for(const pre of host.querySelectorAll('pre')){
   const code=pre.querySelector('code'); if(!code)continue;
   const button=document.createElement('button');button.className='copy-code';button.textContent='Copy';
   button.onclick=async()=>{try{await navigator.clipboard.writeText(code.textContent);button.textContent='Copied';}catch{button.textContent='Select to copy';}setTimeout(()=>button.textContent='Copy',1800);};
   pre.prepend(button);
  }
 }
};
