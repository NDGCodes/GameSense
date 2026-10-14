import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const modes = [
  { value: 'trending', label: 'Trending' },
  { value: 'similar', label: 'Similar' },
  { value: 'cozy', label: 'Cozy' },
  { value: 'competitive', label: 'Competitive' },
];

function App() {
  const [mode, setMode] = useState('trending');
  const [favoriteGame, setFavoriteGame] = useState('Cozy Comet Cafe');
  const [result, setResult] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [catalogStatus, setCatalogStatus] = useState('not loaded');
  const [health, setHealth] = useState('checking');
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then(response => (response.ok ? response.json() : Promise.reject(new Error(`API returned ${response.status}`))))
      .then(() => setHealth('ok'))
      .catch(() => setHealth('unavailable'));
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/games?limit=500`)
      .then(response => (response.ok ? response.json() : Promise.reject(new Error(`API returned ${response.status}`))))
      .then(games => {
        setCatalog(games);
        setCatalogStatus(`${games.length} catalog options loaded`);
        if (games.length > 0 && favoriteGame === 'Cozy Comet Cafe') {
          setFavoriteGame(games[0].slug);
        }
      })
      .catch(() => setCatalogStatus('catalog unavailable'));
  }, []);

  async function loadRecommendations() {
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/recommendations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, favorite_game: favoriteGame }),
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setResult(await response.json());
    } catch (err) {
      setError(err.message);
    }
  }

  return <main>
    <section className="hero">
      <p className="eyebrow">GameSense app-infrastructure foundation</p>
      <h1>Discover your next Steam-style game with explainable demo recommendation modes.</h1>
      <p>This slice validates the local app, database migration, API, deployment, and observability path before the later ML phase.</p>
      <p className={`status status-${health}`}>API status: {health}</p>
    </section>
    <section className="panel">
      <label>Favorite game{catalog.length > 0 ? <select value={favoriteGame} onChange={event => setFavoriteGame(event.target.value)}>
          {catalog.map(game => <option key={game.slug} value={game.slug}>{game.title} ({game.slug})</option>)}
        </select> : <input value={favoriteGame} onChange={event => setFavoriteGame(event.target.value)} />}
      </label>
      <p className="catalog-status">{catalogStatus}. In content bundle mode these titles come from the same returned snapshot used by the backend recommender; fixture mode remains labeled as demo data.</p>
      <label>Recommendation mode<select value={mode} onChange={event => setMode(event.target.value)}>
        {modes.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select></label>
      <button onClick={loadRecommendations}>Get recommendations</button>
      {error && <p className="error">{error}</p>}
      {result && <div className="results">
        <p className="notice">{result.disclosure || result.fixtureNotice}</p>
        <div className="metadata" aria-label="Recommendation source metadata">
          <span>Algorithm: {result.algorithm || 'demo-fixture-rules'}</span>
          <span>Version: {result.version || 'legacy'}</span>
          <span>Data snapshot: {result.dataSnapshot || 'demo-database-fixtures'}</span>
        </div>
        <p>{result.explanation}</p>
        {result.recommendations.length === 0 && <p className="notice">No recommendations were returned for this selection.</p>}
        <div className="cards">
          {result.recommendations.map(game => <article key={game.slug}>
            <div className="card-header"><h2>{game.title}</h2><span>{game.source}</span></div>
            <p>{game.shortDescription}</p>
            <p className="genres">{game.genres.join(' · ')}</p>
            <p className="reason"><strong>Why this appears:</strong> {game.reason}</p>
          </article>)}
        </div>
      </div>}
    </section>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
