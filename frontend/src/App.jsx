import React, { useState, useCallback } from 'react';
import axios from 'axios';
import './App.css';

// Points to the Discogs proxy (website backend)
const BACKEND_BASE_URL = 'http://127.0.0.1:8000/api/discogs'; // Base URL
const BACKEND_SEARCH_URL = `${BACKEND_BASE_URL}/search/`;
const BACKEND_AUTHORIZE_URL = `${BACKEND_BASE_URL}/authorize/`;

// Default items per page to request
const ITEMS_PER_PAGE = 20;

// User facing texts
const APPLICATION_TITLE = 'digger';
const LOADING = 'LOADING...';
const SEARCH = 'SEARCH';
const NO_RESULTS = 'No search results found for this page or query.';
const AUTHORIZE_PROMPT = 'Authorization required. Please authorize with Discogs to perform searches.';
const AUTHORIZE_BUTTON_TEXT = 'Authorize with Discogs';

function setEmptyResult()
{
  setResults([]);
  setPagination(null);
}

function App()
{
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authorizeUrl, setAuthorizeUrl] = useState(null);

  const setEmptyResult = useCallback(() => {
    setResults([]);
    setPagination(null);
  }, []);
  
  const handleAuthorize = () => {
    if (authorizeUrl)
    {
      const popupWidth = 600;
      const popupHeight = 700;
      const left = window.screen.width / 2 - popupWidth / 2;
      const right = window.screen.height / 2 - popupHeight / 2;
      window.open
      (
        authorizeUrl,
        'discogsAuthorizationPopup',
        'width=${popupWidth},height=${popupHeight},top=${top},left=${left}'
      );
    }
    else
    {
      console.error("Failed authorization");
      setError("Could not initialize authorization");
    }
  }


  // Makes a research in the database, looking for just page 1
  const handleSearch = async (page = 1) =>
  {
    if (!query.trim())
    {
      setError('No search item provided. Please add one');
      setEmptyResult();
      setAuthorizeUrl(null);
      return;
    }

    setLoading(true);
    setError(null);
    setAuthorizeUrl(null);
    
    // Waits cleaning results while loading
    if (page === 1)
    {
      setEmptyResult();
    }

    try
    {
      // Makes DB search using proxy
      const response = await axios.get(BACKEND_SEARCH_URL,
      {
        params:
        {
          q: trimmedQuery,
          page: page,
          per_page: ITEMS_PER_PAGE
        },
      });

      console.log("Backend response:", response.data);
      
      setResults(response.data.results || []);
      setPagination(response.data.pagination || null);

      if (!response.data.results || response.data.results.length === 0) {
         if (response.data.pagination && response.data.pagination.items > 0) {
             setError(`No results found on page ${page}. Total items found: ${response.data.pagination.items}`);
         } else {
             setError(NO_RESULTS);
         }
      }

    }
    catch (err)
    {
      console.error("Error while executing backend query:", err);
      setResults([]);
      setPagination(null);

      if (err.response) {
        console.error("Backend error response:", err.response);
        const errorData = err.response.data;
        const status = err.response.status;

        if (status === 401 && errorData?.authorize_url)
        {
          setError(AUTHORIZE_PROMPT);
          setAuthorizeUrl(errorData.authorize_url);
        }
        else if (status === 404) {
          setError(`Error: User '${trimmedQuery}' not found or inventory is private/empty.`);
        }
        else
        {
          const errorMsg = errorData?.error || err.message || 'Unknown error during research';
          setError(`Error: ${errorMsg} (Status: ${status})`);
          setAuthorizeUrl(null);
        }
      } else {
         setError(`Network Error: ${err.message}`);
         setAuthorizeUrl(null);
      }
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
    handleSearch(1); // Always start search from page 1
  }

  return (
    <div className="App">
      <h1>{APPLICATION_TITLE}</h1>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Discogs username"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? LOADING : SEARCH}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {authorizeUrl && !loading && (
        <div className="authorization-prompt">
          <button onClick={handleAuthorize} disabled={loading}>
            {AUTHORIZE_BUTTON_TEXT}
          </button>
        </div>
      )}

      {loading && <p>{LOADING}</p>}

      <div className="results">
        {Array.isArray(results) && results.length > 0 && results.map((item) => (
          <div key={item.id || item.release_id || item.url} className="result-item">
            <p> <strong>{item.title || 'No Title'}</strong> by {item.artist || 'Unknown Artist'} </p>
            {item.price && item.currency && (
               <p>Price: {item.price} {item.currency}</p>
            )}
            <p>Condition (Media/Sleeve): {item.condition || 'N/A'} / {item.sleeve_condition || 'N/A'}</p>
            {item.url && <p><a href={item.url} target="_blank" rel="noopener noreferrer">View on Discogs Marketplace</a></p>}
            {typeof item.num_for_sale !== 'undefined' && item.num_for_sale !== null && (
              <p>({item.num_for_sale} available for sale according to stats)</p>
            )}
            {item.error && <p className="error">Note: {item.error}</p>}
          </div>
        ))}
        {results.length === 0 && !loading && !error && pagination && <p>{`${NO_RESULTS}`}</p>}
      </div>
    </div>
  );
}

export default App;