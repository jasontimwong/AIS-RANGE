# Changelog

All notable changes to this project will be documented in this file.

## [3.3.3] - 2025-01-14

### 🐛 Fixed
- **Route Display Issues**: Fixed new planned routes showing incorrectly on map
- **Route Jump Back**: Resolved routes jumping back to initial state after clicks
- **Data Sync Issues**: Ensured correct route data synchronization through subscription pattern

### 🔧 Changed
- **RouteService Refactoring**: Implemented singleton pattern for unified route data management
  - Added localStorage persistence (24-hour cache)
  - Implemented subscription pattern for automatic component updates
  - Distinguished between user-planned and default routes
- **Component Updates**: 
  - App.tsx subscribes to RouteService for automatic route updates
  - RoutePlanner uses routeService.planRoute()
  - Removed dependency on fixed getRoute() function

### 🗑️ Removed
- Deleted redundant test files (test_route_display.html, test_route_service.html)
- Cleaned up temporary documentation (SOLUTION_DELIVERY.md, ISSUES_DIAGNOSIS.md)

## [3.3.2] - 2025-08-14

### 🎉 Major Updates
- **Dynamic Route Planning Refactoring** - Complete re-planning architecture with unified 50m path granularity

### ✨ Added
- HybridAStar dynamic motion_step configuration support
- Performance benchmark framework (tests/bench/)
- Refactored acceptance test suite
  
### ♻️ Reverted
- Reverted "Frontend core planning service integration (🧮 Planning(Core) button)", temporarily not directly integrating `/plan` in frontend
- Maintained `getEncLite` priority using backend `/enc/lite` strategy (non-breaking)

### 🔧 Changed
- **Path Granularity Optimization**: Reduced from 100m to 50m, 48% precision improvement
- **Architecture Improvement**: Replaced local patching with complete re-planning
- **Performance Optimization**: Single planning replaces dual-path comparison
- **Code Simplification**: Removed redundant _densify_latlon and _stitch_replanned_segments methods

### 📊 Performance Metrics
- Path granularity: 95.9m → 49.9m
- Planning time: <1 second (20 AIS targets)
- Test coverage: All 6 acceptance tests passed

---

**Version**: 3.3.3 - AIS RANGE Maritime Planning System  
**Status**: Production Ready 🚀  
**Updated**: 2025-01-14
