"""
Forensics Suite for Route Planning Analysis
Provides tools for incident investigation and audit trail
"""

import json
import time
import hashlib
import traceback
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import datetime as dt
import pickle
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ForensicEvent:
    """Single forensic event in the audit trail"""
    timestamp: str
    event_type: str  # 'input', 'decision', 'output', 'error'
    component: str
    data: Dict[str, Any]
    hash: Optional[str] = None
    
    def calculate_hash(self) -> str:
        """Calculate event hash for integrity"""
        event_str = f"{self.timestamp}:{self.event_type}:{self.component}:{json.dumps(self.data, sort_keys=True)}"
        return hashlib.sha256(event_str.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify event hasn't been tampered with"""
        if not self.hash:
            return True
        return self.hash == self.calculate_hash()


@dataclass
class ForensicSnapshot:
    """Complete system state snapshot"""
    timestamp: str
    route_state: Dict[str, Any]
    traffic_state: List[Dict[str, Any]]
    decisions: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)


class ForensicsRecorder:
    """Records all events for forensic analysis"""
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize forensics recorder.
        
        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id or dt.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.events: List[ForensicEvent] = []
        self.snapshots: List[ForensicSnapshot] = []
        self.start_time = time.time()
        
        logger.info(f"Forensics recorder initialized: {self.session_id}")
    
    def record_event(self, 
                     event_type: str,
                     component: str,
                     data: Dict[str, Any]):
        """
        Record a forensic event.
        
        Args:
            event_type: Type of event
            component: Component that generated event
            data: Event data
        """
        event = ForensicEvent(
            timestamp=dt.datetime.now().isoformat(),
            event_type=event_type,
            component=component,
            data=data
        )
        event.hash = event.calculate_hash()
        
        self.events.append(event)
        
        # Log critical events
        if event_type == 'error':
            logger.error(f"Forensic event: {component} - {data}")
        elif event_type == 'decision':
            logger.info(f"Decision recorded: {component}")
    
    def capture_snapshot(self,
                        route_state: Dict[str, Any],
                        traffic_state: List[Dict[str, Any]] = None,
                        decisions: List[Dict[str, Any]] = None):
        """
        Capture complete system state snapshot.
        
        Args:
            route_state: Current route information
            traffic_state: Traffic vessel states
            decisions: Recent decisions made
        """
        # Calculate performance metrics
        current_time = time.time()
        elapsed = current_time - self.start_time
        event_rate = len(self.events) / elapsed if elapsed > 0 else 0
        
        snapshot = ForensicSnapshot(
            timestamp=dt.datetime.now().isoformat(),
            route_state=route_state,
            traffic_state=traffic_state or [],
            decisions=decisions or [],
            performance_metrics={
                'elapsed_time': elapsed,
                'total_events': len(self.events),
                'event_rate': event_rate,
                'memory_snapshots': len(self.snapshots)
            }
        )
        
        self.snapshots.append(snapshot)
        logger.info(f"Snapshot captured: {len(self.snapshots)} total")
    
    def save_session(self, output_dir: str):
        """
        Save complete forensic session.
        
        Args:
            output_dir: Output directory path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        session_dir = output_path / self.session_id
        session_dir.mkdir(exist_ok=True)
        
        # Save events
        events_file = session_dir / "events.json"
        with open(events_file, 'w') as f:
            events_data = [asdict(e) for e in self.events]
            json.dump(events_data, f, indent=2, default=str)
        
        # Save snapshots
        snapshots_file = session_dir / "snapshots.json"
        with open(snapshots_file, 'w') as f:
            snapshots_data = [s.to_dict() for s in self.snapshots]
            json.dump(snapshots_data, f, indent=2, default=str)
        
        # Save session metadata
        metadata = {
            'session_id': self.session_id,
            'start_time': dt.datetime.fromtimestamp(self.start_time).isoformat(),
            'end_time': dt.datetime.now().isoformat(),
            'total_events': len(self.events),
            'total_snapshots': len(self.snapshots),
            'duration_seconds': time.time() - self.start_time
        }
        
        metadata_file = session_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Forensic session saved to: {session_dir}")
        
        return str(session_dir)


class ForensicsAnalyzer:
    """Analyzes forensic data for incidents and patterns"""
    
    def __init__(self):
        """Initialize forensics analyzer"""
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def load_session(self, session_dir: str) -> Dict[str, Any]:
        """
        Load a forensic session for analysis.
        
        Args:
            session_dir: Session directory path
            
        Returns:
            Session data dictionary
        """
        session_path = Path(session_dir)
        
        # Load metadata
        with open(session_path / "metadata.json", 'r') as f:
            metadata = json.load(f)
        
        # Load events
        with open(session_path / "events.json", 'r') as f:
            events_data = json.load(f)
            events = [ForensicEvent(**e) for e in events_data]
        
        # Load snapshots
        with open(session_path / "snapshots.json", 'r') as f:
            snapshots_data = json.load(f)
        
        session_data = {
            'metadata': metadata,
            'events': events,
            'snapshots': snapshots_data
        }
        
        self.sessions[metadata['session_id']] = session_data
        
        logger.info(f"Loaded session: {metadata['session_id']}")
        
        return session_data
    
    def analyze_incident(self, 
                        session_id: str,
                        incident_time: str,
                        window_seconds: float = 60.0) -> Dict[str, Any]:
        """
        Analyze events around an incident.
        
        Args:
            session_id: Session to analyze
            incident_time: Time of incident (ISO format)
            window_seconds: Time window around incident
            
        Returns:
            Incident analysis report
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not loaded")
        
        session = self.sessions[session_id]
        events = session['events']
        
        # Parse incident time
        incident_dt = dt.datetime.fromisoformat(incident_time)
        
        # Find events in window
        relevant_events = []
        for event in events:
            event_dt = dt.datetime.fromisoformat(event.timestamp)
            time_diff = abs((event_dt - incident_dt).total_seconds())
            
            if time_diff <= window_seconds:
                relevant_events.append({
                    'event': event,
                    'time_diff': time_diff
                })
        
        # Sort by time difference
        relevant_events.sort(key=lambda x: x['time_diff'])
        
        # Analyze event patterns
        analysis = {
            'incident_time': incident_time,
            'window_seconds': window_seconds,
            'events_in_window': len(relevant_events),
            'event_types': {},
            'components_involved': set(),
            'errors': [],
            'decisions': [],
            'timeline': []
        }
        
        for item in relevant_events:
            event = item['event']
            
            # Count event types
            event_type = event.event_type
            analysis['event_types'][event_type] = analysis['event_types'].get(event_type, 0) + 1
            
            # Track components
            analysis['components_involved'].add(event.component)
            
            # Collect errors
            if event.event_type == 'error':
                analysis['errors'].append({
                    'time': event.timestamp,
                    'component': event.component,
                    'error': event.data
                })
            
            # Collect decisions
            if event.event_type == 'decision':
                analysis['decisions'].append({
                    'time': event.timestamp,
                    'component': event.component,
                    'decision': event.data
                })
            
            # Build timeline
            analysis['timeline'].append({
                'time': event.timestamp,
                'type': event.event_type,
                'component': event.component,
                'summary': str(event.data).replace('\n', ' ')[:100]
            })
        
        # Convert set to list for JSON serialization
        analysis['components_involved'] = list(analysis['components_involved'])
        
        return analysis
    
    def verify_integrity(self, session_id: str) -> Dict[str, Any]:
        """
        Verify integrity of all events in a session.
        
        Args:
            session_id: Session to verify
            
        Returns:
            Integrity report
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not loaded")
        
        session = self.sessions[session_id]
        events = session['events']
        
        report = {
            'session_id': session_id,
            'total_events': len(events),
            'verified': 0,
            'failed': 0,
            'corrupted_events': []
        }
        
        for i, event in enumerate(events):
            if event.verify_integrity():
                report['verified'] += 1
            else:
                report['failed'] += 1
                report['corrupted_events'].append({
                    'index': i,
                    'timestamp': event.timestamp,
                    'component': event.component
                })
        
        report['integrity_percentage'] = (report['verified'] / report['total_events'] * 100) if report['total_events'] > 0 else 0
        
        return report
    
    def generate_timeline(self, 
                         session_id: str,
                         start_time: Optional[str] = None,
                         end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Generate event timeline for visualization.
        
        Args:
            session_id: Session to analyze
            start_time: Start of timeline (ISO format)
            end_time: End of timeline (ISO format)
            
        Returns:
            Timeline data for visualization
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not loaded")
        
        session = self.sessions[session_id]
        events = session['events']
        
        timeline = []
        
        for event in events:
            # Filter by time range if specified
            if start_time:
                if event.timestamp < start_time:
                    continue
            if end_time:
                if event.timestamp > end_time:
                    continue
            
            timeline.append({
                'timestamp': event.timestamp,
                'type': event.event_type,
                'component': event.component,
                'data_size': len(str(event.data)),
                'hash': event.hash[:8] if event.hash else None
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def export_evidence_package(self,
                               session_id: str,
                               output_path: str,
                               include_snapshots: bool = True) -> str:
        """
        Export complete evidence package for external analysis.
        
        Args:
            session_id: Session to export
            output_path: Output file path
            include_snapshots: Whether to include snapshots
            
        Returns:
            Path to evidence package
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not loaded")
        
        session = self.sessions[session_id]
        
        # Build evidence package
        package = {
            'export_time': dt.datetime.now().isoformat(),
            'session_id': session_id,
            'metadata': session['metadata'],
            'events': [asdict(e) for e in session['events']],
            'integrity_report': self.verify_integrity(session_id)
        }
        
        if include_snapshots:
            package['snapshots'] = session['snapshots']
        
        # Calculate package hash
        package_str = json.dumps(package, sort_keys=True, default=str)
        package['package_hash'] = hashlib.sha256(package_str.encode()).hexdigest()
        
        # Save package
        with open(output_path, 'w') as f:
            json.dump(package, f, indent=2, default=str)
        
        logger.info(f"Evidence package exported: {output_path}")
        
        return output_path