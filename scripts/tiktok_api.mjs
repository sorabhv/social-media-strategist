/**
 * Node.js helper for TikTok Creative Center API.
 * Uses tiktok-discovery-api which handles signature generation.
 *
 * Usage:
 *   node tiktok_api.mjs songs   [country] [limit] [period]
 *   node tiktok_api.mjs hashtags [country] [limit] [period]
 *   node tiktok_api.mjs creators [country] [limit] [period]
 *   node tiktok_api.mjs videos  [country] [limit] [period]
 *
 * Outputs JSON to stdout for Python to consume.
 */

import TiktokDiscovery from "tiktok-discovery-api";

const [, , type = "songs", country = "US", limit = "10", period = "7"] = process.argv;

const fetchers = {
  songs: () =>
    TiktokDiscovery.getTrendingSongs(country, 1, parseInt(limit), parseInt(period)),
  hashtags: () =>
    TiktokDiscovery.getTrendingHastag(country, 1, parseInt(limit), parseInt(period)),
  creators: () =>
    TiktokDiscovery.getTrendingCreators(country, 1, parseInt(limit), parseInt(period)),
  videos: () =>
    TiktokDiscovery.getTrendingVideos(country, 1, parseInt(limit), parseInt(period)),
};

if (!fetchers[type]) {
  console.error(`Unknown type: ${type}. Use: songs, hashtags, creators, videos`);
  process.exit(1);
}

try {
  const data = await fetchers[type]();
  console.log(JSON.stringify(data));
} catch (e) {
  console.error(JSON.stringify({ error: e.message }));
  process.exit(1);
}
