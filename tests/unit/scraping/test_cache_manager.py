\
# filepath: c:\\\\Users\\\\oktay\\\\Documents\\\\aisports\\\\tests\\\\unit\\\\scraping\\\\test_cache_manager.py
import pytest
import os
import json
import time
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from capabilities.scraping.cache_manager import CacheManager

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory for tests."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return str(cache_dir)

@pytest.fixture
def cache_manager(temp_cache_dir):
    """Fixture to create a CacheManager instance with a temporary cache directory."""
    return CacheManager(cache_dir=temp_cache_dir, cache_expiration_hours=1)

@pytest.fixture
def cache_manager_long_expiry(temp_cache_dir):
    """CacheManager with a longer, non-trivial expiry for certain tests."""
    return CacheManager(cache_dir=temp_cache_dir, cache_expiration_hours=24)

class TestCacheManager:

    def test_initialization(self, temp_cache_dir):
        """Test that CacheManager initializes and creates the cache directory."""
        assert os.path.exists(temp_cache_dir)
        manager = CacheManager(cache_dir=temp_cache_dir, cache_expiration_hours=24)
        assert manager.cache_dir == temp_cache_dir
        assert manager.cache_expiration_hours == 24
        assert os.path.isdir(manager.cache_dir)

    @pytest.mark.parametrize("url, params, expected_suffix_part", [
        ("http://example.com", None, "http://example.com"),
        ("http://example.com", {"key": "value"}, "http://example.com-key:value"),
        ("http://example.com", {"b": "2", "a": "1"}, "http://example.com-a:1-b:2"), # Sorted params
        ("http://example.com", {"list_param": ["z", "a"]}, "http://example.com-list_param:a|z"), # Sorted list
        ("http://example.com", {"k": ["v2", "v1"], "p": "val"}, "http://example.com-k:v1|v2-p:val"),
    ])
    def test_generate_cache_key(self, cache_manager, url, params, expected_suffix_part):
        key1 = cache_manager.generate_cache_key(url, params)
        key2 = cache_manager.generate_cache_key(url, params) # Consistency
        assert isinstance(key1, str)
        assert len(key1) == 32 # MD5 hexdigest length
        assert key1 == key2

        # Test that different params yield different keys
        if params is not None:
            params_alt = params.copy()
            params_alt["new_key"] = "new_value"
            key_alt = cache_manager.generate_cache_key(url, params_alt)
            assert key1 != key_alt
        else:
            key_alt = cache_manager.generate_cache_key(url, {"new_key": "new_value"})
            assert key1 != key_alt

    def test_generate_cache_key_for_article(self, cache_manager):
        url = "http://example.com/article1"
        keywords = ["news", "sports"]
        key_direct = cache_manager.generate_cache_key(url, params={"keywords": sorted(keywords)})
        key_alias = cache_manager.generate_cache_key_for_article(url, keywords)
        assert key_alias == key_direct
        assert len(key_alias) == 32

        keywords_shuffled = ["sports", "news"]
        key_alias_shuffled = cache_manager.generate_cache_key_for_article(url, keywords_shuffled)
        # The alias method itself doesn't sort keywords before passing to generate_cache_key,
        # but generate_cache_key sorts list param values.
        assert key_alias_shuffled == key_direct 

    def test_cache_content_and_get_cached_content_valid(self, cache_manager_long_expiry):
        manager = cache_manager_long_expiry
        url = "http://example.com/content"
        data = {"title": "Test Title", "body": "Test Body"}
        cache_key = manager.generate_cache_key(url)

        # Cache miss initially
        assert manager.get_cached_content(cache_key) is None

        # Cache content
        assert manager.cache_content(cache_key, data) is True

        # Cache hit
        cached_data = manager.get_cached_content(cache_key)
        assert cached_data is not None
        assert cached_data == data

    def test_get_cached_content_expired(self, temp_cache_dir):
        # Use a very short expiration for this test
        manager = CacheManager(cache_dir=temp_cache_dir, cache_expiration_hours=0.0001) # approx 0.36 seconds
        url = "http://example.com/expired"
        data = {"title": "Expired Content"}
        cache_key = manager.generate_cache_key(url)

        assert manager.cache_content(cache_key, data) is True
        cache_file_path = manager._get_cache_file_path(cache_key)
        assert os.path.exists(cache_file_path)

        time.sleep(0.5) # Wait for cache to expire

        assert manager.get_cached_content(cache_key) is None
        assert not os.path.exists(cache_file_path) # File should be removed

    def test_get_cached_content_file_not_found(self, cache_manager):
        assert cache_manager.get_cached_content("non_existent_key") is None

    def test_get_cached_content_corrupted_json(self, cache_manager):
        cache_key = "corrupted_key"
        cache_file_path = cache_manager._get_cache_file_path(cache_key)
        
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            f.write("this is not json")
        
        assert os.path.exists(cache_file_path)
        assert cache_manager.get_cached_content(cache_key) is None
        assert not os.path.exists(cache_file_path) # Corrupted file should be removed

    def test_get_cached_content_missing_timestamp(self, cache_manager):
        cache_key = "missing_timestamp_key"
        cache_file_path = cache_manager._get_cache_file_path(cache_key)
        data_no_timestamp = {"data": {"title": "Test"}}
        
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(data_no_timestamp, f)
            
        assert os.path.exists(cache_file_path)
        assert cache_manager.get_cached_content(cache_key) is None
        assert not os.path.exists(cache_file_path) # File should be removed

    def test_cache_content_error_writing(self, cache_manager):
        # Mock open to raise an OSError
        with patch('builtins.open', MagicMock(side_effect=OSError("Disk full"))):
            assert cache_manager.cache_content("some_key", {"data": "test"}) is False

    def test_cleanup_expired_cache(self, temp_cache_dir):
        manager = CacheManager(cache_dir=temp_cache_dir, cache_expiration_hours=1)
        base_url = "http://example.com/page"
        
        # Cache some items: 1 valid, 1 expired, 1 corrupted, 1 missing timestamp
        valid_key = manager.generate_cache_key(base_url + "1")
        manager.cache_content(valid_key, {"data": "valid"})

        expired_key = manager.generate_cache_key(base_url + "2")
        manager.cache_content(expired_key, {"data": "to_expire"})
        # Manually alter timestamp to make it expired
        expired_file_path = manager._get_cache_file_path(expired_key)
        with open(expired_file_path, 'r+', encoding='utf-8') as f:
            content = json.load(f)
            content["timestamp"] = (datetime.now() - timedelta(hours=2)).isoformat()
            f.seek(0)
            json.dump(content, f)
            f.truncate()

        corrupted_key = manager.generate_cache_key(base_url + "3")
        corrupted_file_path = manager._get_cache_file_path(corrupted_key)
        with open(corrupted_file_path, 'w', encoding='utf-8') as f:
            f.write("not json")

        no_ts_key = manager.generate_cache_key(base_url + "4")
        no_ts_file_path = manager._get_cache_file_path(no_ts_key)
        with open(no_ts_file_path, 'w', encoding='utf-8') as f:
            json.dump({"data": "no_ts_data"}, f)
            
        # Add a non-cache file to ensure it's ignored
        with open(os.path.join(temp_cache_dir, "other_file.txt"), "w") as f:
            f.write("ignore me")

        assert os.path.exists(manager._get_cache_file_path(valid_key))
        assert os.path.exists(expired_file_path)
        assert os.path.exists(corrupted_file_path)
        assert os.path.exists(no_ts_file_path)

        removed_count = manager.cleanup_expired_cache()
        assert removed_count == 3 # expired, corrupted, no_ts

        assert os.path.exists(manager._get_cache_file_path(valid_key)) # Valid should remain
        assert not os.path.exists(expired_file_path)
        assert not os.path.exists(corrupted_file_path)
        assert not os.path.exists(no_ts_file_path)
        assert os.path.exists(os.path.join(temp_cache_dir, "other_file.txt")) # Ignored file should remain

    def test_cleanup_expired_cache_empty_dir(self, cache_manager):
        assert cache_manager.cleanup_expired_cache() == 0

    def test_cleanup_expired_cache_no_expired_files(self, cache_manager_long_expiry):
        manager = cache_manager_long_expiry
        manager.cache_content(manager.generate_cache_key("http://example.com/fresh"), {"data": "fresh"})
        assert manager.cleanup_expired_cache() == 0
        assert os.path.exists(manager._get_cache_file_path(manager.generate_cache_key("http://example.com/fresh")))

    def test_get_cached_content_removes_expired_file(self, temp_cache_dir):
        manager = CacheManager(cache_dir=temp_cache_dir, cache_expiration_hours=0.0001) # ~0.36s
        key = manager.generate_cache_key("http://example.com/test_expiry_removal")
        manager.cache_content(key, {"data": "will expire"})
        cache_file = manager._get_cache_file_path(key)
        
        assert os.path.exists(cache_file)
        time.sleep(0.5) # Ensure expiry
        
        assert manager.get_cached_content(key) is None # This call should detect expiry and remove the file
        assert not os.path.exists(cache_file)

    def test_get_cached_content_removes_corrupted_file(self, cache_manager):
        key = cache_manager.generate_cache_key("http://example.com/test_corrupt_removal")
        cache_file = cache_manager._get_cache_file_path(key)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True) # Ensure directory exists
        with open(cache_file, 'w') as f:
            f.write("{not_json_at_all")
        
        assert os.path.exists(cache_file)
        assert cache_manager.get_cached_content(key) is None # This call should detect corruption and remove
        assert not os.path.exists(cache_file)

# To run these tests:
# pytest tests/unit/scraping/test_cache_manager.py
# For coverage:
# pytest --cov=capabilities.scraping.cache_manager --cov-report=html tests/unit/scraping/test_cache_manager.py
