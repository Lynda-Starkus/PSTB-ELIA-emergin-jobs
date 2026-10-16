(function(){
  'use strict';
  const $=s=>document.querySelector(s), O=window.ELIA_OUTCOMES;
  if(!O||!window.ELIA_NATIVE)return;
  const themeKey='elia-native-theme-v3';
  let mode='original';
  try{mode=localStorage.getItem(themeKey)||mode;}catch(_e){}
  function setTheme(next){
    mode=['original','dark','light'].includes(next)?next:'original';
    document.documentElement.dataset.theme=mode;
    $('#theme-toggle').textContent='Thème : '+({original:'Original',dark:'Sombre',light:'Clair'})[mode];
    $('#theme-toggle').setAttribute('aria-label','Thème '+mode+'. Cliquer pour changer.');
    try{localStorage.setItem(themeKey,mode);}catch(_e){}
    window.dispatchEvent(new CustomEvent('elia:themechange',{detail:{theme:mode}}));
  }
  $('#theme-toggle').addEventListener('click',()=>setTheme(mode==='original'?'light':mode==='light'?'dark':'original'));
  window.ELIA_THEME={get:()=>mode,set:setTheme};setTheme(mode);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ids=rows=>rows.map(t=>t.id);
  const select=(rows,sort='roles')=>window.ELIA_NATIVE.select(ids(rows),sort);
  function search(value){$('#q').value=value;$('#q').dispatchEvent(new Event('input',{bubbles:true}));}
  const chapter=(duration,target,label,heading,body='',source='',prepare,action)=>
    ({duration,target,label,heading,body,source,tags:[],prepare,action});
  const chapters=[
    chapter(9,'.sc-title','Objectif','+1 million d’offres en France.',
      'Quels métiers émergent avec l’IA ?','Étude France · Extrait : 907 889 intitulés.'),
    chapter(9,'.step[data-s="1"]','Signaux précoces','De nouveaux rôles apparaissent.',
      'On suit leur diffusion dans les annonces.','HN · Archive internationale, 2011–2026.'),
    chapter(10,'.step[data-s="2"]','Déploiement','FDE : 21 → 87 mentions.',
      '+314 % sur deux années comparées.','HN international · Oct. 2025–sept. 2026 / année précédente.'),
    chapter(8,'#accel','Familles en essor','Les agents IA gagnent du terrain.',
      'Le graphique suit les familles de métiers.','HN international · Parts des annonces, lissées sur 3 mois.'),
    chapter(11,'#france','France','Ingénieur IA : 537 résultats.',
      '425 publiés depuis 31 jours ou moins.','France Travail · 4 oct. 2026 · Mots-clés, chevauchements possibles.'),
    chapter(8,'#france','Offres récentes','On regarde les offres récentes.',
      'Le filtre passe à 31 jours.','France Travail · Collecte du 4 octobre 2026.',null,
      ()=>click('#fr-metric button[data-m="count_31j"]')),
    chapter(9,'#france','Employeurs','Wavestone : 11 · Onepoint : 10.',
      'Des offres d’ingénieur IA publiées.','Adzuna France · Requête « AI engineer » · 4 octobre 2026.',
      ()=>$('#fr-metric button[data-m="count"]').click()),
    chapter(9,'#carte','Territoires','Île-de-France : 582 résultats.',
      'Auvergne-Rhône-Alpes : 111.','France Travail · Requêtes sur 10 intitulés IA.'),
    chapter(11,'#decouverte','Appellations','Développeur IA : 23 annonces.',
      '11 variantes d’intitulé.','France · FT, CSP, Adzuna · Groupement automatique.',null,
      ()=>click('#cands .cand[data-group="développeur ia"]',true)),
    chapter(9,'#decouverte','Fiches à construire','Tech Lead IA : 11 annonces.',
      'Agents, RAG et LLMOps dans les titres.','France · Exemples bruts · Regroupement à valider.',null,
      ()=>click('#cands .cand[data-group="tech ia"]',true)),
    chapter(9,'#decouverte','Entrée dans le métier','Développeur IA junior · Freelance.',
      'Un intitulé réellement publié.','France Travail · Exemple du 29 septembre 2026.'),
    chapter(12,'#intitules','Cinq rôles en France','5 rôles IA recrutés en France.',
      '537 · 32 · 22 · 11 · 9 résultats.','France Travail · Sélection ELIA · 4 octobre 2026.',
      ()=>select(O.selectedFrance5)),
    chapter(13,'#intitules','Top 5 bullish','FDE +314 % · Agents +138 %.',
      'Les 5 plus fortes hausses retenues.','HN international · 12 mois comparés · ≥ 24 mentions / 24 mois.',
      ()=>select(O.bullish5,'growth')),
    chapter(13,'#intitules','Top 5 bearish','Sécurité IA : 12 → 4 mentions.',
      '5 intitulés en recul dans l’archive.','HN international · 12 mois comparés · Petits effectifs.',
      ()=>select(O.bearish5,'growth')),
    chapter(11,'#intitules','Signaux absents','4 intitulés absents depuis 12 mois.',
      'Disparition du métier non établie.','HN international · 1–2 mentions l’année précédente.',
      ()=>select(O.absent12Months)),
    chapter(10,'#intitules','France / international','FDE : 87 mentions HN, 9 résultats FR.',
      '5 rôles à surveiller ici.','HN / France Travail · Deux périmètres différents.',
      ()=>select(O.international5.slice().sort((a,b)=>b.ftCount-a.ftCount))),
    chapter(11,'#intitules','Fiche métier','Ingénieur IA : ouvrir la fiche.',
      'Alias, compétences et sources.','Référentiel ELIA · Fiche à actualiser.',
      ()=>{window.ELIA_NATIVE.select(null);search('Ingénieur IA');},
      ()=>click('.cardt[data-title="ai_engineer"]')),
    chapter(8,'#intitules','Thème','Original, clair ou sombre.',
      'Le choix est mémorisé.','',()=>window.ELIA_NATIVE.select(null),
      ()=>{document.body.classList.add('tour-show-theme');click('#theme-toggle');}),
    chapter(9,'#methode','Résultats','Repérer les rôles. Suivre leur diffusion.',
      'Puis valider les fiches métier.','France : collecte du 4 oct. 2026 · Archive HN internationale.')
  ];
  const duration=chapters.reduce((n,c)=>n+c.duration,0);
  const clock=n=>Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0');
  const state={running:false,paused:false,index:0,total:chapters.length,duration,elapsed:0,complete:false};
  let raf=0,lastTime=0,stepElapsed=0,scrollElapsed=0,scrollStart=0,scrollEnd=0,savedTheme=mode;
  let timers=[],marked=null;
  const later=(fn,ms)=>timers.push(setTimeout(fn,ms));
  function clearTimers(){timers.forEach(clearTimeout);timers=[];}
  function closeDrawer(){const button=$('#drawer .close');if(button&&$('#drawer').classList.contains('on'))button.click();document.body.classList.remove('tour-drawer');}
  function click(selector,expand){
    const target=$(selector);if(!target||!state.running)return;
    if(expand&&target.classList.contains('open'))return;
    const r=target.getBoundingClientRect(),cursor=$('#tour-cursor');
    cursor.classList.add('active');cursor.style.left=(r.x+r.width*.5)+'px';cursor.style.top=(r.y+r.height*.5)+'px';
    if(marked)marked.classList.remove('tour-target');marked=target;target.classList.add('tour-target');
    later(()=>{
      if(!state.running)return;
      cursor.classList.remove('click');void cursor.offsetWidth;cursor.classList.add('click');target.click();
      document.body.classList.toggle('tour-drawer',$('#drawer').classList.contains('on'));
      later(()=>{target.classList.remove('tour-target');cursor.classList.remove('active');},1400);
    },reduced?0:750);
  }
  const elapsedBefore=index=>chapters.slice(0,index).reduce((n,c)=>n+c.duration,0);
  function enter(index){
    clearTimers();closeDrawer();document.body.classList.remove('tour-show-theme');
    if(marked)marked.classList.remove('tour-target');$('#tour-cursor').classList.remove('active');
    state.index=Math.max(0,Math.min(chapters.length-1,index));stepElapsed=0;scrollElapsed=0;
    const c=chapters[state.index];if(c.prepare)c.prepare();
    const target=$(c.target);scrollStart=window.scrollY;const r=target.getBoundingClientRect();
    scrollEnd=Math.max(0,Math.min(document.documentElement.scrollHeight-innerHeight,
      scrollStart+r.top+(target.classList.contains('step')?(r.height-innerHeight)/2:-35)));
    document.body.classList.toggle('tour-on-paper',target.classList.contains('light'));
    const cap=$('#tour-caption');cap.classList.remove('visible');
    later(()=>{$('#tour-heading').textContent=c.heading;$('#tour-body').textContent=c.body;$('#tour-source').textContent=c.source;cap.classList.add('visible');},reduced?0:200);
    if(c.action)later(c.action,2600);
  }
  function tick(now){
    if(!state.running)return;
    const delta=Math.max(0,Math.min(100,now-lastTime));lastTime=now;
    if(!state.paused){
      stepElapsed+=delta;scrollElapsed+=delta;
      const p=reduced?1:Math.min(1,scrollElapsed/1800),e=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
      window.scrollTo({top:scrollStart+(scrollEnd-scrollStart)*e,behavior:'instant'});
      state.elapsed=elapsedBefore(state.index)+stepElapsed/1000;
      $('#tour-time').textContent=clock(state.elapsed)+' / '+clock(duration);
      if(stepElapsed>=chapters[state.index].duration*1000){
        if(state.index<chapters.length-1)enter(state.index+1);
        else{state.running=false;state.complete=true;state.elapsed=duration;$('#tour-pause').textContent='Rejouer';return;}
      }
    }
    raf=requestAnimationFrame(tick);
  }
  function start(options={}){
    stop(false);savedTheme=mode;window.ELIA_NATIVE.start();
    if(options.theme)setTheme(options.theme);
    window.ELIA_NATIVE.select(null);closeDrawer();
    document.querySelectorAll('#cands .cand.open').forEach(c=>c.classList.remove('open'));
    $('#fr-metric button[data-m="count"]').click();
    Object.assign(state,{running:true,paused:false,index:0,elapsed:0,complete:false});
    document.body.classList.add('tour-active');document.body.classList.toggle('tour-recording',!!options.recording);
    $('#tour-overlay').hidden=false;$('#tour-pause').textContent='Pause';
    lastTime=performance.now();enter(0);raf=requestAnimationFrame(tick);
  }
  function stop(restore=true){
    cancelAnimationFrame(raf);clearTimers();if(marked)marked.classList.remove('tour-target');
    state.running=false;state.paused=false;$('#tour-overlay').hidden=true;
    document.body.classList.remove('tour-active','tour-recording','tour-drawer','tour-on-paper','tour-show-theme');
    closeDrawer();window.ELIA_NATIVE.restore();if(restore)setTheme(savedTheme);
  }
  function pause(){if(state.complete){start();return;}state.paused=!state.paused;$('#tour-pause').textContent=state.paused?'Reprendre':'Pause';}
  function seek(index){if(!state.running)return;enter(index);state.elapsed=elapsedBefore(state.index);}
  $('#tour-launch').addEventListener('click',()=>start());$('#tour-pause').addEventListener('click',pause);
  $('#tour-stop').addEventListener('click',()=>stop());$('#tour-prev').addEventListener('click',()=>seek(state.index-1));$('#tour-next').addEventListener('click',()=>seek(state.index+1));
  document.addEventListener('keydown',event=>{
    if(!document.body.classList.contains('tour-active')||/INPUT|SELECT|TEXTAREA/.test(event.target.tagName))return;
    if(event.key==='Escape')stop();if(event.code==='Space'){event.preventDefault();pause();}
    if(event.key==='ArrowRight'){event.preventDefault();seek(state.index+1);}if(event.key==='ArrowLeft'){event.preventDefault();seek(state.index-1);}
  });
  window.ELIA_TOUR={start,stop,pause,seek,state,chapters:chapters.map(({prepare,action,...c})=>c)};
})();
