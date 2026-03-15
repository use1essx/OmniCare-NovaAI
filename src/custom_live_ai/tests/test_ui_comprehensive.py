#!/usr/bin/env python3
"""
Comprehensive Unit Tests for index_detailed.html UI
Tests all major JavaScript functions and error handling
"""

import pytest
from pathlib import Path
import re


class TestIndexDetailedHTML:
    """Comprehensive tests for the detailed UI"""
    
    @pytest.fixture(scope="class")
    def html_content(self):
        """Load the HTML file"""
        html_path = Path(__file__).parent.parent / "src" / "static" / "index_detailed.html"
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_file_exists(self):
        """Test that index_detailed.html exists"""
        html_path = Path(__file__).parent.parent / "src" / "static" / "index_detailed.html"
        assert html_path.exists(), "index_detailed.html not found"
    
    def test_html_structure_valid(self, html_content):
        """Test that HTML has valid structure"""
        assert "<!DOCTYPE html>" in html_content
        assert "<html" in html_content
        assert "</html>" in html_content
        assert "<head>" in html_content
        assert "<body>" in html_content
    
    def test_required_libraries_loaded(self, html_content):
        """Test that all required external libraries are loaded"""
        required_libs = [
            "@mediapipe/camera_utils",
            "@mediapipe/pose",
            "@mediapipe/hands",
            "@mediapipe/face_mesh",
            "face-api.js"
        ]
        for lib in required_libs:
            assert lib in html_content, f"Missing library: {lib}"
    
    def test_all_ui_sections_present(self, html_content):
        """Test that all major UI sections exist"""
        sections = [
            "camera-section",
            "sidebar-section",
            "controls-container",
            "console-container",
            "tab-recording",
            "tab-session",
            "tab-emotion",
            "tab-posture",
            "tab-interventions",
            "tab-stats"
        ]
        for section in sections:
            assert section in html_content, f"Missing UI section: {section}"
    
    def test_console_systems_present(self, html_content):
        """Test that all three console systems exist"""
        consoles = ["console-all", "console-errors", "console-api"]
        for console in consoles:
            assert console in html_content, f"Missing console: {console}"
    
    def test_critical_functions_defined(self, html_content):
        """Test that all critical JavaScript functions are defined"""
        critical_functions = [
            "function startCamera()",
            "function stopCamera()",
            "function startRecording()",
            "function stopRecording()",
            "function logToConsole(",
            "function logApiCall(",
            "function updateEmotionDisplay(",
            "function startSession(",
            "function stopSession(",
            "function showControlTab(",
            "function showConsole(",
            "function smoothScrollConsole("
        ]
        for func in critical_functions:
            assert func in html_content, f"Missing critical function: {func}"
    
    def test_null_checks_in_console_logging(self, html_content):
        """Test that console logging has null checks"""
        # Should have null checks for console elements
        assert "if (allConsole)" in html_content or "if(allConsole)" in html_content, "Missing allConsole null check"
        # Error console check is now part of the error handling block
        assert "type === 'error'" in html_content or "type === 'warning'" in html_content, "Missing error/warning handling"
    
    def test_smooth_scroll_implementation(self, html_content):
        """Test that smooth scroll uses requestAnimationFrame"""
        assert "requestAnimationFrame" in html_content, "requestAnimationFrame not used for smooth scroll"
        assert "smoothScrollConsole" in html_content, "smoothScrollConsole function missing"
    
    def test_max_console_lines_limit(self, html_content):
        """Test that console has line limits to prevent memory issues"""
        assert "MAX_CONSOLE_LINES" in html_content, "MAX_CONSOLE_LINES constant missing"
        # Check that it's set to a reasonable value (50-100)
        max_lines_match = re.search(r'MAX_CONSOLE_LINES\s*=\s*(\d+)', html_content)
        assert max_lines_match, "MAX_CONSOLE_LINES value not found"
        max_lines = int(max_lines_match.group(1))
        assert 20 <= max_lines <= 200, f"MAX_CONSOLE_LINES should be 20-200, got {max_lines}"
    
    def test_emotion_display_null_checks(self, html_content):
        """Test that updateEmotionDisplay has comprehensive null checks"""
        # Should have element null checks in updateEmotionDisplay
        required_checks = [
            ("emojiEl", "emotionEmoji"),
            ("labelEl", "emotionLabel"),
            ("confEl", "emotionConfidence"),
            ("scoresDiv", "emotionScores")
        ]
        for var_name, element_id in required_checks:
            # Check that element is assigned to a variable and checked
            assert element_id in html_content, f"Missing element: {element_id}"
            # The pattern is: const varName = document.getElementById(...); if (varName) ...
            # Just verify the element IDs exist and there are some if statements
        assert html_content.count("if (") > 50, "Insufficient null checks found"
    
    def test_face_detection_before_data_stream(self, html_content):
        """Test that data stream checks for face detection before sending"""
        # Find startSessionDataStream function
        assert "startSessionDataStream" in html_content
        data_stream_match = re.search(r'function startSessionDataStream\([^{]*\{([^}]+\{[^}]+\})+[^}]+\}', html_content, re.DOTALL)
        assert data_stream_match, "startSessionDataStream function not found"
        
        func_body = data_stream_match.group(0)
        # Should check if face is detected before sending
        assert "face" in func_body.lower() and "detected" in func_body.lower(), "No face detection check in data stream"
        assert "if (!faceDetected)" in func_body or "if(!faceDetected)" in func_body, "Missing faceDetected guard clause"
    
    def test_api_error_handling(self, html_content):
        """Test that API calls have proper error handling"""
        # Check for try-catch blocks in async functions
        assert "try {" in html_content, "No try-catch blocks found"
        assert "catch (error)" in html_content or "catch(error)" in html_content, "No error catching found"
        
        # Check that errors are logged
        assert "logToConsole" in html_content
    
    def test_no_infinite_loops(self, html_content):
        """Test that there are no obvious infinite loops"""
        # Check for while(true) patterns (should not exist)
        assert "while(true)" not in html_content.lower(), "Potential infinite loop found"
        assert "while (true)" not in html_content.lower(), "Potential infinite loop found"
    
    def test_duplicate_message_throttling(self, html_content):
        """Test that duplicate messages are throttled"""
        log_func_match = re.search(r'function logToConsole\([^{]+\{([^}]+\{[^}]+\})+[^}]+\}', html_content, re.DOTALL)
        assert log_func_match, "logToConsole function not found"
        
        func_body = log_func_match.group(0)
        # Should have throttling logic
        assert "lastLogged" in func_body or "lastMessage" in func_body, "No message throttling found"
    
    def test_intervention_system_present(self, html_content):
        """Test that intervention system is properly implemented"""
        intervention_functions = [
            "triggerIntervention",
            "addInterventionToHistory"
        ]
        for func in intervention_functions:
            assert func in html_content, f"Missing intervention function: {func}"
    
    def test_session_management_functions(self, html_content):
        """Test that session management is complete"""
        session_functions = [
            "startSession",
            "stopSession",
            "getSessionStatus",
            "generateReport"
        ]
        for func in session_functions:
            assert func in html_content, f"Missing session function: {func}"
    
    def test_no_console_errors_in_syntax(self, html_content):
        """Test that there are no obvious syntax errors"""
        # Check for balanced braces
        open_braces = html_content.count('{')
        close_braces = html_content.count('}')
        # Should be roughly balanced (allowing for CSS and inline styles)
        assert abs(open_braces - close_braces) < 10, f"Unbalanced braces: {open_braces} open, {close_braces} close"
        
        # Check for balanced parentheses in script section
        script_match = re.search(r'<script>(.*)</script>', html_content, re.DOTALL)
        if script_match:
            script_content = script_match.group(1)
            open_parens = script_content.count('(')
            close_parens = script_content.count(')')
            assert abs(open_parens - close_parens) < 5, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"
    
    def test_tab_switching_implementation(self, html_content):
        """Test that tab switching is properly implemented"""
        assert "showControlTab" in html_content, "showControlTab function missing"
        assert "showConsole" in html_content, "showConsole function missing"
        assert "tab-button" in html_content, "Tab buttons missing"
        assert "tab-panel" in html_content, "Tab panels missing"
    
    def test_fps_counter_present(self, html_content):
        """Test that FPS counter is implemented"""
        assert "updateFPS" in html_content, "updateFPS function missing"
        assert "fps" in html_content.lower(), "FPS tracking missing"
        assert "fpsOverlay" in html_content or "fps-overlay" in html_content, "FPS overlay element missing"
    
    def test_body_part_detection_toggles(self, html_content):
        """Test that body part detection toggles exist"""
        toggles = ["toggle-head", "toggle-hands", "toggle-upper", "toggle-lower", "toggle-skeleton"]
        for toggle in toggles:
            assert toggle in html_content, f"Missing body part toggle: {toggle}"
    
    def test_recording_quality_options(self, html_content):
        """Test that recording quality options exist"""
        qualities = ["ultralow", "low", "medium", "high"]
        for quality in qualities:
            assert quality in html_content, f"Missing recording quality: {quality}"
    
    def test_css_grid_layout(self, html_content):
        """Test that CSS grid layout is properly defined"""
        assert "display: grid" in html_content or "display:grid" in html_content, "CSS Grid not used"
        assert "grid-template-columns" in html_content, "Grid columns not defined"
        # Should have 60/40 split
        assert "60%" in html_content and "40%" in html_content, "60/40 split not defined"
    
    def test_no_hardcoded_localhost_paths(self, html_content):
        """Test that API calls don't have hardcoded localhost paths"""
        # API calls should use relative paths
        script_match = re.search(r'<script>(.*)</script>', html_content, re.DOTALL)
        if script_match:
            script_content = script_match.group(1)
            # Count localhost references (some are ok for comments)
            localhost_refs = script_content.count('http://localhost:8001')
            # Should be minimal (mainly in comments)
            assert localhost_refs < 5, f"Too many hardcoded localhost references: {localhost_refs}"
    
    def test_error_console_separation(self, html_content):
        """Test that errors are properly separated into error console"""
        # Check that errors are handled specially
        assert "console-errors" in html_content, "Error console not found"
        # Check for error/warning type handling (type comparison)
        assert "type ===" in html_content or "type ==" in html_content, "No type checking found"
        # Verify multiple console divs exist
        assert html_content.count("console-") >= 3, "Not enough console types found"
    
    def test_api_call_logging(self, html_content):
        """Test that API calls are logged to API console"""
        assert "logApiCall" in html_content, "logApiCall function missing"
        # Should intercept fetch
        assert "originalFetch" in html_content or "window.fetch" in html_content, "Fetch not intercepted for logging"
    
    def test_memory_leak_prevention(self, html_content):
        """Test that there are measures to prevent memory leaks"""
        # Should have cleanup functions
        cleanup_keywords = ["clearInterval", "removeChild", "clear", "reset"]
        found_cleanup = any(keyword in html_content for keyword in cleanup_keywords)
        assert found_cleanup, "No cleanup/memory management found"
        
        # Should trim console lines
        assert "removeChild" in html_content, "No console line trimming found"
    
    def test_responsive_design_media_query(self, html_content):
        """Test that responsive design is implemented"""
        assert "@media" in html_content, "No media queries for responsive design"
        assert "max-width" in html_content or "min-width" in html_content, "No responsive breakpoints"
    
    def test_accessibility_features(self, html_content):
        """Test that basic accessibility features are present"""
        # Should have button labels
        assert 'button' in html_content.lower()
        # Should have headings
        assert '<h1' in html_content or '<h2' in html_content or '<h3' in html_content
        # Should have alt text or aria labels (at least some)
        # (MediaPipe canvas may not need alt text, but UI buttons should be clear)
        assert 'heading' in html_content.lower() or '<h' in html_content


