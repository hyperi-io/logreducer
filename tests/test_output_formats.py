"""
Tests for different output formats
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from logreducer import LogReducer, OutputFormat
from logreducer.config import ProcessingLevel


class TestOutputFormats:
    """Test different output format options"""
    
    def test_line_format_default(self, small_log_file, tmp_path):
        """Test default line-by-line output format"""
        output_file = tmp_path / "output.log"
        meta_file = tmp_path / "output.meta.json"
        
        reducer = LogReducer(
            level="standard",
            enable_logging=False,  # Test with logging off
            output_format="line"  # Explicit line format
        )
        
        result = reducer.process_file(small_log_file, output_file)
        
        # Check output file exists
        assert output_file.exists()
        
        # Check metadata file exists for line format
        assert meta_file.exists()
        
        # Read output and verify it's line format
        with open(output_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        assert all('\n' in line for line in lines)
        
        # Verify metadata
        with open(meta_file, 'r') as f:
            metadata = json.load(f)
        
        assert 'stats' in metadata
        assert 'config' in metadata
        assert 'timestamp' in metadata
    
    def test_json_format(self, small_log_file, tmp_path):
        """Test JSON output format"""
        output_file = tmp_path / "output.json"
        
        reducer = LogReducer(
            level="standard", 
            enable_logging=True,  # Test with logging on
            log_level="INFO",
            output_format="json"
        )
        
        result = reducer.process_file(small_log_file, output_file)
        
        # Check output file exists
        assert output_file.exists()
        
        # Read and parse JSON
        with open(output_file, 'r') as f:
            output_data = json.load(f)
        
        assert 'lines' in output_data
        assert 'stats' in output_data
        assert 'config' in output_data
        assert 'timestamp' in output_data
        
        assert isinstance(output_data['lines'], list)
        assert len(output_data['lines']) > 0
        
        # Verify timestamp format
        timestamp = output_data['timestamp']
        datetime.fromisoformat(timestamp)  # Should not raise
    
    def test_json_format_pretty(self, small_log_file, tmp_path):
        """Test pretty JSON output format"""
        output_file = tmp_path / "output.json"
        
        reducer = LogReducer(
            level="standard",
            output_format="json",
            pretty_json=True
        )
        
        result = reducer.process_file(small_log_file, output_file)
        
        # Read file content
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Pretty JSON should have indentation
        assert '  ' in content or '\t' in content
        assert '\n' in content
        
        # Should still be valid JSON
        output_data = json.loads(content)
        assert 'lines' in output_data
    
    def test_jsonl_format(self, small_log_file, tmp_path):
        """Test JSON Lines output format"""
        output_file = tmp_path / "output.jsonl"
        
        reducer = LogReducer(
            level="standard",
            output_format="jsonl"
        )
        
        result = reducer.process_file(small_log_file, output_file)
        
        # Check output file exists
        assert output_file.exists()
        
        # Read and parse JSONL
        with open(output_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        
        # Each line should be valid JSON
        for line in lines:
            obj = json.loads(line)
            assert 'line' in obj
            assert 'timestamp' in obj
            
            # Verify timestamp
            datetime.fromisoformat(obj['timestamp'])
    
    def test_output_format_with_logging_disabled(self, small_log_file, tmp_path):
        """Test that output formats work correctly with logging disabled"""
        for format_type in ['line', 'json', 'jsonl']:
            output_file = tmp_path / f"output_{format_type}.{format_type}"
            
            reducer = LogReducer(
                level="standard",
                enable_logging=False,  # Logging disabled
                output_format=format_type
            )
            
            result = reducer.process_file(small_log_file, output_file)
            
            assert output_file.exists()
            
            # Verify file has content
            assert output_file.stat().st_size > 0
    
    def test_output_format_with_log_file(self, small_log_file, tmp_path):
        """Test output formats with log file configured"""
        output_file = tmp_path / "output.json"
        log_file = tmp_path / "processing.log"
        
        reducer = LogReducer(
            level="standard",
            enable_logging=True,
            log_file=str(log_file),
            log_level="DEBUG",
            output_format="json"
        )
        
        result = reducer.process_file(small_log_file, output_file)
        
        # Both output and log file should exist
        assert output_file.exists()
        assert log_file.exists()
        
        # Verify log file has content
        with open(log_file, 'r') as f:
            log_content = f.read()
        
        assert len(log_content) > 0
        assert "Processing" in log_content or "DEBUG" in log_content or "INFO" in log_content
    
    def test_log_file_error_handling(self, small_log_file, tmp_path):
        """Test that processing continues if log file can't be created"""
        output_file = tmp_path / "output.log"
        
        # Try to create log in a read-only directory (simulated by invalid path)
        reducer = LogReducer(
            level="standard",
            enable_logging=True,
            log_file="/invalid/path/that/does/not/exist/processing.log",
            output_format="line"
        )
        
        # Should not fail, just skip log file creation
        result = reducer.process_file(small_log_file, output_file)
        
        assert output_file.exists()
        assert len(result) > 0
    
    def test_return_metadata_flag(self, small_log_file, tmp_path):
        """Test return_metadata flag with different formats"""
        for format_type in ['line', 'json', 'jsonl']:
            output_file = tmp_path / f"output_{format_type}.{format_type}"
            
            # With metadata - create fresh reducer
            reducer = LogReducer(
                level="standard",
                output_format=format_type
            )
            
            result_with_meta = reducer.process_file(
                small_log_file, 
                output_file,
                return_metadata=True
            )
            
            assert isinstance(result_with_meta, dict)
            assert 'lines' in result_with_meta
            assert 'stats' in result_with_meta
            assert 'config' in result_with_meta
            
            # Without metadata (default) - create fresh reducer
            reducer2 = LogReducer(
                level="standard",
                output_format=format_type
            )
            
            result_no_meta = reducer2.process_file(
                small_log_file,
                str(output_file) + ".2"
            )
            
            assert isinstance(result_no_meta, list)
            assert len(result_no_meta) > 0
    
    def test_all_processing_modes_with_formats(self, small_log_file, tmp_path):
        """Test all processing modes work with different output formats"""
        modes = ['pattern', 'anomaly', 'temporal', 'hybrid']
        formats = ['line', 'json', 'jsonl']
        
        for mode in modes:
            for format_type in formats:
                output_file = tmp_path / f"{mode}_{format_type}.{format_type}"
                
                reducer = LogReducer(
                    level="enhanced",
                    mode=mode,
                    output_format=format_type,
                    enable_logging=False
                )
                
                result = reducer.process_file(small_log_file, output_file)
                
                assert output_file.exists()
                assert output_file.stat().st_size > 0
    
    def test_large_file_with_formats(self, large_log_file, tmp_path):
        """Test different formats with large files"""
        for format_type in ['line', 'json', 'jsonl']:
            output_file = tmp_path / f"large_{format_type}.{format_type}"
            
            reducer = LogReducer(
                level="standard",
                output_format=format_type,
                enable_logging=False,
                max_patterns=100  # Limit for faster test
            )
            
            result = reducer.process_file(large_log_file, output_file)
            
            assert output_file.exists()
            
            # Verify output is properly reduced
            input_size = large_log_file.stat().st_size
            output_size = output_file.stat().st_size
            
            assert output_size < input_size  # Should be reduced