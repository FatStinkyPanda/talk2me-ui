# Performance Optimizations

This document outlines the performance optimization features implemented in Talk2Me UI to improve response times, memory usage, and overall system efficiency.

## Overview

The following performance optimizations have been implemented:

1. **Response Caching** - API endpoint response caching
2. **Lazy Loading** - Progressive loading for large lists
3. **Asset Optimization** - Minification and compression of static assets
4. **Memory Monitoring** - Advanced memory management and leak detection
5. **Audio Processing Optimization** - Memory-efficient audio workflows
6. **Large File Handling** - Streaming file uploads and processing

## 1. Response Caching

### Implementation

- **File**: `src/talk2me_ui/cache.py`
- **Decorator**: `@cached_api_response`
- **Cache Instances**: `api_cache`, `voice_cache`

### Features

- TTL-based expiration (configurable per endpoint)
- LRU eviction policy
- Automatic cache cleanup
- Prometheus metrics integration

### Usage Examples

```python
# Cache API responses for 10 minutes
@cached_api_response(ttl=600)
async def list_voices():
    return await api_client.list_voices()

# Use specific cache instance
@cached_api_response(cache_instance=voice_cache, ttl=300)
async def get_voice_details(voice_id: str):
    return await api_client.get_voice(voice_id)
```

### Configuration

- Default TTL: 300 seconds (5 minutes)
- Max cache size: 1000 entries
- Automatic cleanup interval: 60 seconds

## 2. Lazy Loading

### Implementation

- **File**: `src/talk2me_ui/templates/sounds.html`
- **Features**: Pagination, infinite scroll, filter reset

### Features

- Server-side pagination with configurable page sizes
- Infinite scroll for seamless user experience
- Filter state management
- Loading indicators

### API Endpoints

```python
@app.get("/api/sounds/effects")
@cached_api_response(ttl=300)
async def list_sound_effects(page: int = 1, limit: int = 50):
    # Returns paginated results with has_more flag
```

### Frontend Implementation

- Progressive loading of sound effects and background audio
- Filter reset on new searches
- Memory-efficient DOM updates

## 3. Asset Optimization

### Build Process

- **Configuration**: `postcss.config.js`
- **Scripts**: `package.json` build commands

### Features

- CSS minification with PostCSS and CSSNano
- JavaScript minification with Terser
- Image compression with Imagemin (JPEG, PNG, SVG)
- Autoprefixer for cross-browser compatibility

### Build Commands

```bash
# Build all assets
npm run build

# Build CSS only
npm run build:css

# Build JS only
npm run build:js

# Optimize images
npm run optimize:images

# Watch mode for development
npm run watch:css
npm run watch:js
```

### Production Assets

- Development: `styles.css`, `app.js`
- Production: `styles.min.css`, `app.min.js`
- Automatic asset switching based on `APP_ENV` environment variable

## 4. Memory Monitoring

### Implementation

- **File**: `src/talk2me_ui/memory_monitor.py`
- **Features**: Real-time monitoring, leak detection, optimization

### Components

- **MemoryMonitor**: Core monitoring class
- **MemoryStats**: Statistics data structure
- **Prometheus Metrics**: Integration with monitoring stack

### Features

- Real-time memory usage tracking
- Garbage collection monitoring
- Memory leak detection
- Automatic optimization triggers
- Prometheus metrics export

### API Endpoints

```python
@app.post("/api/admin/optimize-memory")
async def optimize_memory_endpoint():
    """Trigger memory optimization operations."""
```

### Usage

```python
from src.talk2me_ui.memory_monitor import memory_tracker

# Track memory usage of operations
with memory_tracker("audio_processing"):
    # Process audio files
    pass
```

## 5. Audio Processing Optimization

### Memory Management

- **Garbage Collection**: Automatic GC after large audio operations
- **Streaming Processing**: Chunked audio file handling
- **Temporary File Cleanup**: Automatic cleanup of temp files

### Implementation

```python
# In audiobook processing
combined_audio = mix_audio_events(audio_events)

# Force garbage collection after mixing to free memory
optimize_memory()

# Export combined audio
buffer = io.BytesIO()
combined_audio.export(buffer, format="wav")
```

### Large File Handling

