============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.5, pluggy-1.6.0 -- C:\Users\oktay\Documents\aisports\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: c:\Users\oktay\Documents\aisports
plugins: anyio-4.9.0, asyncio-1.0.0, cov-6.1.1, mock-3.14.1
asyncio: mode=Mode.STRICT, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 6 items

tests/unit/scraping/extractors/test_base_extractor.py::TestBaseExtractor::test_base_extractor_is_abc PASSED [ 16%]
tests/unit/scraping/extractors/test_base_extractor.py::TestBaseExtractor::test_abstract_method_defined PASSED [ 33%]
tests/unit/scraping/extractors/test_base_extractor.py::TestBaseExtractor::test_default_priority PASSED [ 50%]
tests/unit/scraping/extractors/test_base_extractor.py::TestBaseExtractor::test_concrete_extractor_implementation PASSED [ 66%]
tests/unit/scraping/extractors/test_base_extractor.py::TestBaseExtractor::test_concrete_extractor_error_scenario PASSED [ 83%]
tests/unit/scraping/extractors/test_base_extractor.py::TestBaseExtractor::test_cannot_instantiate_base_extractor_directly PASSED [100%]

============================== 6 passed in 3.09s ==============================
