(() => {
  const q=(s,r=document)=>r.querySelector(s), qa=(s,r=document)=>[...r.querySelectorAll(s)];

  const toggle=q('.nav-toggle'), links=q('.primary-links');
  if(toggle&&links){
    toggle.addEventListener('click',()=>{const open=links.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));});
    qa('a',links).forEach(a=>a.addEventListener('click',()=>{links.classList.remove('open');toggle.setAttribute('aria-expanded','false');}));
  }

  const copyText=async(button,text)=>{
    const old=button.textContent;
    try{await navigator.clipboard.writeText(text);button.textContent='Copied';button.classList.add('copied');}
    catch(_){button.textContent='Select text';}
    setTimeout(()=>{button.textContent=old;button.classList.remove('copied');},1300);
  };
  qa('[data-copy]').forEach(b=>b.addEventListener('click',()=>copyText(b,b.dataset.copy||'')));

  // v23 sharded lazy global search
  const dialog=q('[data-search-dialog]'),input=q('[data-site-search]'),results=q('[data-search-results]');
  let lastFocus=null,coreItems=null,apiItems=null,corePromise=null,apiPromise=null;
  const coreVersion='4f9bd5c76dcd',apiVersion='23a7c8b7c5e1';
  const searchURL=(name,version)=>`${window.RAZ_BASE||''}assets/${name}?v=${version}`;
  const loadCore=()=>{if(coreItems)return Promise.resolve(coreItems);if(!corePromise)corePromise=fetch(searchURL('search-core.json',coreVersion),{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error(`search core ${r.status}`);return r.json();}).then(data=>{coreItems=Array.isArray(data)?data:[];return coreItems;});return corePromise;};
  const loadAPI=()=>{if(apiItems)return Promise.resolve(apiItems);if(!apiPromise)apiPromise=fetch(searchURL('search-api-manifest.json',apiVersion),{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error(`search api manifest ${r.status}`);return r.json();}).then(manifest=>Promise.all((Array.isArray(manifest.shards)?manifest.shards:[]).map(shard=>fetch(searchURL(shard.file,shard.digest),{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error(`search api ${r.status}`);return r.json();})))).then(parts=>{apiItems=parts.flatMap(data=>Array.isArray(data)?data:[]);return apiItems;});return apiPromise;};
  const escapeSearch=value=>String(value??'').replace(/[&<>\"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const searchKind=url=>url.startsWith('packages/')?'Package':url.startsWith('docs/diagnostics/')?'Diagnostic':url.startsWith('docs/stdlib/')?'Stdlib API':url.startsWith('docs/api/')?'API':url.startsWith('learn/')?'Book':url.startsWith('releases/')?'Release':url.startsWith('news/')?'News':url.startsWith('docs/')?'Docs':'Site';
  const scoreSearch=(item,term,words)=>{if(!term)return 1;const title=String(item.title||'').toLowerCase(),name=String(item.name||'').toLowerCase(),qualified=String(item.qualified_name||'').toLowerCase(),namespace=String(item.namespace||'').toLowerCase(),kind=String(item.kind||''),description=String(item.description||'').toLowerCase(),keywords=String(item.keywords||'').toLowerCase(),url=String(item.url||'').toLowerCase(),hay=`${title} ${name} ${qualified} ${namespace} ${description} ${keywords}`;if(!words.every(w=>hay.includes(w)))return -1;let score=words.length*20;if(qualified===term)score+=360;if(name===term)score+=280;if(title===term)score+=240;if(qualified.startsWith(term))score+=170;if(title.startsWith(term))score+=130;if(title.includes(term)||qualified.includes(term))score+=70;if(keywords.split(/\s+/).includes(term))score+=55;if(url.includes(term.replace(/::/g,'/')))score+=35;if(/^d\d{4}$/i.test(term)&&name===term)score+=220;if(/^(?:raz\s+|razc\s+)/.test(term)&&kind==='cli')score+=110;if(term.includes('::')&&qualified.includes(term))score+=140;return score;};
  const renderSearch=(term='',includeAPI=false)=>{if(!results)return;const normalized=term.trim().toLowerCase(),words=normalized.split(/\s+/).filter(Boolean);const source=[...(coreItems||[]),...(includeAPI?(apiItems||[]):[])];const ranked=source.map(item=>({item,score:scoreSearch(item,normalized,words)})).filter(x=>x.score>=0).sort((a,b)=>b.score-a.score||String(a.item.title).localeCompare(String(b.item.title))).slice(0,12);results.innerHTML=ranked.length?ranked.map(({item})=>{const href=/^(?:https?:)?\/\//.test(item.url)?item.url:`${window.RAZ_BASE||''}${item.url}`;return `<a class="search-result" href="${escapeSearch(href)}"><span class="search-result-top"><b>${escapeSearch(item.title)}</b><em>${escapeSearch(searchKind(String(item.url||'')))}</em></span><span>${escapeSearch(item.description||'')}</span></a>`;}).join(''):'<div class="search-result search-empty"><b>No results</b><span>Try a package, diagnostic code, command, module, or symbol name.</span></div>';};
  const runSearch=async()=>{const term=(input?.value||'').trim();await loadCore();if(term.length>=2){if(results&&!apiItems)results.setAttribute('aria-busy','true');try{await loadAPI();}finally{results&&results.removeAttribute('aria-busy');}renderSearch(term,true);}else renderSearch(term,false);};
  const openSearch=async()=>{if(!dialog)return;lastFocus=document.activeElement;dialog.hidden=false;document.body.style.overflow='hidden';if(results)results.innerHTML='<div class="search-result search-loading"><b>Loading search…</b><span>Preparing the Raz documentation index.</span></div>';setTimeout(()=>input&&input.focus(),0);try{await loadCore();renderSearch(input?.value||'',false);if((input?.value||'').trim().length>=2)await runSearch();}catch(_){if(results)results.innerHTML='<div class="search-result search-empty"><b>Search unavailable</b><span>The index could not be loaded. Try again in a moment.</span></div>';}};
  const closeSearch=()=>{if(!dialog)return;dialog.hidden=true;document.body.style.overflow='';lastFocus&&lastFocus.focus&&lastFocus.focus();};
  const resultLinks=()=>results?qa('a.search-result',results):[];let searchTimer=null;
  qa('[data-search-open]').forEach(b=>b.addEventListener('click',openSearch));qa('[data-search-close]').forEach(b=>b.addEventListener('click',closeSearch));input&&input.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>runSearch().catch(()=>{}),90);});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openSearch();}if(e.key==='Escape'&&dialog&&!dialog.hidden){e.preventDefault();closeSearch();}if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&document.activeElement?.tagName!=='INPUT'&&document.activeElement?.tagName!=='TEXTAREA'){e.preventDefault();openSearch();}if(dialog&&!dialog.hidden&&(e.key==='ArrowDown'||e.key==='ArrowUp')){const links=resultLinks();if(!links.length)return;e.preventDefault();const current=links.indexOf(document.activeElement),delta=e.key==='ArrowDown'?1:-1,next=current<0?(delta>0?0:links.length-1):(current+delta+links.length)%links.length;links[next].focus();}if(dialog&&!dialog.hidden&&e.key==='Tab'){const focusable=qa('button:not([disabled]),a[href],input:not([disabled])',dialog).filter(el=>el.offsetParent!==null);if(!focusable.length)return;const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
  // end v23 sharded lazy global search
  const platformButtons=qa('[data-platform-button]'), panels=qa('[data-platform-panel]'), detected=q('[data-platform-detected]');
  if(platformButtons.length){
    const ua=(navigator.userAgent||'').toLowerCase(); let platform=ua.includes('windows')?'windows':ua.includes('linux')&&!ua.includes('android')?'linux':'other';
    const select=name=>{platformButtons.forEach(b=>b.classList.toggle('active',b.dataset.platformButton===name));panels.forEach(p=>p.hidden=p.dataset.platformPanel!==name);};
    platformButtons.forEach(b=>b.addEventListener('click',()=>select(b.dataset.platformButton)));
    select(platform); if(detected)detected.textContent=platform==='windows'?'Windows detected':platform==='linux'?'Linux detected':'Other host selected';
  }

  const pkgSearch=q('[data-package-search]'), pkgButtons=qa('[data-package-filter]'), pkgItems=qa('[data-package]'), pkgCount=q('[data-package-count]'), pkgEmpty=q('[data-package-empty]');
  if(pkgItems.length){
    let category='all';
    const filter=()=>{const term=(pkgSearch?.value||'').trim().toLowerCase();let shown=0;pkgItems.forEach(item=>{const okCat=category==='all'||item.dataset.category===category;const okTerm=!term||(item.dataset.search||'').includes(term);const show=okCat&&okTerm;item.hidden=!show;item.classList.toggle('package-filtered-out',!show);if(show){item.style.removeProperty('display');shown++;}else{item.style.setProperty('display','none','important');}});if(pkgCount)pkgCount.textContent=`${shown} package${shown===1?'':'s'}`;if(pkgEmpty){pkgEmpty.hidden=shown!==0;if(shown===0)pkgEmpty.style.removeProperty('display');else pkgEmpty.style.setProperty('display','none','important');}};
    pkgSearch&&pkgSearch.addEventListener('input',filter); pkgButtons.forEach(b=>b.addEventListener('click',()=>{category=b.dataset.packageFilter||'all';pkgButtons.forEach(x=>{const active=x===b;x.classList.toggle('active',active);x.setAttribute('aria-pressed',String(active));});filter();})); filter();
  }


  const escapeHTML=s=>s.replace(/[&<>]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
  const razKeywords=new Set('as async auto await break case comptime const continue defer derive dyn else enum extern false fn for global if impl import in match move mut namespace null private public ref return self spawn static struct thread_local trait true type union unsafe while'.split(' '));
  const razTypes=new Set('i8 i16 i32 i64 u8 u16 u32 u64 usize f32 f64 bool char string void'.split(' '));
  const highlightRaz=code=>{
    if(!code||code.dataset.highlighted==='true')return;
    const src=code.textContent||'';let i=0,out='';
    const emit=(cls,value)=>{out+=cls?`<span class="tok-${cls}">${escapeHTML(value)}</span>`:escapeHTML(value);};
    while(i<src.length){
      const c=src[i],n=src[i+1];
      if(c==='/'&&n==='/'){let j=i+2;while(j<src.length&&src[j]!=='\n')j++;emit('comment',src.slice(i,j));i=j;continue;}
      if(c==='/'&&n==='*'){let j=i+2;while(j<src.length-1&&!(src[j]==='*'&&src[j+1]==='/'))j++;j=Math.min(src.length,j+2);emit('comment',src.slice(i,j));i=j;continue;}
      if(c==='"'||(c==="'"&&n!==undefined)){const quote=c;let j=i+1,escaped=false;while(j<src.length){const ch=src[j];if(!escaped&&ch===quote){j++;break;}escaped=!escaped&&ch==='\\';if(ch!=='\\')escaped=false;j++;}emit('string',src.slice(i,j));i=j;continue;}
      if(/[0-9]/.test(c)){let j=i+1;while(j<src.length&&/[0-9A-Fa-f_xob\.]/.test(src[j]))j++;emit('number',src.slice(i,j));i=j;continue;}
      if(/[A-Za-z_]/.test(c)){let j=i+1;while(j<src.length&&/[A-Za-z0-9_]/.test(src[j]))j++;const word=src.slice(i,j);emit(razKeywords.has(word)?'keyword':razTypes.has(word)?'type':/^[A-Z]/.test(word)?'name':null,word);i=j;continue;}
      if('@'===c){let j=i+1;while(j<src.length&&/[A-Za-z0-9_]/.test(src[j]))j++;emit('attribute',src.slice(i,j));i=j;continue;}
      emit(null,c);i++;
    }
    code.innerHTML=out;code.dataset.highlighted='true';
  };
  qa('code.language-raz').forEach(highlightRaz);
  qa('.code-card').forEach(card=>{const label=q('.code-bar span',card);if(label&&/\b(?:raz|rz)\b/i.test(label.textContent||''))highlightRaz(q('pre code',card));});
  qa('.doc-code').forEach(card=>{if((card.dataset.language||'').toLowerCase()==='raz')highlightRaz(q('pre code',card));});

  const diagSearch=q('[data-diagnostic-search]'),diagButtons=qa('[data-diagnostic-filter]'),diagItems=qa('[data-diagnostic]'),diagCount=q('[data-diagnostic-count]'),diagEmpty=q('[data-diagnostic-empty]');
  if(diagItems.length){let category='all';const filter=()=>{const term=(diagSearch?.value||'').trim().toLowerCase();let shown=0;diagItems.forEach(item=>{const show=(category==='all'||item.dataset.category===category)&&(!term||(item.dataset.search||'').includes(term));item.hidden=!show;if(show)shown++;});if(diagCount)diagCount.textContent=String(shown);if(diagEmpty)diagEmpty.hidden=shown!==0;};diagSearch&&diagSearch.addEventListener('input',filter);diagButtons.forEach(b=>b.addEventListener('click',()=>{category=b.dataset.diagnosticFilter;diagButtons.forEach(x=>x.classList.toggle('active',x===b));filter();}));}

  const stdSearch=q('[data-stdlib-search]'),stdButtons=qa('[data-stdlib-filter]'),stdItems=qa('[data-stdlib-module]'),stdCount=q('[data-stdlib-count]'),stdEmpty=q('[data-stdlib-empty]');
  if(stdItems.length){let layer='all';const filter=()=>{const term=(stdSearch?.value||'').trim().toLowerCase();let shown=0;stdItems.forEach(item=>{const show=(layer==='all'||item.dataset.layer===layer)&&(!term||(item.dataset.search||'').includes(term));item.hidden=!show;if(show)shown++;});if(stdCount)stdCount.textContent=`${shown} module${shown===1?'':'s'} in this snapshot`;if(stdEmpty)stdEmpty.hidden=shown!==0;};stdSearch&&stdSearch.addEventListener('input',filter);stdButtons.forEach(b=>b.addEventListener('click',()=>{layer=b.dataset.stdlibFilter;stdButtons.forEach(x=>x.classList.toggle('active',x===b));filter();}));}

  const stdItemSearch=q('[data-stdlib-item-search]'),stdApiItems=qa('[data-stdlib-api-item]'),stdApiCount=q('[data-stdlib-item-count]'),stdApiEmpty=q('[data-stdlib-item-empty]');
  if(stdApiItems.length){const filterItems=()=>{const term=(stdItemSearch?.value||'').trim().toLowerCase();let shown=0;stdApiItems.forEach(item=>{const show=!term||(item.dataset.search||'').includes(term);item.hidden=!show;if(show)shown++;});if(stdApiCount)stdApiCount.textContent=`${shown} documented item${shown===1?'':'s'}`;if(stdApiEmpty)stdApiEmpty.hidden=shown!==0;};stdItemSearch&&stdItemSearch.addEventListener('input',filterItems);}


  // v8: local, privacy-preserving progress for The Raz Book.
  const bookChapter=q('[data-book-chapter]')?.dataset.bookChapter||q('[data-book-complete]')?.dataset.bookChapter;
  const bookProgressEls=qa('[data-book-progress-count]'),bookBars=qa('[data-book-progress-bar]'),bookNavItems=qa('[data-book-nav-item]'),bookComplete=q('[data-book-complete]'),bookContinue=qa('[data-book-continue]');
  if(bookProgressEls.length||bookNavItems.length||bookComplete||bookContinue.length){
    const total=29, progressKey='raz.book.completed.v1', lastKey='raz.book.last.v1';
    const readCompleted=()=>{try{const value=JSON.parse(localStorage.getItem(progressKey)||'[]');return new Set(Array.isArray(value)?value.map(Number).filter(n=>n>=1&&n<=total):[]);}catch(_){return new Set();}};
    const saveCompleted=set=>{try{localStorage.setItem(progressKey,JSON.stringify([...set].sort((a,b)=>a-b)));}catch(_){}};
    const saveLast=n=>{try{localStorage.setItem(lastKey,String(n));}catch(_){}};
    const readLast=()=>{try{const n=Number(localStorage.getItem(lastKey)||1);return n>=1&&n<=total?n:1;}catch(_){return 1;}};
    let completed=readCompleted();
    if(bookChapter)saveLast(Number(bookChapter));
    const update=()=>{
      const pct=Math.round(completed.size/total*100);
      bookProgressEls.forEach(el=>el.textContent=`${completed.size} / ${total} chapters`);
      bookBars.forEach(el=>el.style.width=`${pct}%`);
      bookNavItems.forEach(el=>{const n=Number(el.dataset.bookNavItem);el.classList.toggle('complete',completed.has(n));});
      if(bookComplete&&bookChapter){const done=completed.has(Number(bookChapter));bookComplete.classList.toggle('complete',done);bookComplete.textContent=done?'Completed ✓':'Mark chapter complete';bookComplete.setAttribute('aria-pressed',String(done));}
      const last=readLast(),slug=`chapter-${String(last).padStart(2,'0')}/index.html`;
      bookContinue.forEach(el=>{el.href=`${el.dataset.bookPrefix||''}${slug}`;el.textContent=last===1?'Start chapter 1 →':`Continue chapter ${last} →`;});
    };
    bookComplete&&bookComplete.addEventListener('click',()=>{const n=Number(bookChapter);completed.has(n)?completed.delete(n):completed.add(n);saveCompleted(completed);update();});
    update();
  }

})();

// v11 unified API reference filters.
(() => {
  const input = document.querySelector('[data-api-search]');
  if (!input) return;
  const entries = [...document.querySelectorAll('[data-api-entry]')];
  const filters = [...document.querySelectorAll('[data-api-filter]')];
  const count = document.querySelector('[data-api-count]');
  const empty = document.querySelector('[data-api-empty]');
  let scope = 'all';
  const apply = () => {
    const q = input.value.trim().toLowerCase();
    let shown = 0;
    entries.forEach(entry => {
      const okScope = scope === 'all' || entry.dataset.apiScope === scope;
      const okText = !q || (entry.dataset.search || '').includes(q);
      const show = okScope && okText;
      entry.hidden = !show;
      if (show) shown += 1;
    });
    if (count) count.textContent = `${shown} reference group${shown === 1 ? '' : 's'}`;
    if (empty) empty.hidden = shown !== 0;
  };
  input.addEventListener('input', apply);
  filters.forEach(button => button.addEventListener('click', () => {
    scope = button.dataset.apiFilter || 'all';
    filters.forEach(x => x.classList.toggle('active', x === button));
    apply();
  }));
})();
