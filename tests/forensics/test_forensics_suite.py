"""
Tests for forensics suite
"""

import pytest
import json
import tempfile
from pathlib import Path
import datetime as dt
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.forensics.forensics_suite import (
    ForensicEvent,
    ForensicSnapshot,
    ForensicsRecorder,
    ForensicsAnalyzer
)


class TestForensicEvent:
    """Test ForensicEvent class"""
    
    def test_event_creation(self):
        """Test creating forensic event"""
        event = ForensicEvent(
            timestamp="2025-01-01T10:00:00",
            event_type="decision",
            component="route_planner",
            data={'action': 'turn_left', 'angle': 30}
        )
        
        assert event.event_type == "decision"
        assert event.component == "route_planner"
        assert event.data['action'] == 'turn_left'
    
    def test_event_hash_calculation(self):
        """Test event hash calculation"""
        event = ForensicEvent(
            timestamp="2025-01-01T10:00:00",
            event_type="input",
            component="sensor",
            data={'value': 42}
        )
        
        hash1 = event.calculate_hash()
        assert hash1 is not None
        assert len(hash1) == 64  # SHA256 hex length
        
        # Same data should give same hash
        hash2 = event.calculate_hash()
        assert hash1 == hash2
    
    def test_event_integrity_verification(self):
        """Test event integrity verification"""
        event = ForensicEvent(
            timestamp="2025-01-01T10:00:00",
            event_type="output",
            component="executor",
            data={'result': 'success'}
        )
        
        # No hash should pass
        assert event.verify_integrity() == True
        
        # Correct hash should pass
        event.hash = event.calculate_hash()
        assert event.verify_integrity() == True
        
        # Modified hash should fail
        event.hash = "tampered_hash"
        assert event.verify_integrity() == False


class TestForensicSnapshot:
    """Test ForensicSnapshot class"""
    
    def test_snapshot_creation(self):
        """Test creating forensic snapshot"""
        snapshot = ForensicSnapshot(
            timestamp="2025-01-01T10:00:00",
            route_state={'waypoints': [{'lat': 0, 'lon': 0}]},
            traffic_state=[{'id': 'VESSEL001'}],
            decisions=[{'type': 'avoidance'}],
            performance_metrics={'cpu': 50.0, 'memory': 1024.0}
        )
        
        assert snapshot.timestamp == "2025-01-01T10:00:00"
        assert len(snapshot.route_state['waypoints']) == 1
        assert len(snapshot.traffic_state) == 1
    
    def test_snapshot_to_dict(self):
        """Test converting snapshot to dict"""
        snapshot = ForensicSnapshot(
            timestamp="2025-01-01T10:00:00",
            route_state={'status': 'active'},
            traffic_state=[],
            decisions=[],
            performance_metrics={'latency': 0.1}
        )
        
        snapshot_dict = snapshot.to_dict()
        
        assert snapshot_dict['timestamp'] == "2025-01-01T10:00:00"
        assert snapshot_dict['route_state']['status'] == 'active'
        assert snapshot_dict['performance_metrics']['latency'] == 0.1


class TestForensicsRecorder:
    """Test ForensicsRecorder class"""
    
    def test_recorder_initialization(self):
        """Test recorder initialization"""
        recorder = ForensicsRecorder(session_id="TEST_SESSION")
        
        assert recorder.session_id == "TEST_SESSION"
        assert recorder.events == []
        assert recorder.snapshots == []
    
    def test_record_event(self):
        """Test recording events"""
        recorder = ForensicsRecorder()
        
        # Record various event types
        recorder.record_event("input", "sensor", {'reading': 100})
        recorder.record_event("decision", "planner", {'action': 'continue'})
        recorder.record_event("error", "executor", {'error': 'timeout'})
        
        assert len(recorder.events) == 3
        assert recorder.events[0].event_type == "input"
        assert recorder.events[1].event_type == "decision"
        assert recorder.events[2].event_type == "error"
        
        # All events should have hashes
        for event in recorder.events:
            assert event.hash is not None
    
    def test_capture_snapshot(self):
        """Test capturing snapshots"""
        recorder = ForensicsRecorder()
        
        # Add some events first
        recorder.record_event("input", "test", {'data': 1})
        
        # Capture snapshot
        recorder.capture_snapshot(
            route_state={'position': {'lat': 10, 'lon': 20}},
            traffic_state=[{'id': 'V001', 'speed': 15}],
            decisions=[{'type': 'maintain_course'}]
        )
        
        assert len(recorder.snapshots) == 1
        
        snapshot = recorder.snapshots[0]
        assert snapshot.route_state['position']['lat'] == 10
        assert len(snapshot.traffic_state) == 1
        assert snapshot.performance_metrics['total_events'] == 1
    
    def test_save_session(self, tmp_path):
        """Test saving forensic session"""
        recorder = ForensicsRecorder(session_id="SAVE_TEST")
        
        # Add some data
        recorder.record_event("input", "test1", {'value': 1})
        recorder.record_event("output", "test2", {'value': 2})
        
        recorder.capture_snapshot(
            route_state={'status': 'running'},
            traffic_state=[],
            decisions=[]
        )
        
        # Save session
        session_dir = recorder.save_session(str(tmp_path))
        
        # Check files exist
        session_path = Path(session_dir)
        assert session_path.exists()
        assert (session_path / "events.json").exists()
        assert (session_path / "snapshots.json").exists()
        assert (session_path / "metadata.json").exists()
        
        # Verify metadata
        with open(session_path / "metadata.json", 'r') as f:
            metadata = json.load(f)
        
        assert metadata['session_id'] == "SAVE_TEST"
        assert metadata['total_events'] == 2
        assert metadata['total_snapshots'] == 1


