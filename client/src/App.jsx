// frontend/src/App.js - MODIFIED AGAIN FOR DEBUGGING JSON PARSING
import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [handle, setHandle] = useState('');
  const [numRecommendations, setNumRecommendations] = useState(10);
  const [goalTags, setGoalTags] = useState('');
  const [userData, setUserData] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_URL = 'http://localhost:8000';

  const fetchRecommendations = async () => {
    setLoading(true);
    setError(null);
    setUserData(null);
    setRecommendations([]);

    try {
      const url = new URL(`${API_URL}/recommend/${handle}`);
      url.searchParams.append('num_recommendations', numRecommendations);
      if (goalTags) {
        url.searchParams.append('goal_tags', goalTags);
      }

      const response = await fetch(url.toString());

      // --- NEW DEBUGGING CODE ---
      const rawResponseText = await response.text();
      console.log("Raw Response Text from Backend:", rawResponseText);

      if (!response.ok) {
        // If response is not OK, use the raw text for error detail
        throw new Error(`HTTP error! Status: ${response.status}. Response: ${rawResponseText}`);
      }

      let data;
      try {
          data = JSON.parse(rawResponseText); // Try parsing the raw text
          console.log("Parsed JSON Data:", data);
      } catch (jsonParseError) {
          console.error("JSON Parsing Error (from raw text):", jsonParseError);
          console.error("Problematic Raw Text:", rawResponseText);
          throw new Error(`Failed to parse response from server as JSON. Check console for "Problematic Raw Text".`);
      }
      // --- END NEW DEBUGGING CODE ---


      setUserData({
        handle: handle,
        rating: data.user_rating,
        solvedCount: data.solved_count,
        unsolvedAttemptsCount: data.unsolved_attempts_count,
        preferredTags: data.preferred_tags,
        struggledTags: data.struggled_tags,
        tag_success_rates: data.tag_success_rates,
      });
      setRecommendations(data.recommendations);
    } catch (e) {
      console.error("Error in fetchRecommendations:", e);
      setError(e.message || "Failed to fetch recommendations. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ... (rest of your App.js code is unchanged) ...

  return (
    <div className="App">
      <header className="App-header">
        <h1>Codeforces Problem Recommender</h1>
        <p>Get personalized problem recommendations to boost your competitive programming skills!</p>
      </header>
      <div className="input-section">
        <input
          type="text"
          placeholder="Enter Codeforces Handle (e.g., tourist)"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
        />
        <input
          type="number"
          placeholder="Num Recs"
          value={numRecommendations}
          onChange={(e) => setNumRecommendations(e.target.value)}
          min="1"
          max="20"
        />
        <input
          type="text"
          placeholder="Goal Tags (e.g., dp,graphs)"
          value={goalTags}
          onChange={(e) => setGoalTags(e.target.value)}
        />
        <button onClick={fetchRecommendations} disabled={loading || !handle}>
          {loading ? 'Loading...' : 'Get Recommendations'}
        </button>
      </div>

      {error && <p className="error-message">{error}</p>}

      {userData && (
        <div className="user-stats">
          <h2>📊 User Stats for {userData.handle}</h2>
          <p><strong>Rating:</strong> {userData.rating || 'N/A'}</p>
          <p><strong>Problems Solved:</strong> {userData.solvedCount}</p>
          <p><strong>Problems Attempted (Unsolved):</strong> {userData.unsolvedAttemptsCount}</p>
          {userData.preferredTags && userData.preferredTags.length > 0 && (
            <p><strong>Preferred Tags:</strong> {userData.preferredTags.map(tag => `${tag[0]} (${tag[1]} attempts)`).join(', ')}</p>
          )}
          {userData.struggledTags && userData.struggledTags.length > 0 && (
            <p><strong>Struggled Tags:</strong> {userData.struggledTags.map(tag => `${tag[0]} (${tag[1]} attempts)`).join(', ')}</p>
          )}
          {userData.tag_success_rates && Object.keys(userData.tag_success_rates).length > 0 && (
            <div>
              <h3>Tag Success Rates:</h3>
              <div className="tag-rates-grid">
                {Object.entries(userData.tag_success_rates)
                  .sort(([, a], [, b]) => b - a)
                  .map(([tag, rate]) => (
                    <div key={tag} className="tag-rate-item">
                      <strong>{tag}:</strong> {(rate * 100).toFixed(1)}%
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="recommendations-section">
          <h2>💡 Recommended Problems:</h2>
          <div className="problem-list">
            {recommendations.map((problem, index) => (
              <div key={problem.problem_id || index} className="problem-card">
                <h3><a href={problem.url} target="_blank" rel="noopener noreferrer">{problem.problem_name}</a></h3>
                <p>Rating: {problem.problem_rating || 'N/A'}</p>
                <p className="tags">Tags: {problem.problem_tags.join(', ')}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && !error && !userData && (
        <div className="initial-message">
          <p>Enter a Codeforces handle above to get started!</p>
          <p>Example handles: tourist, fefer_ivan, Errichto</p>
        </div>
      )}

      <footer className="App-footer">
        <p>&copy; 2025 Codeforces Problem Recommender. Built with FastAPI and React.</p>
      </footer>
    </div>
  );
}

export default App;