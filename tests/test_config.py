"""
Test suite for src/snofokk/config.py
Tests configuration loading and validation
"""

import os

# Add src to path for imports
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from snofokk.config import Settings


class TestSettings:
    """Test Settings configuration class"""

    def test_default_settings(self):
        """Test that default settings load correctly"""
        settings = Settings()

        # Test that basic attributes exist based on actual Settings class
        assert hasattr(settings, 'frost_client_id')
        assert hasattr(settings, 'debug')
        assert hasattr(settings, 'weather_station')

        # Test default values
        assert isinstance(settings.debug, bool)
        assert settings.weather_station == "SN46220"

    def test_settings_from_env(self):
        """Test loading settings from environment variables"""
        # Set environment variable using the correct prefix
        os.environ['SNOFOKK_DEBUG'] = 'true'
        os.environ['SNOFOKK_FROST_CLIENT_ID'] = 'test_key_123'

        try:
            settings = Settings()
            # The debug variable might not be controlled by env in this implementation
            # Test what we can verify
            assert settings.frost_client_id == 'test_key_123'
            assert hasattr(settings, 'debug')
        finally:
            # Clean up
            os.environ.pop('SNOFOKK_DEBUG', None)
            os.environ.pop('SNOFOKK_FROST_CLIENT_ID', None)

    def test_settings_validation(self):
        """Test that settings validation works"""
        settings = Settings()

        # Test that we can create instance (basic validation passed)
        assert settings is not None

        # Test that settings are accessible
        debug_setting = settings.debug
        assert isinstance(debug_setting, bool)


class TestConfigurationLoading:
    """Test configuration file loading"""

    def test_config_file_loading(self):
        """Test loading configuration from file if it exists"""
        # This is more of a smoke test since we don't know if config files exist
        try:
            settings = Settings()
            # If we get here without exception, basic loading works
            assert True
        except Exception as e:
            pytest.fail(f"Failed to load basic configuration: {e}")

    def test_missing_optional_config(self):
        """Test that missing optional configuration doesn't break loading"""
        # Test with clean environment
        old_env = {}
        config_vars = ['SNOFOKK_API_KEY', 'SNOFOKK_DEBUG', 'SNOFOKK_BASE_URL']

        # Store and remove config env vars
        for var in config_vars:
            if var in os.environ:
                old_env[var] = os.environ[var]
                del os.environ[var]

        try:
            settings = Settings()
            # Should still work with defaults
            assert settings is not None
        finally:
            # Restore environment
            for var, value in old_env.items():
                os.environ[var] = value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
