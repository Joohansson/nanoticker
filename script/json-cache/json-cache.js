const NodeCache =             require("node-cache" );
const Http =                  require('http');
const Fs =                    require('fs');
const Express =               require('express');
const Cors =                  require('cors');
const Helmet =                require('helmet');

const PATH_MONITORS = '/monitors.json';
const PATH_STATS = '/stats.json';
const PATH_MONITORS_BETA = '/monitors-beta.json';
const PATH_STATS_BETA = '/stats-beta.json';
const HTTP_PORT = '9950';
const CACHE_DURATION = 10;
const PROXY_HOPS = 2;

// Define the proxy app
const app = Express();
app.use(Helmet());
app.use(Cors()); // Allow all origin in cors
app.set('trust proxy', PROXY_HOPS);
app.use(Express.json());
app.use(Express.static('static'));

var jsonCache = new NodeCache( { stdTTL: CACHE_DURATION, checkperiod: 5 } );

app.get('/', (req, res) => {
  processRequest(req.query, req, res);
})

// Check if a string is a valid JSON
function isValidJson (obj) {
  if (obj != null) {
    try {
        JSON.parse(JSON.stringify(obj));
        return true
    } catch (e) {
      return false;
    }
  }
  else  {
    return false;
  }
}

function getFromCache(id, path, req, res) {
  const cachedValue = jsonCache.get(id)
  if (isValidJson(cachedValue)) {
    console.info("Cache requested from: " + req.ip + " - " + id);
    return res.json(cachedValue);
  }
  console.info("File requested from: " + req.ip + " - " + id);

  // Update from file
  try {
    const file = JSON.parse(Fs.readFileSync(path, 'UTF-8'));
    // Store in cache
    if (!jsonCache.set(id, file, CACHE_DURATION)) {
      console.info("Failed saving cache for " + id)
    }
    return res.json(file);
  }
  catch(e) {
    console.log("Could not read " + id, e);
    res.status(500).json({error: e.toString()});
  }
}

async function processRequest(query, req, res) {
  // Use cached value first
  try {
    switch (query.file) {
      case 'monitors':
        getFromCache('monitors', PATH_MONITORS, req, res)
        break;
      case 'stats':
        getFromCache('stats', PATH_STATS, req, res)
        break;
      case 'monitors-beta':
        getFromCache('monitors-beta', PATH_MONITORS_BETA, req, res)
        break;
      case 'stats-beta':
        getFromCache('stats-beta', PATH_STATS_BETA, req, res)
        break;
    }
    res.status(500).json({error: 'Bad request'})
  }
  catch(e) {
    return;
  }
}

Http.createServer(app).listen(HTTP_PORT, function() {
  console.log("Http server started on port: " + HTTP_PORT);
})