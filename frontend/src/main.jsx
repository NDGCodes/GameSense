import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import GameArtwork from './GameArtwork';
import './styles.css';

const API = import.meta.env.VITE_API_BASE_URL || '';
const PAGE_SIZE = 30;
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function Icon({ name }) {
  const shapes = {
    search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>,
    grid: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>,
    arrow: <path d="M3 12h18m-7-7 7 7-7 7"/>,
    back: <path d="M21 12H3m7 7-7-7 7-7"/>,
    close: <path d="M5 5 19 19M19 5 5 19"/>,
  };
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

function Card({ game, onSelect, poster = false }) {
  return <button className="game-card" type="button" onClick={() => onSelect(game)} aria-label={`Explore ${game.title} and similar games`}>
    <GameArtwork game={game} preferPortrait={poster}/><span className="card-shade"/><span className="card-copy"><strong>{game.title}</strong><small>{game.genres?.slice(0,2).join(' / ')}</small></span><span className="card-arrow"><Icon name="arrow"/></span>
  </button>;
}

function App() {
  const [games,setGames]=useState([]), [query,setQuery]=useState(''), [search,setSearch]=useState(''), [genre,setGenre]=useState('All games');
  const [catalogState,setCatalogState]=useState('loading'), [hasMore,setHasMore]=useState(true), [catalogError,setCatalogError]=useState(''), [retryToken,setRetryToken]=useState(0);
  const [selected,setSelected]=useState(null), [result,setResult]=useState(null), [resultState,setResultState]=useState('idle'), [resultError,setResultError]=useState('');
  const headingRef=useRef(null), searchRef=useRef(null), catalogController=useRef(null), resultController=useRef(null), catalogId=useRef(0), resultId=useRef(0), cache=useRef(new Map());

  useEffect(()=>{const timer=setTimeout(()=>setSearch(query.trim()),250);return ()=>clearTimeout(timer)},[query]);
  useEffect(()=>{
    const id=++catalogId.current; catalogController.current?.abort();
    const controller=new AbortController(); catalogController.current=controller;
    setGames([]);setHasMore(true);setCatalogState('loading');setCatalogError('');
    const params=new URLSearchParams({limit:String(PAGE_SIZE),offset:'0'});
    if(search)params.set('q',search);
    fetch(`${API}/api/games?${params}`,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error(`Catalog request failed (${r.status})`);return r.json()}).then(data=>{if(id===catalogId.current){setGames(data);setHasMore(data.length===PAGE_SIZE);setCatalogState('ready')}}).catch(e=>{if(id===catalogId.current&&e.name!=='AbortError'){setCatalogError(e.message);setCatalogState('error')}});
    return ()=>controller.abort();
  },[search,retryToken]);
  useEffect(()=>()=>{catalogController.current?.abort();resultController.current?.abort()},[]);

  async function loadMore(){
    if(!['ready','more-error'].includes(catalogState)||!hasMore)return;
    const id=catalogId.current, controller=new AbortController();catalogController.current=controller;setCatalogState('more');
    const params=new URLSearchParams({limit:String(PAGE_SIZE),offset:String(games.length)});if(search)params.set('q',search);
    try{const r=await fetch(`${API}/api/games?${params}`,{signal:controller.signal});if(!r.ok)throw Error(`Catalog request failed (${r.status})`);const data=await r.json();if(id===catalogId.current){setGames(old=>[...old,...data]);setHasMore(data.length===PAGE_SIZE);setCatalogState('ready')}}
    catch(e){if(id===catalogId.current&&e.name!=='AbortError'){setCatalogError(e.message);setCatalogState('more-error')}}
  }
  function backToCatalog(){
    ++resultId.current;resultController.current?.abort();setSelected(null);setResultState('idle');
    requestAnimationFrame(()=>{window.scrollTo({top:0,behavior:'instant'});searchRef.current?.focus({preventScroll:true})});
  }
  async function selectGame(game,retry=false){
    if(!game)return;
    const id=++resultId.current;resultController.current?.abort();setSelected(game);setResultError('');
    const cached=!retry&&cache.current.get(game.slug);setResult(cached||null);setResultState(cached?'ready':'loading');
    window.scrollTo({top:0,behavior:reducedMotion()?'instant':'smooth'});
    requestAnimationFrame(()=>headingRef.current?.focus({preventScroll:true}));
    if(cached)return;
    const controller=new AbortController();resultController.current=controller;
    try{const r=await fetch(`${API}/api/recommendations`,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({mode:'similar',favorite_game:game.slug,limit:9})});if(!r.ok)throw Error(`Recommendations request failed (${r.status})`);const data=await r.json();if(id===resultId.current){cache.current.set(game.slug,data);setResult(data);setResultState('ready')}}
    catch(e){if(id===resultId.current&&e.name!=='AbortError'){setResultError(e.message);setResultState('error')}}
  }
  const genres=['All games',...new Set(games.flatMap(game=>game.genres||[]))].slice(0,7);
  const visible=genre==='All games'?games:games.filter(game=>game.genres?.includes(genre));
  const matches=(result?.recommendations||[]).filter(game=>game.slug!==selected?.slug);
  const groups=[matches.slice(0,3),matches.slice(3,6),matches.slice(6,9)].filter(group=>group.length);
  return <div className="app-shell">
    <div className="workspace"><header className="topbar"><button className="brand" type="button" onClick={backToCatalog}>GAMESENSE<span>.</span></button><nav aria-label="Main navigation"><button className={!selected?'nav-active':''} type="button" onClick={backToCatalog}>LIBRARY</button>{selected&&<span className="nav-current" aria-current="page">GAME DETAILS</span>}</nav><label className="search-box"><Icon name="search"/><span className="sr-only">Search the game catalog</span><input id="game-search" name="game-search" ref={searchRef} type="search" placeholder="Search games" value={query} onChange={e=>{setQuery(e.target.value);setGenre('All games');if(selected)backToCatalog()}}/>{query&&<button type="button" onClick={()=>{setQuery('');setGenre('All games')}} aria-label="Clear search"><Icon name="close"/></button>}</label></header>
      <div className="layout"><aside className="sidebar" aria-label="Library filters"><p className="sidebar-heading">BROWSE GAMES</p><div className="sidebar-group">{genres.map(value=><button key={value} type="button" className={genre===value?'sidebar-active':''} onClick={()=>{setGenre(value);if(selected)backToCatalog()}}>{value}</button>)}</div><div className="sidebar-bottom"><span className="sidebar-mark">G/S</span><p>Find your next game.</p><small>Choose a title to see games with similar catalog signals.</small></div></aside>
      <main className="content" id="main-content">{!selected?<section className="catalog-view" aria-label="Game catalog"><div className="catalog-intro"><span className="overline">THE GAMESENSE LIBRARY</span><h1>Explore the catalog<span>.</span></h1><p>Pick a game to discover similar titles.</p></div><div className="catalog-toolbar"><div><span className="overline">ALL GAMES</span><h2>{search?`Results for “${search}”`:genre==='All games'?'Browse games':genre}</h2></div><label className="mobile-genres"><span className="sr-only">Filter by genre</span><select id="game-genre" name="game-genre" value={genre} onChange={e=>setGenre(e.target.value)}>{genres.map(value=><option key={value}>{value}</option>)}</select></label></div>
        {catalogState==='loading'&&<p className="feedback" role="status">Loading games…</p>}
        {catalogState==='error'&&<div className="feedback error" role="alert">Could not load the catalog. {catalogError}<button type="button" onClick={()=>setRetryToken(n=>n+1)}>Try again</button></div>}
        {!['loading','error'].includes(catalogState)&&!visible.length&&<p className="feedback">No games found here. Try a different title or filter.</p>}
        <div className="poster-grid">{visible.map(game=><Card key={game.slug} game={game} onSelect={selectGame} poster/>)}</div>
        {hasMore&&catalogState!=='error'&&<div className="paging"><span>{games.length} games loaded{genre!=='All games'?' · filter applies to loaded games':''}</span><button type="button" onClick={loadMore} disabled={catalogState==='more'}>{catalogState==='more'?'Loading…':'Load more games'} <Icon name="arrow"/></button>{catalogState==='more-error'&&<small role="alert">{catalogError} Try again.</small>}</div>}
      </section>:<div className="detail-view" key={selected.slug}><button type="button" className="back-link" onClick={backToCatalog}><Icon name="back"/> All games</button><section className="detail-hero" aria-label={`${selected.title} overview`}><div className="detail-art"><GameArtwork game={selected}/></div><div className="detail-shade"/><div className="detail-copy"><span className="overline">SELECTED GAME</span><h1 ref={headingRef} tabIndex="-1">{selected.title}</h1>{selected.shortDescription&&<p>{selected.shortDescription}</p>}<div className="hero-tags">{selected.genres?.slice(0,3).map(value=><span key={value}>{value}</span>)}</div></div></section><div className="detail-meta"><div><span>GAME</span><strong>{selected.title}</strong></div><div><span>GENRES</span><strong>{selected.genres?.slice(0,2).join(' · ')||'Not listed'}</strong></div><div><span>CATALOG SOURCE</span><strong>{selected.source}</strong></div></div>
        <section className="recommendations-section" aria-live="polite"><div className="section-head"><div><span className="overline">BASED ON YOUR SELECTION</span><h2>Similar to {selected.title}</h2></div></div>{resultState==='loading'&&<><p className="feedback" role="status">Finding similar games…</p><div className="poster-grid loading-grid" aria-hidden="true"><span/><span/><span/></div></>}{resultState==='error'&&<div className="feedback error" role="alert"><p>{resultError}</p><button type="button" onClick={()=>selectGame(selected,true)}>Try again</button></div>}{resultState==='ready'&&!matches.length&&<p className="feedback">No similar games were returned for this title.</p>}{resultState==='ready'&&groups.map((group,index)=><div className="recommendation-group" key={index}><div className="group-heading"><h3>{index===0?'Closest matches':'More similar games'}</h3><span>{String(index+1).padStart(2,'0')} / {String(groups.length).padStart(2,'0')}</span></div><div className="recommendation-grid">{group.map(game=><Card key={`${game.source}:${game.slug}`} game={game} onSelect={selectGame}/>)}</div></div>)}{result&&<details className="source-details"><summary>Recommendation source and artwork</summary><p>{result.explanation}</p><p>{result.disclosure||result.fixtureNotice}</p><p>Algorithm: {result.algorithm} · Version: {result.version} · Data snapshot: {result.dataSnapshot}</p><p>Artwork loads from Steam when available. Publisher artwork rights are separate from the catalog dataset license; missing artwork uses a title placeholder.</p></details>}</section></div>}</main></div></div></div>;
}
createRoot(document.getElementById('root')).render(<App/>);
