\
# filepath: c:\\\\Users\\\\oktay\\\\Documents\\\\aisports\\\\tests\\\\unit\\\\scraping\\\\test_file_manager.py
import pytest
import os
import json
import time
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from capabilities.scraping.file_manager import FileManager

@pytest.fixture
def temp_base_dir(tmp_path):
    """Create a temporary base directory for FileManager tests."""
    base_dir = tmp_path / "fm_data"
    # FileManager creates subdirs, so we just provide the base
    return str(base_dir)

@pytest.fixture
def file_manager(temp_base_dir):
    """Fixture to create a FileManager instance with a temporary base directory."""
    fm = FileManager(base_data_dir=temp_base_dir)
    return fm

class TestFileManager:

    def test_initialization(self, temp_base_dir):
        """Test FileManager initialization creates session and articles directories."""
        fm = FileManager(base_data_dir=temp_base_dir)
        assert fm.base_data_dir == temp_base_dir
        assert os.path.exists(fm.base_data_dir)
        assert os.path.isdir(fm.base_data_dir)
        
        expected_session_dir = os.path.join(temp_base_dir, 'sessions')
        expected_articles_dir = os.path.join(temp_base_dir, 'articles')
        
        assert fm.session_dir == expected_session_dir
        assert os.path.exists(fm.session_dir)
        assert os.path.isdir(fm.session_dir)
        
        assert fm.articles_dir == expected_articles_dir
        assert os.path.exists(fm.articles_dir)
        assert os.path.isdir(fm.articles_dir)

    @pytest.mark.parametrize("name, expected_sanitized", [
        ("valid_id", "valid_id"),
        ("id with spaces", "id_with_spaces"),
        ("../../../etc/passwd", "etc_passwd"),
        ("long_name_" + "a"*150, "long_name_" + "a"* (100 - len("long_name_"))),
        ("special-!@#$%^&*()-+=.json", "special--.json"),
    ])
    def test_sanitize_filename(self, file_manager, name, expected_sanitized):
        assert file_manager._sanitize_filename(name) == expected_sanitized

    def test_get_session_file_path(self, file_manager):
        session_id = "test_session_123"
        sanitized_id = file_manager._sanitize_filename(session_id)
        expected_path = os.path.join(file_manager.session_dir, f"session_{sanitized_id}.json")
        assert file_manager._get_session_file_path(session_id) == expected_path

    def test_get_article_file_path(self, file_manager):
        article_id = "article_hash_abc123"
        sanitized_id = file_manager._sanitize_filename(article_id)
        expected_path = os.path.join(file_manager.articles_dir, f"article_{sanitized_id}.json")
        assert file_manager._get_article_file_path(article_id) == expected_path

    def test_save_and_load_json_data_success(self, file_manager, tmp_path):
        file_path = str(tmp_path / "test_data.json")
        data_to_save = {"key": "value", "number": 123, "list": [1, 2, 3]}
        
        assert file_manager.save_json_data(file_path, data_to_save, "test_data") is True
        assert os.path.exists(file_path)
        
        loaded_data = file_manager.load_json_data(file_path, "test_data")
        assert loaded_data == data_to_save

    def test_load_json_data_file_not_found(self, file_manager):
        assert file_manager.load_json_data("non_existent_file.json", "test_data") is None

    def test_load_json_data_corrupted_file(self, file_manager, tmp_path):
        file_path = str(tmp_path / "corrupted.json")
        with open(file_path, 'w') as f:
            f.write("this is not valid json")
        
        assert file_manager.load_json_data(file_path, "corrupted_data") is None
        # Optionally, check if the file is deleted or moved if implemented

    def test_save_json_data_io_error(self, file_manager):
        with patch('builtins.open', MagicMock(side_effect=IOError("Disk full"))):
            assert file_manager.save_json_data("some_path.json", {"data": "test"}, "test_io") is False

    def test_save_and_load_session_data(self, file_manager):
        session_id = "session_abc"
        payload_data = {"info": "session details", "articles_count": 5}
        
        assert file_manager.save_session_data(session_id, payload_data) is True
        
        loaded_payload = file_manager.load_session_data(session_id)
        assert loaded_payload is not None
        assert loaded_payload == payload_data

        # Check the actual file content for structure
        session_file_path = file_manager._get_session_file_path(session_id)
        with open(session_file_path, 'r') as f:
            raw_data = json.load(f)
        assert raw_data["session_id"] == session_id
        assert "saved_at" in raw_data
        assert raw_data["payload"] == payload_data

    def test_load_session_data_mismatch_id(self, file_manager, caplog):
        session_id_actual = "actual_session"
        session_id_file_content = "different_session"
        
        # Manually create a session file with mismatched ID in payload
        session_file_path = file_manager._get_session_file_path(session_id_actual)
        malformed_data = {
            'session_id': session_id_file_content, # Mismatched ID
            'saved_at': datetime.now().isoformat(),
            'payload': {"data": "test"}
        }
        file_manager.save_json_data(session_file_path, malformed_data, "session")

        # When loading with actual_session, it should still return payload but log a warning
        loaded_payload = file_manager.load_session_data(session_id_actual)
        assert loaded_payload == {"data": "test"}
        assert f"Session ID mismatch in file {session_file_path}" in caplog.text


    def test_save_and_load_article_data(self, file_manager):
        article_id = "article_xyz"
        article_content = {"title": "Test Article", "body": "Lorem ipsum..."}
        
        assert file_manager.save_article(article_id, article_content) is True
        
        loaded_article = file_manager.load_article(article_id)
        assert loaded_article is not None
        assert loaded_article["title"] == article_content["title"] # Part of original data
        assert loaded_article["body"] == article_content["body"]   # Part of original data
        assert loaded_article["article_id_meta"] == article_id # Metadata added by save_article
        assert "file_saved_at" in loaded_article # Metadata added by save_article

    def test_cleanup_old_files(self, file_manager, temp_base_dir):
        # Create some files with different modification times
        dir_to_clean = os.path.join(temp_base_dir, "cleanup_test_dir")
        os.makedirs(dir_to_clean, exist_ok=True)
        
        now = time.time()
        file_prefix = "item_"

        # Old file (should be removed)
        old_file_path = os.path.join(dir_to_clean, f"{file_prefix}old.json")
        with open(old_file_path, 'w') as f: json.dump({"data": "old"}, f)
        os.utime(old_file_path, (now - 3*24*60*60, now - 3*24*60*60)) # 3 days old

        # New file (should be kept)
        new_file_path = os.path.join(dir_to_clean, f"{file_prefix}new.json")
        with open(new_file_path, 'w') as f: json.dump({"data": "new"}, f)
        os.utime(new_file_path, (now - 1*24*60*60, now - 1*24*60*60)) # 1 day old
        
        # Another old file with different prefix (should be ignored if prefix is used)
        other_prefix_old_file = os.path.join(dir_to_clean, "other_old.json")
        with open(other_prefix_old_file, 'w') as f: json.dump({"data": "other_old"}, f)
        os.utime(other_prefix_old_file, (now - 3*24*60*60, now - 3*24*60*60))

        # Non-json file (should be ignored)
        non_json_file = os.path.join(dir_to_clean, f"{file_prefix}text.txt")
        with open(non_json_file, 'w') as f: f.write("text")
        os.utime(non_json_file, (now - 3*24*60*60, now - 3*24*60*60))


        # Test cleanup with prefix
        removed_count = file_manager.cleanup_old_files(dir_to_clean, days_old=2, file_prefix=file_prefix)
        assert removed_count == 1
        assert not os.path.exists(old_file_path)
        assert os.path.exists(new_file_path)
        assert os.path.exists(other_prefix_old_file) # Ignored due to prefix
        assert os.path.exists(non_json_file) # Ignored due to extension

        # Reset old_file_path for next test
        with open(old_file_path, 'w') as f: json.dump({"data": "old"}, f)
        os.utime(old_file_path, (now - 3*24*60*60, now - 3*24*60*60))

        # Test cleanup without prefix (should remove both old json files)
        removed_count_no_prefix = file_manager.cleanup_old_files(dir_to_clean, days_old=2, file_prefix=None)
        assert removed_count_no_prefix == 2 # old_file_path and other_prefix_old_file
        assert not os.path.exists(old_file_path)
        assert not os.path.exists(other_prefix_old_file)
        assert os.path.exists(new_file_path)
        assert os.path.exists(non_json_file)


    def test_cleanup_old_files_non_existent_dir(self, file_manager, caplog):
        assert file_manager.cleanup_old_files("non_existent_dir_for_cleanup", days_old=1) == 0
        assert "Cleanup directory non_existent_dir_for_cleanup does not exist" in caplog.text

    def test_cleanup_old_sessions(self, file_manager):
        # This mostly tests that it calls cleanup_old_files correctly
        with patch.object(file_manager, 'cleanup_old_files', return_value=5) as mock_cleanup:
            days = 7
            result = file_manager.cleanup_old_sessions(days)
            mock_cleanup.assert_called_once_with(file_manager.session_dir, days, file_prefix="session_")
            assert result == 5

    def test_cleanup_old_articles(self, file_manager):
        with patch.object(file_manager, 'cleanup_old_files', return_value=3) as mock_cleanup:
            days = 30
            result = file_manager.cleanup_old_articles(days)
            mock_cleanup.assert_called_once_with(file_manager.articles_dir, days, file_prefix="article_")
            assert result == 3

# To run these tests:
# pytest tests/unit/scraping/test_file_manager.py
# For coverage:
# pytest --cov=capabilities.scraping.file_manager --cov-report=html tests/unit/scraping/test_file_manager.py
