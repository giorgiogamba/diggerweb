import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// Points to the Discogs proxy (website backend)
const BACKEND_API_URL = 'http://127.0.0.1:8000/api/discogs/search/';
const QUERY_PARAM = 'username';

function App()
{
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState(QUERY_PARAM);
  const [results, setResults] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Makes a research in the database, looking for just page 1
  const handleSearch = async (page = 1) =>
  {
    if (!query.trim())
    {
      setError('No search item provided. Please add one');
      return;
    }

    setLoading(true);
    setError(null);
    
    // Waits cleaning results while loading
    if (page === 1)
    {
      setResults([]);
      setPagination(null);
    }

    try
    {
      // Makes DB search using proxy
      const response = await axios.get(BACKEND_API_URL,
      {
        params:
        {
          q: query,
          type: searchType,
          page: page,
        },
      });

      console.log("Backend response:", response.data);
      
      setResults(response.data.results || []);
      setPagination(response.data.pagination || null);

    }
    catch (err)
    {
      console.error("Error while executing backend query:", err);
      const errorMsg = err.response?.data?.error || err.message || 'Unknown error during research';

      setError(`Error: ${errorMsg}`);
      setResults([]);
      setPagination(null);
    }
    finally
    {
      setLoading(false);
    }
  };

  // Invoked when the user presses the "Search" button
  const handleSubmit = (e) =>
  {
    e.preventDefault();
    handleSearch(1);
  }

  return (
    <div className="App">
      <h1>diggerweb</h1>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search on Discogs"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Search'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {loading && <p>Loading...</p>}

      <div className="results">
        {results.length > 0 && results.map((item) => (
          <div key={item.url || item.items} className="result-item">
            <div>
              {`${item.url} -- (${item.items})`}
            </div>
          </div>
        ))}
         {results.length === 0 && !loading && !error && pagination && <p>No search result found</p>}
      </div>
    </div>
  );
}

export default App;