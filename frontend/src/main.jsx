import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function App() {
  const [mode, setMode] = useState('trending');
  const [favoriteGame, setFavoriteGame] = useState('Portal 2');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function loadRecommendations() {
    setError('');
    try {
      const response = await fetch('/api/recommendations', {
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
      <p className="eyebrow">GameSense foundation</p>
      <h1>Discover your next Steam game with explainable recommendation modes.</h1>
      <p>This first slice proves the local app, API, deployment, and observability story for the M10 walkthrough.</p>
    </section>
    <section className="panel">
      <label>Favorite game<input value={favoriteGame} onChange={event => setFavoriteGame(event.target.value)} /></label>
      <label>Recommendation mode<select value={mode} onChange={event => setMode(event.target.value)}>
        <option value="trending">Trending</option><option value="similar">Similar</option><option value="cozy">Cozy</option><option value="competitive">Competitive</option>
      </select></label>
      <button onClick={loadRecommendations}>Get recommendations</button>
      {error && <p className="error">{error}</p>}
      {result && <div className="cards">{result.recommendations.map(game => <article key={game}>{game}</article>)}<p>{result.explanation}</p></div>}
    </section>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
