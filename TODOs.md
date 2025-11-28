# TrendRadar TODOs

## MCP Language Awareness
- [ ] **Add language filtering to deep_search** - Currently the MCP tools don't know which language each platform uses
  - Config has `language` field per platform (e.g., "de", "en", "zh", "fr")
  - `deep_search` should allow filtering by language: `deep_search(query="AI", language="de")`
  - Return language info in results metadata
  - Consider auto-translating queries for non-English searches

## Platform Search Status

### Working (7 platforms)
- ✅ The Guardian (API)
- ✅ Spiegel (JS/Stealth) - de
- ✅ Al Jazeera (JS/Stealth) - en
- ✅ Heise (JS/Stealth) - de
- ✅ Le Monde (JS/Stealth) - fr
- ✅ Straits Times (JS/Stealth) - en
- ✅ Times of India (URL pattern) - en

### Disabled (need work)
- ❌ Tagesspiegel - JS search broken (uses complex React framework)
- ❌ Moscow Times - Search page only shows contribution banners
- ❌ Times of Israel - Cloudflare blocks even with stealth mode

## Future Improvements
- [ ] Add more platforms with working search
- [ ] Consider browserless.io for stubborn Cloudflare sites
- [ ] Add proxy rotation support for rate-limited sites
- [ ] Cache search results to reduce duplicate requests
