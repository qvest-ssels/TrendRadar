# TrendRadar TODOs

## MCP Language Awareness
- [x] **Add language filtering to deep_search** - ✅ DONE
  - Config has `language` field per platform (e.g., "de", "en", "zh", "fr")
  - `deep_search` now supports `language` parameter: `deep_search(query="AI", language="de")`
  - Returns language info in results metadata
  - Added `get_platform_language()` and updated `get_searchable_platforms(language=)`

## CDN Detection
- [x] **Add `cdn` field to config** - ✅ DONE (partial)
  - Added `cdn: "cloudflare"` to platforms with known Cloudflare protection
  - Platforms marked: timesofisrael, dailymaverick, aawsat
- [ ] **Use CDN info in browser service**
  - Auto-apply extra stealth/wait time for Cloudflare sites
  - Consider proxy rotation for Cloudflare-protected sites
  - Log CDN type when search fails for debugging

## Platform Search Status

### Working (7 platforms)
- ✅ The Guardian (API) - en
- ✅ Spiegel (JS/Stealth) - de
- ✅ Al Jazeera (JS/Stealth) - en
- ✅ Heise (JS/Stealth) - de
- ✅ Le Monde (JS/Stealth) - fr
- ✅ Straits Times (JS/Stealth) - en
- ✅ Times of India (URL pattern) - en

### Disabled (need work)
- ❌ Tagesspiegel - JS search broken (uses complex React framework)
- ❌ Moscow Times - Search page only shows contribution banners
- ❌ Times of Israel - Cloudflare blocks even with stealth mode (cdn: cloudflare)
- ❌ Daily Maverick - Cloudflare protection (cdn: cloudflare)
- ❌ Asharq Al-Awsat - Cloudflare protection (cdn: cloudflare)

### Not yet tested
- ⏳ Slashdot - Has search, needs testing
- ⏳ Guardian AU - Can use same API as Guardian
- ⏳ Folha - Portuguese, search page timeout

## Future Improvements
- [ ] Add more platforms with working search
- [ ] Consider browserless.io for stubborn Cloudflare sites
- [ ] Add proxy rotation support for rate-limited sites
- [ ] Cache search results to reduce duplicate requests
- [ ] Auto-detect CDN from response headers
