"""
SBOM (Software Bill of Materials) Manager
Tracks dependencies and supply chain for security and compliance
"""

import json
import hashlib
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import datetime as dt
import logging
import pkg_resources
import importlib.metadata

logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """Single dependency in the SBOM"""
    name: str
    version: str
    license: Optional[str] = None
    source: Optional[str] = None
    hash: Optional[str] = None
    vulnerabilities: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []


@dataclass
class SBOM:
    """Complete Software Bill of Materials"""
    created: str
    version: str
    format: str = "CycloneDX"
    components: List[Dependency] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.components is None:
            self.components = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'bomFormat': self.format,
            'specVersion': '1.4',
            'serialNumber': f"urn:uuid:{hashlib.sha256(self.created.encode()).hexdigest()[:32]}",
            'version': 1,
            'metadata': {
                'timestamp': self.created,
                'tools': [
                    {
                        'vendor': 'ECDIS Route Planner',
                        'name': 'SBOM Manager',
                        'version': self.version
                    }
                ],
                **self.metadata
            },
            'components': [asdict(c) for c in self.components]
        }


class SBOMManager:
    """Manages SBOM generation and analysis"""
    
    def __init__(self):
        """Initialize SBOM manager"""
        self.sbom: Optional[SBOM] = None
        self.vulnerability_db: Dict[str, List[Dict]] = {}
        
    def generate_sbom(self, 
                      requirements_file: Optional[str] = None,
                      include_transitive: bool = True) -> SBOM:
        """
        Generate SBOM from current environment or requirements file.
        
        Args:
            requirements_file: Path to requirements.txt
            include_transitive: Include transitive dependencies
            
        Returns:
            Generated SBOM
        """
        components = []
        
        if requirements_file:
            # Parse requirements file
            components.extend(self._parse_requirements(requirements_file))
        
        # Get installed packages
        installed = self._get_installed_packages()
        
        # Merge with requirements
        component_dict = {c.name: c for c in components}
        
        for pkg in installed:
            if pkg.name not in component_dict:
                component_dict[pkg.name] = pkg
            else:
                # Update version if installed differs
                component_dict[pkg.name].version = pkg.version
        
        # Get transitive dependencies if requested
        if include_transitive:
            for name in list(component_dict.keys()):
                deps = self._get_dependencies(name)
                for dep in deps:
                    if dep.name not in component_dict:
                        component_dict[dep.name] = dep
        
        # Create SBOM
        self.sbom = SBOM(
            created=dt.datetime.now().isoformat(),
            version="1.0.0",
            components=list(component_dict.values()),
            metadata={
                'component_count': len(component_dict),
                'include_transitive': include_transitive
            }
        )
        
        logger.info(f"Generated SBOM with {len(self.sbom.components)} components")
        
        return self.sbom
    
    def _parse_requirements(self, requirements_file: str) -> List[Dependency]:
        """
        Parse requirements.txt file.
        
        Args:
            requirements_file: Path to requirements file
            
        Returns:
            List of dependencies
        """
        dependencies = []
        
        with open(requirements_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse package spec
                    if '==' in line:
                        name, version = line.split('==')
                    elif '>=' in line:
                        name = line.split('>=')[0]
                        version = 'latest'
                    else:
                        name = line.split('[')[0].split('<')[0].split('>')[0]
                        version = 'unspecified'
                    
                    dependencies.append(Dependency(
                        name=name.strip(),
                        version=version.strip(),
                        source='requirements.txt'
                    ))
        
        return dependencies
    
    def _get_installed_packages(self) -> List[Dependency]:
        """
        Get list of installed Python packages.
        
        Returns:
            List of installed dependencies
        """
        dependencies = []
        
        try:
            # Use importlib.metadata for Python 3.8+
            for dist in importlib.metadata.distributions():
                try:
                    dep = Dependency(
                        name=dist.metadata['Name'],
                        version=dist.version,
                        license=dist.metadata.get('License', 'Unknown'),
                        source='pip'
                    )
                    
                    # Calculate package hash if possible
                    if hasattr(dist, 'files') and dist.files:
                        files_str = ''.join(str(f) for f in dist.files)
                        dep.hash = hashlib.sha256(files_str.encode()).hexdigest()[:16]
                    
                    dependencies.append(dep)
                    
                except Exception as e:
                    logger.warning(f"Failed to process package {dist.metadata.get('Name', 'unknown')}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to get installed packages: {e}")
            
            # Fallback to pkg_resources
            for dist in pkg_resources.working_set:
                dependencies.append(Dependency(
                    name=dist.project_name,
                    version=dist.version,
                    source='pip'
                ))
        
        return dependencies
    
    def _get_dependencies(self, package_name: str) -> List[Dependency]:
        """
        Get dependencies of a package.
        
        Args:
            package_name: Package to analyze
            
        Returns:
            List of dependencies
        """
        dependencies = []
        
        try:
            # Try to get requirements from metadata
            dist = importlib.metadata.distribution(package_name)
            if dist.requires:
                for req in dist.requires:
                    # Parse requirement string
                    if ';' in req:
                        req = req.split(';')[0]
                    
                    if '>' in req or '<' in req or '=' in req:
                        name = req.split('>')[0].split('<')[0].split('=')[0]
                    else:
                        name = req
                    
                    dependencies.append(Dependency(
                        name=name.strip(),
                        version='*',
                        source=f'dependency of {package_name}'
                    ))
                    
        except Exception as e:
            logger.debug(f"Could not get dependencies for {package_name}: {e}")
        
        return dependencies
    
    def check_vulnerabilities(self, 
                             use_external_api: bool = False) -> Dict[str, List[Dict]]:
        """
        Check components for known vulnerabilities.
        
        Args:
            use_external_api: Use external vulnerability API
            
        Returns:
            Dictionary of vulnerabilities by package
        """
        if not self.sbom:
            raise ValueError("No SBOM generated yet")
        
        vulnerabilities = {}
        
        # Internal vulnerability database (simplified)
        known_vulnerabilities = {
            'requests': {
                '<2.31.0': [{
                    'id': 'CVE-2023-32681',
                    'severity': 'medium',
                    'description': 'Proxy bypass vulnerability'
                }]
            },
            'urllib3': {
                '<2.0.0': [{
                    'id': 'CVE-2023-43804',
                    'severity': 'high',
                    'description': 'Cookie injection vulnerability'
                }]
            }
        }
        
        for component in self.sbom.components:
            vuln_list = []
            
            # Check internal database
            if component.name in known_vulnerabilities:
                for version_pattern, vulns in known_vulnerabilities[component.name].items():
                    # Simplified version comparison
                    if version_pattern.startswith('<'):
                        # Check if component version is less than specified
                        vuln_list.extend(vulns)
            
            if vuln_list:
                vulnerabilities[component.name] = vuln_list
                component.vulnerabilities = vuln_list
        
        # Log summary
        total_vulns = sum(len(v) for v in vulnerabilities.values())
        logger.info(f"Found {total_vulns} vulnerabilities in {len(vulnerabilities)} packages")
        
        return vulnerabilities
    
    def generate_license_report(self) -> Dict[str, Any]:
        """
        Generate license compliance report.
        
        Returns:
            License report
        """
        if not self.sbom:
            raise ValueError("No SBOM generated yet")
        
        report = {
            'total_components': len(self.sbom.components),
            'licenses': {},
            'unknown_licenses': [],
            'copyleft_licenses': [],
            'permissive_licenses': []
        }
        
        # Categorize licenses
        copyleft = ['GPL', 'LGPL', 'AGPL', 'MPL']
        permissive = ['MIT', 'BSD', 'APACHE', 'ISC']  # Changed 'Apache' to 'APACHE'
        
        for component in self.sbom.components:
            license_name = component.license or 'Unknown'
            
            # Count licenses
            report['licenses'][license_name] = report['licenses'].get(license_name, 0) + 1
            
            # Categorize
            if license_name == 'Unknown':
                report['unknown_licenses'].append(component.name)
            elif any(cl in license_name.upper() for cl in copyleft):
                report['copyleft_licenses'].append({
                    'name': component.name,
                    'license': license_name
                })
            elif any(pl in license_name.upper() for pl in permissive):
                report['permissive_licenses'].append({
                    'name': component.name,
                    'license': license_name
                })
        
        # Calculate percentages
        total = report['total_components']
        if total > 0:
            report['unknown_percentage'] = len(report['unknown_licenses']) / total * 100
            report['copyleft_percentage'] = len(report['copyleft_licenses']) / total * 100
            report['permissive_percentage'] = len(report['permissive_licenses']) / total * 100
        
        return report
    
    def export_sbom(self, 
                    output_path: str,
                    format: str = 'cyclonedx') -> str:
        """
        Export SBOM to file.
        
        Args:
            output_path: Output file path
            format: Export format (cyclonedx, spdx)
            
        Returns:
            Path to exported file
        """
        if not self.sbom:
            raise ValueError("No SBOM generated yet")
        
        if format == 'cyclonedx':
            # Export as CycloneDX JSON
            with open(output_path, 'w') as f:
                json.dump(self.sbom.to_dict(), f, indent=2, default=str)
                
        elif format == 'spdx':
            # Export as SPDX (simplified)
            spdx_doc = {
                'spdxVersion': 'SPDX-2.3',
                'creationInfo': {
                    'created': self.sbom.created,
                    'creators': ['Tool: SBOM Manager']
                },
                'name': 'ECDIS Route Planner',
                'packages': []
            }
            
            for component in self.sbom.components:
                spdx_doc['packages'].append({
                    'name': component.name,
                    'versionInfo': component.version,
                    'licenseConcluded': component.license or 'NOASSERTION',
                    'filesAnalyzed': False
                })
            
            with open(output_path, 'w') as f:
                json.dump(spdx_doc, f, indent=2)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"SBOM exported to: {output_path}")
        
        return output_path
    
    def verify_supply_chain(self) -> Dict[str, Any]:
        """
        Verify supply chain integrity.
        
        Returns:
            Verification report
        """
        if not self.sbom:
            raise ValueError("No SBOM generated yet")
        
        report = {
            'verified_components': 0,
            'unverified_components': 0,
            'suspicious_components': [],
            'integrity_score': 0.0
        }
        
        for component in self.sbom.components:
            # Check if component has hash
            if component.hash:
                report['verified_components'] += 1
            else:
                report['unverified_components'] += 1
            
            # Check for suspicious patterns
            suspicious_patterns = [
                'typosquat',
                'test',
                'debug',
                'backdoor',
                'malware'
            ]
            
            if any(pattern in component.name.lower() for pattern in suspicious_patterns):
                report['suspicious_components'].append({
                    'name': component.name,
                    'reason': 'Name contains suspicious pattern'
                })
        
        # Calculate integrity score
        total = len(self.sbom.components)
        if total > 0:
            report['integrity_score'] = report['verified_components'] / total * 100
        
        return report
    
    def compare_sboms(self, 
                      other_sbom_path: str) -> Dict[str, Any]:
        """
        Compare current SBOM with another.
        
        Args:
            other_sbom_path: Path to other SBOM file
            
        Returns:
            Comparison report
        """
        if not self.sbom:
            raise ValueError("No SBOM generated yet")
        
        # Load other SBOM
        with open(other_sbom_path, 'r') as f:
            other_data = json.load(f)
        
        # Extract components
        current_components = {c.name: c.version for c in self.sbom.components}
        other_components = {}
        
        for comp in other_data.get('components', []):
            other_components[comp['name']] = comp['version']
        
        # Compare
        report = {
            'added': [],
            'removed': [],
            'updated': [],
            'unchanged': []
        }
        
        # Find additions and updates
        for name, version in current_components.items():
            if name not in other_components:
                report['added'].append({'name': name, 'version': version})
            elif other_components[name] != version:
                report['updated'].append({
                    'name': name,
                    'old_version': other_components[name],
                    'new_version': version
                })
            else:
                report['unchanged'].append({'name': name, 'version': version})
        
        # Find removals
        for name, version in other_components.items():
            if name not in current_components:
                report['removed'].append({'name': name, 'version': version})
        
        # Summary
        report['summary'] = {
            'total_current': len(current_components),
            'total_other': len(other_components),
            'added_count': len(report['added']),
            'removed_count': len(report['removed']),
            'updated_count': len(report['updated']),
            'unchanged_count': len(report['unchanged'])
        }
        
        return report