class TestForensicsAnalyzer:
    """Test ForensicsAnalyzer class"""
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        analyzer = ForensicsAnalyzer()
        
        assert analyzer.sessions == {}
    
    def test_load_session(self, tmp_path):
        """Test loading forensic session"""
        # Create a session to load
        recorder = ForensicsRecorder(session_id="LOAD_TEST")
        recorder.record_event("test", "component", {'data': 'test'})
        session_dir = recorder.save_session(str(tmp_path))
        
        # Load with analyzer
        analyzer = ForensicsAnalyzer()
        session_data = analyzer.load_session(session_dir)
        
        assert session_data['metadata']['session_id'] == "LOAD_TEST"
        assert len(session_data['events']) == 1
        assert "LOAD_TEST" in analyzer.sessions
    
    def test_analyze_incident(self, tmp_path):
        """Test incident analysis"""
        # Create session with events around incident
        recorder = ForensicsRecorder(session_id="INCIDENT_TEST")
        
        base_time = dt.datetime(2025, 1, 1, 10, 0, 0)
        
        # Events before incident
        recorder.events.append(ForensicEvent(
            timestamp=(base_time - dt.timedelta(seconds=30)).isoformat(),
            event_type="input",
            component="sensor",
            data={'normal': True}
        ))
        
        # Incident event
        recorder.events.append(ForensicEvent(
            timestamp=base_time.isoformat(),
            event_type="error",
            component="planner",
            data={'error': 'collision_risk'}
        ))
        
        # Events after incident
        recorder.events.append(ForensicEvent(
            timestamp=(base_time + dt.timedelta(seconds=10)).isoformat(),
            event_type="decision",
            component="planner",
            data={'action': 'emergency_stop'}
        ))
        
        session_dir = recorder.save_session(str(tmp_path))
        
        # Analyze incident
        analyzer = ForensicsAnalyzer()
        analyzer.load_session(session_dir)
        
        analysis = analyzer.analyze_incident(
            "INCIDENT_TEST",
            base_time.isoformat(),
            window_seconds=60.0
        )
        
        assert analysis['events_in_window'] == 3
        assert 'error' in analysis['event_types']
        assert 'planner' in analysis['components_involved']
        assert len(analysis['errors']) == 1
        assert len(analysis['timeline']) == 3
    
    def test_verify_integrity(self, tmp_path):
        """Test integrity verification"""
        # Create session with valid hashes
        recorder = ForensicsRecorder(session_id="INTEGRITY_TEST")
        
        # Add events with hashes
        for i in range(5):
            recorder.record_event("test", f"comp_{i}", {'value': i})
        
        session_dir = recorder.save_session(str(tmp_path))
        
        # Verify integrity
        analyzer = ForensicsAnalyzer()
        analyzer.load_session(session_dir)
        
        report = analyzer.verify_integrity("INTEGRITY_TEST")
        
        assert report['total_events'] == 5
        assert report['verified'] == 5
        assert report['failed'] == 0
        assert report['integrity_percentage'] == 100.0
    
    def test_generate_timeline(self, tmp_path):
        """Test timeline generation"""
        # Create session with events
        recorder = ForensicsRecorder(session_id="TIMELINE_TEST")
        
        base_time = dt.datetime(2025, 1, 1, 10, 0, 0)
        
        for i in range(10):
            recorder.events.append(ForensicEvent(
                timestamp=(base_time + dt.timedelta(seconds=i*10)).isoformat(),
                event_type="input" if i % 2 == 0 else "output",
                component=f"comp_{i}",
                data={'index': i},
                hash=f"hash_{i}"
            ))
        
        session_dir = recorder.save_session(str(tmp_path))
        
        # Generate timeline
        analyzer = ForensicsAnalyzer()
        analyzer.load_session(session_dir)
        
        timeline = analyzer.generate_timeline("TIMELINE_TEST")
        
        assert len(timeline) == 10
        assert timeline[0]['timestamp'] < timeline[-1]['timestamp']
        
        # Test with time range
        start_time = (base_time + dt.timedelta(seconds=20)).isoformat()
        end_time = (base_time + dt.timedelta(seconds=60)).isoformat()
        
        filtered_timeline = analyzer.generate_timeline(
            "TIMELINE_TEST",
            start_time=start_time,
            end_time=end_time
        )
        
        assert len(filtered_timeline) < 10
    
    def test_export_evidence_package(self, tmp_path):
        """Test evidence package export"""
        # Create session
        recorder = ForensicsRecorder(session_id="EVIDENCE_TEST")
        recorder.record_event("test", "component", {'evidence': 'data'})
        recorder.capture_snapshot({'route': 'active'}, [], [])
        
        session_dir = recorder.save_session(str(tmp_path))
        
        # Export evidence
        analyzer = ForensicsAnalyzer()
        analyzer.load_session(session_dir)
        
        export_file = tmp_path / "evidence.json"
        result = analyzer.export_evidence_package(
            "EVIDENCE_TEST",
            str(export_file),
            include_snapshots=True
        )
        
        assert export_file.exists()
        
        # Verify package
        with open(export_file, 'r') as f:
            package = json.load(f)
        
        assert package['session_id'] == "EVIDENCE_TEST"
        assert 'events' in package
        assert 'snapshots' in package
        assert 'integrity_report' in package
        assert 'package_hash' in package