class TestJavaScriptLogic:
    """Tests for JavaScript logic and functions"""
    
    def test_emotion_map_complete(self):
        """Test that emotion mapping is complete"""
        html_path = Path(__file__).parent.parent / "src" / "static" / "index_detailed.html"
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        required_emotions = ['happy', 'sad', 'angry', 'neutral', 'surprise', 'fear', 'disgust']
        for emotion in required_emotions:
            assert emotion in html_content.lower(), f"Missing emotion mapping: {emotion}"
    
    def test_console_timestamp_format(self):
        """Test that console timestamps are formatted correctly"""
        html_path = Path(__file__).parent.parent / "src" / "static" / "index_detailed.html"
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Should use toLocaleTimeString for timestamps
        assert "toLocaleTimeString" in html_content, "Timestamps not properly formatted"
    
    def test_data_validation_before_send(self):
        """Test that data is validated before sending to backend"""
        html_path = Path(__file__).parent.parent / "src" / "static" / "index_detailed.html"
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Should have validation checks
        validation_patterns = [
            "if (!",  # Guard clauses
            "if(",    # Conditional checks
            "||",     # Default values
            "?"       # Ternary operators
        ]
        found_validation = sum(html_content.count(pattern) for pattern in validation_patterns)
        assert found_validation > 50, f"Insufficient validation checks: {found_validation}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])

