import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// Points to the Discogs proxy (website backend)
const BACKEND_API_URL = 'http://127.0.0.1:8000/api/discogs/search/';

function App()
{
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState('release');
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

  const ReleaseInfoComponent = ({data}) =>
  {
    const headers = Object.keys(data[0]);
    const rows = data.map(item => Object.values(item));

    return (
      <table>
        <thead>
          <tr>
            {headers.map(header => <th key={header}>{header}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) =>
            (
              <tr key={index}>
                {row.map((cell, index) => <td key={index}>{cell}</td>)}
              </tr>
            ))}
        </tbody>
      </table>
    );
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
        <select value={searchType} onChange={(e) => setSearchType(e.target.value)}>
          <option value="release">Release</option>
          <option value="artist">Artist</option>
          <option value="label">Label</option>
          <option value="master">Master Release</option>
        </select>
        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Search'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {loading && <p>Loading...</p>}

      <div className="results">
        {results.length > 0 && results.map((item) => (
          <div key={item.id || item.uri} className="result-item">
            <img src={item.thumb || item.cover_image || 'https://via.placeholder.com/60?text=N/A'} alt={item.title} />
            <div>
              <strong>{item.title}</strong>
              {item.year && ` (${item.year})`}
              {item.country && ` - ${item.country}`}
              <br />
              <small>Type: {item.type} - ID: {item.id}</small>
              {/* Populate here in order to show other data */}
              {item.formats && <p><small>Formats: <ReleaseInfoComponent data={item.formats}/></small></p> }
            </div>
          </div>
        ))}
         {results.length === 0 && !loading && !error && pagination && <p>No search result found</p>}
      </div>

      {pagination && pagination.pages > 1 && (
        <div className="pagination">
          <button
            onClick={() => handleSearch(pagination.page - 1)}
            disabled={loading || pagination.page <= 1}>
          Previous
          </button>
          <span> Page {pagination.page} dof {pagination.pages} (Tot: {pagination.items}) </span>
            <button
              onClick={() => handleSearch(pagination.page + 1)}
              disabled={loading || pagination.page >= pagination.pages}>
          Next
          </button>
        </div>
      )}

    </div>
  );
}

export default App;