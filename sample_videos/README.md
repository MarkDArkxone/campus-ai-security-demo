# Sample Videos

Put local test videos in this directory, for example:

```text
sample_videos/test.mp4
```

Then switch the video source in `app/config.py`:

```python
VIDEO_SOURCE = str(BASE_DIR / "sample_videos" / "test.mp4")
```

You can also update it at runtime with:

```bash
curl -X POST http://127.0.0.1:8000/api/config ^
  -H "Content-Type: application/json" ^
  -d "{\"video_source\":\"sample_videos/test.mp4\"}"
```
