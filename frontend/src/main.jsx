import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import GameArtwork from './GameArtwork';
import './styles.css';

const API = import.meta.env.VITE_API_BASE_URL || '';
const picks = ['Hollow Knight', 'Celeste', 'Stardew Valley', 'Portal 2', 'DOOM', 'Terraria', 'Cuphead', 'Dead Cells', 'Undertale', 'Subnautica', 'BioShock Infinite', 'The Binding of Isaac: Rebirth', 'Slay the Spire', 'Risk of Rain 2'];
function Icon({ name }) {
  const shape = { search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>, grid: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>, spark: <path d="m12 2 2.2 7.8L22 12l-7.8 2.2L12 22l-2.2-7.8L2 12l7.8-2.2L12 2Z"/>, arrow: <path d="M3 12h18m-7-7 7 7-7 7"/>, close: <path d="M5 5 19 19M19 5 5 19"/> };
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shape[name]}</svg>;
}
function Card({ game, onSelect, active }) {
  return <button className={`game-card ${active ? 'active' : ''}`} type="button" onClick={() => onSelect(game)} aria-label={`Find games similar to ${game.title}`}>
    <GameArtwork game={game}/><span className="card-shade"/><span className="card-copy"><strong>{game.title}</strong><small>{game.genres?.slice(0,2).join(' / ')}</small></span><span className="card-arrow"><Icon name="arrow"/></span>
  </button>;
}
function App() {
  const [catalog,setCatalog]=useState([]), [featured,setFeatured]=useState([]), [query,setQuery]=useState(''), [matches,setMatches]=useState(null), [genre,setGenre]=useState('All games'), [limit,setLimit]=useState(24);
  const [catalogState,setCatalogState]=useState('loading'), [searchState,setSearchState]=useState('idle'), [selected,setSelected]=useState(null), [result,setResult]=useState(null), [recommendationState,setRecommendationState]=useState('idle'), [error,setError]=useState('');
  const resultsRef=useRef(null), requestId=useRef(0);
  useEffect(()=>{
    const controller=new AbortController();
    fetch(`${API}/api/games?limit=500`,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error(`Catalog request failed (${r.status})`);return r.json()}).then(g=>{setCatalog(g);setCatalogState('ready')}).catch(e=>{if(e.name!=='AbortError'){setError(e.message);setCatalogState('error')}});
    Promise.all(picks.map(async title=>{try{const r=await fetch(`${API}/api/games?q=${encodeURIComponent(title)}&limit=20`,{signal:controller.signal});if(!r.ok)return null;return (await r.json()).find(g=>g.title.toLowerCase()===title.toLowerCase())||null}catch{return null}})).then(g=>{if(!controller.signal.aborted)setFeatured(g.filter(Boolean))});
    return ()=>controller.abort();
  },[]);
  useEffect(()=>{
    if(!query.trim()){setMatches(null);setSearchState('idle');return}
    const controller=new AbortController();setMatches(null);setSearchState('loading');
    const timer=setTimeout(()=>fetch(`${API}/api/games?q=${encodeURIComponent(query.trim())}&limit=1000`,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error('Search unavailable');return r.json()}).then(g=>{setMatches(g);setSearchState('ready')}).catch(e=>{if(e.name!=='AbortError'){setMatches([]);setSearchState('error')}}),250);
    return ()=>{clearTimeout(timer);controller.abort()};
  },[query]);
  async function selectGame(game){
    const id=++requestId.current;setSelected(game);setResult(null);setError('');setRecommendationState('loading');
    requestAnimationFrame(()=>resultsRef.current?.scrollIntoView({behavior:'smooth',block:'start'}));
    try{const response=await fetch(`${API}/api/recommendations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'similar',favorite_game:game.slug})});if(!response.ok)throw Error(`Recommendations request failed (${response.status})`);const data=await response.json();if(id===requestId.current){setResult(data);setRecommendationState('ready')}}catch(e){if(id===requestId.current){setError(e.message);setRecommendationState('error')}}
  }
  const genres=['All games',...new Set(catalog.flatMap(g=>g.genres||[]))].slice(0,6), featuredGames=featured.length?featured:catalog.slice(0,5), hero=featuredGames[0];
  const pool=query.trim()?(matches||[]):catalog, filtered=genre==='All games'?pool:pool.filter(g=>g.genres?.includes(genre));
  const ordered=query.trim()||genre!=='All games'?filtered:[...featuredGames,...catalog.filter(g=>!featuredGames.some(f=>f.slug===g.slug))];
  return <div className="app-shell">
    <aside className="rail" aria-label="Quick game picks"><a className="rail-logo" href="#top" aria-label="GameSense home">G<span>/</span>S</a><a className="rail-icon selected" href="#browse" aria-label="Browse games"><Icon name="grid"/></a><a className="rail-icon" href="#recommendations" aria-label="Recommendations"><Icon name="spark"/></a><div className="rail-covers">{featuredGames.slice(0,4).map(g=><button type="button" key={g.slug} onClick={()=>selectGame(g)} aria-label={`Find games similar to ${g.title}`} title={g.title}><GameArtwork game={g}/></button>)}</div></aside>
    <div className="workspace" id="top"><header className="topbar"><a className="brand" href="#top">GAMESENSE<span>.</span></a><nav aria-label="Main navigation"><a className="nav-active" href="#browse">DISCOVER</a><a href="#recommendations">FOR YOU</a></nav><label className="search-box"><Icon name="search"/><span className="sr-only">Search the full game catalog</span><input type="search" placeholder="Search games" value={query} onChange={e=>{setQuery(e.target.value);setGenre('All games');setLimit(24)}}/>{query&&<button type="button" onClick={()=>setQuery('')} aria-label="Clear search"><Icon name="close"/></button>}</label></header>
      <div className="layout"><aside className="sidebar" aria-label="Browse filters"><div className="sidebar-group"><p className="sidebar-heading">IN THIS VIEW</p>{genres.map(g=><button type="button" key={g} className={genre===g?'sidebar-active':''} onClick={()=>{setGenre(g);setLimit(24)}}>{g}</button>)}</div><div className="sidebar-bottom"><div className="sidebar-emblem"><Icon name="spark"/></div><p>Find more of what you love.</p><small>Select any game to see similar picks from the catalog.</small></div></aside>
      <main className="content">{!query.trim()&&hero&&<section className="feature" aria-label="Featured game"><div className="feature-image"><GameArtwork game={hero}/></div><div className="feature-shade"/><div className="feature-content"><span className="overline">FEATURED GAME</span><h1>{hero.title}</h1><p>{hero.shortDescription}</p><button type="button" onClick={()=>selectGame(hero)}>Find similar games <Icon name="arrow"/></button></div></section>}
      <section id="browse" className="browse-section"><div className="section-head"><div><span className="overline">EXPLORE THE CATALOG</span><h2>{query.trim()?`Search results for “${query.trim()}”`:genre==='All games'?'Games to explore':genre}</h2></div><div className="browse-controls"><label className="mobile-genres"><span className="sr-only">Filter games by genre</span><select value={genre} onChange={e=>{setGenre(e.target.value);setLimit(24)}}>{genres.map(g=><option key={g}>{g}</option>)}</select></label><span className="section-count">{searchState==='loading'&&query.trim()?'Searching…':query.trim()?`${filtered.length} returned`:genre==='All games'?'Browse the catalog':`${filtered.length} in this view`}</span></div></div>
      {catalogState==='loading'&&<p className="feedback">Loading games…</p>}{catalogState==='error'&&<p className="feedback error" role="alert">Could not load the catalog. {error}</p>}{searchState==='error'&&<p className="feedback error" role="alert">Search is unavailable. Try again shortly.</p>}{searchState==='ready'&&query.trim()&&!filtered.length&&<p className="feedback">No games found. Try a different title.</p>}
      <div className="poster-grid">{ordered.slice(0,limit).map(g=><Card key={g.slug} game={g} onSelect={selectGame} active={selected?.slug===g.slug}/>)}</div>{filtered.length>limit&&<button className="load-more" type="button" onClick={()=>setLimit(n=>n+24)}>Show more games</button>}</section>
      <section id="recommendations" className="recommendations-section" ref={resultsRef} aria-live="polite"><div className="section-head"><div><span className="overline">YOUR NEXT GAME</span><h2>{selected?`More like ${selected.title}`:'Select a game to get recommendations'}</h2></div></div>{recommendationState==='idle'&&<p className="feedback">Choose a game above. Similar picks will appear here.</p>}{recommendationState==='loading'&&<p className="feedback" role="status">Finding games similar to {selected?.title}…</p>}{recommendationState==='error'&&<div className="feedback error" role="alert"><p>{error}</p><button type="button" onClick={()=>selectGame(selected)}>Try again</button></div>}
      {result&&<><p className="result-explanation">{result.explanation}</p><div className="poster-grid">{result.recommendations.map(g=><Card key={`${g.source}:${g.slug}`} game={g} onSelect={selectGame}/>)}</div>{!result.recommendations.length&&<p className="feedback">No similar games were returned for this selection.</p>}<details className="source-details"><summary>Recommendation source and artwork</summary><p>{result.disclosure||result.fixtureNotice}</p><p>Algorithm: {result.algorithm} · Version: {result.version} · Data snapshot: {result.dataSnapshot}</p><p>Artwork loads from Steam when available. Publisher artwork rights are separate from the catalog dataset license; missing covers use a title placeholder.</p></details></>}</section>
      </main></div></div></div>;
}
createRoot(document.getElementById('root')).render(<App/>);