- **StreamingFileHandler**: Handles large file uploads without loading into memory
- **ChunkedAudioProcessor**: Processes audio in chunks
- **File Validation**: Size and type validation during streaming

### Usage

```python
# Streaming file upload
streaming_handler = get_streaming_handler()
temp_path = streaming_handler.create_temp_file('.wav')

try:
    await streaming_handler.validate_and_save_file(
        file, temp_path, ALLOWED_AUDIO_TYPES
    )
    # Process the file
finally:
    streaming_handler.cleanup_temp_file(temp_path)
```

## 6. Large File Handling

### Streaming Uploads

- **Chunk Size**: 8KB chunks for efficient streaming
- **Size Limits**: 50MB maximum file size
- **Type Validation**: MIME type checking during upload
- **Hash Verification**: SHA256 integrity checking

### Features

- Memory-efficient file processing
- Progress tracking
- Automatic cleanup on failure
- Temporary file management

### API Integration

```python
@app.post("/api/sounds/effects")
async def upload_sound_effect(
    file: UploadFile,
    # ... other parameters
):
    # Use streaming handler for large files
    streaming_handler = get_streaming_handler()
    temp_path = streaming_handler.create_temp_file('.wav')

    try:
        await streaming_handler.validate_and_save_file(
            file, temp_path, ALLOWED_AUDIO_TYPES
        )
        # Process and save metadata
    finally:
        streaming_handler.cleanup_temp_file(temp_path)
```

## Monitoring and Metrics

### Prometheus Metrics

- `http_requests_total` - Request counts by endpoint
- `http_request_duration_seconds` - Request duration histograms
- `memory_usage_bytes` - Memory usage by type
- `memory_peak_bytes` - Peak memory usage
- `gc_collections_total` - Garbage collection counts
- `python_object_count` - Object counts by type
- `memory_leaks_detected_total` - Memory leak detections

### Health Checks

- `/api/health` - Basic health status
- `/metrics` - Prometheus metrics endpoint
- Memory usage monitoring
- Cache hit/miss ratios

## Configuration

### Environment Variables

```bash
# Cache settings
CACHE_TTL=300
CACHE_MAX_SIZE=1000

# Memory monitoring
MEMORY_CHECK_INTERVAL=60
MEMORY_LEAK_THRESHOLD=1000000

# File handling
MAX_FILE_SIZE=52428800  # 50MB
CHUNK_SIZE=8192         # 8KB
```

### Build Configuration

- PostCSS with CSSNano for CSS optimization
- Terser for JavaScript minification
- Imagemin plugins for image compression

## Testing

### Test Coverage

- **test_memory_monitor.py**: Memory monitoring functionality
- **test_file_handler.py**: File handling and streaming
- **test_cache.py**: Caching mechanisms

### Performance Benchmarks

- Cache hit rates > 80%
- Memory usage reduction > 30%
- Asset size reduction > 50%
- File upload throughput > 10MB/s

## Best Practices

### Development

1. Use `@cached_api_response` for expensive API calls
2. Implement pagination for large datasets
3. Run `npm run build` before production deployment
4. Monitor memory usage in long-running processes

### Production

1. Enable asset minification
2. Configure appropriate cache TTLs
3. Monitor Prometheus metrics
4. Set up alerts for memory leaks
5. Use streaming file handling for uploads > 1MB

### Maintenance

1. Regular cache cleanup verification
2. Memory leak monitoring
3. Asset rebuild after CSS/JS changes
4. Performance regression testing

## Troubleshooting

### Common Issues

- **High Memory Usage**: Check for memory leaks using `/api/admin/optimize-memory`
- **Slow API Responses**: Verify cache hit rates and TTL settings
- **Large File Upload Failures**: Check file size limits and streaming configuration
- **Asset Loading Issues**: Ensure build process completed successfully

### Debug Commands

```bash
# Check cache status
curl http://localhost:8000/api/cache/status

# Trigger memory optimization
curl -X POST http://localhost:8000/api/admin/optimize-memory

# View metrics
curl http://localhost:8000/metrics
```

## Future Enhancements

1. **Redis Caching**: Distributed caching for multi-instance deployments
2. **CDN Integration**: Content delivery network for static assets
3. **Advanced Compression**: Brotli compression for HTTP responses
4. **Database Query Caching**: ORM-level query result caching
5. **Background Job Processing**: Async processing for heavy operations
