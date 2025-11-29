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
- ❌ Folha - Cloudflare protection (cdn: cloudflare)

### Not yet tested
- ⏳ Guardian AU - Can use same API as Guardian

## Future Improvements
- [ ] Add more platforms with working search
- [ ] Consider browserless.io for stubborn Cloudflare sites
- [ ] Add proxy rotation support for rate-limited sites
- [ ] Cache search results to reduce duplicate requests
- [ ] Auto-detect CDN from response headers

---

## Translation Service Integration

### Overview
Modular translation service supporting both local and remote backends, starting with LibreTranslate for local/self-hosted translation.

### Phase 1: Infrastructure Setup
- [x] **1.1 Create translation service directory structure** ✅ DONE
  - Created `mcp_server/services/translation_service.py`
  - TranslationService class with singleton pattern
  - Methods: `translate()`, `translate_batch()`, `detect_language()`, `get_languages()`

- [x] **1.2 Test LibreTranslate with Colima/Docker on ARM** ✅ DONE
  - Tested with Colima on macOS ARM64 (aarch64)
  - Cloned upstream: `libretranslate-upstream/` (gitignored)
  - Key fix: `tty: true` required for docker logs to show
  - Key fix: Port 5000 conflicts with AirPlay on macOS → use 5555
  - Models cached in Docker volume for fast restarts

- [x] **1.3 Create LibreTranslate docker-compose for TrendRadar** ✅ DONE
  - Added `docker/docker-compose-libretranslate.yml`
  - Cloned upstream repo to `libretranslate-upstream/` with working config
  - Volume: `libretranslate_models:/home/libretranslate/.local:rw`
  - Languages: en, de, zh, fr, es (5 languages, 8 models)
  - API tested: `/health`, `/languages`, `/translate` all working
  - Start: `cd libretranslate-upstream && docker compose up -d`

### Phase 2: Translation Service Implementation
- [x] **2.1 Create base translation interface** ✅ DONE
  - `mcp_server/services/translation_service.py` - TranslationService class
  - Methods: `translate(text, source, target)`, `detect_language(text)`, `get_languages()`
  - Batch translation via `translate_batch()`
  - Health check via `is_available()`

- [x] **2.2 Implement LibreTranslate adapter** ✅ DONE
  - HTTP client for LibreTranslate API (`/translate`, `/detect`, `/languages`)
  - Connection health check, timeout handling
  - Singleton pattern via `get_translation_service()`

- [ ] **2.3 Create translation service factory** (optional for future)
  - Config-driven backend selection (local/remote)
  - Support for fallback chains (local -> remote)
  - Easy extensibility for future backends (DeepL, Google, etc.)

### Phase 3: MCP Integration
- [x] **3.1 Add translation config to config.yaml** ✅ SKIPPED
  - Using default URL http://localhost:5555 in code
  - Can be made configurable later if needed

- [x] **3.2 Create MCP translation tools** ✅ DONE
  - `translate_text(text, source, target)` - Translate single text
  - `translate_headlines(date, target_language)` - Translate cached headlines
  - `get_translation_languages()` - Get available languages

- [ ] **3.3 Integrate translation into existing tools** (future)
  - Add optional `translate_to` parameter to `deep_search`
  - Add translation option to `meta_search` results
  - Auto-detect and translate non-English headlines when requested

### Phase 4: Future Extensions
- [ ] **4.1 Remote translation backends**
  - DeepL API adapter (high quality, requires API key)
  - Google Translate API adapter (requires credentials)
  - Azure Translator adapter

- [ ] **4.2 Translation caching**
  - Cache translations to avoid duplicate API calls
  - Use same SQLite cache as headlines
  - TTL-based cache invalidation

- [ ] **4.3 Quality/Cost optimization**
  - Prefer local translation for common language pairs
  - Fallback to remote for unsupported pairs
  - Rate limiting for remote API costs

### Technical Notes
- **LibreTranslate ARM64**: Uses `docker/arm.Dockerfile` with `arm64v8/python:3.11.11-slim-bullseye`
- **Docker command**: `docker run -ti --rm -p 5000:5000 -v lt-local:/home/libretranslate/.local libretranslate/libretranslate --load-only en,de,zh,fr,es`
- **API Endpoints**:
  - `POST /translate` - `{q: "text", source: "en", target: "de"}`
  - `POST /detect` - `{q: "text"}`
  - `GET /languages` - List supported languages
- **Memory**: ~2GB with all models, ~500MB with limited languages
- **First startup**: Downloads language models (~1-2GB)
