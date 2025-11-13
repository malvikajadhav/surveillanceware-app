"""
Time-Aware A* Trajectory Generator
Adapted for Flask backend
"""

import numpy as np
import logging
from datetime import datetime, timedelta
import heapq
from collections import defaultdict

logger = logging.getLogger(__name__)


class TimeAwareAStarGenerator:
    """
    A* with TIME constraints - arrives at exact end time!
    """
    
    MODE_NAMES = {0: 'WALKING', 1: 'CYCLING', 2: 'TRANSIT', 3: 'DRIVING', 4: 'HIGH_SPEED'}
    
    def __init__(self, user_transitions, global_transitions, initial_distribution, state_space,
                 cell_size_km=0.16, grid_size=100):
        self.user_transitions = user_transitions
        self.global_transitions = global_transitions
        self.initial_distribution = initial_distribution
        self.state_space = state_space
        self.cell_size_km = cell_size_km
        self.grid_size = grid_size
        
        # Build cell index
        self.user_cells = defaultdict(set)
        for user_id, user_matrix in self.user_transitions.items():
            for (cell, period, mode) in user_matrix.keys():
                self.user_cells[user_id].add(cell)
        
        logger.info(f"Generator initialized with {len(self.user_transitions)} users")
    
    def lat_lon_to_cell(self, lat, lon, centroid_lat=39.9075, centroid_lon=116.3972, radius_km=8.0):
        """Convert lat/lon to cell"""
        lat_per_km = 1 / 111.0
        lon_per_km = 1 / (111.0 * np.cos(np.radians(centroid_lat)))
        
        min_lat = centroid_lat - radius_km * lat_per_km
        min_lon = centroid_lon - radius_km * lon_per_km
        
        cell_size_lat = (2 * radius_km * lat_per_km) / self.grid_size
        cell_size_lon = (2 * radius_km * lon_per_km) / self.grid_size
        
        lat_idx = int((lat - min_lat) / cell_size_lat)
        lon_idx = int((lon - min_lon) / cell_size_lon)
        
        if 0 <= lat_idx < self.grid_size and 0 <= lon_idx < self.grid_size:
            return lat_idx * self.grid_size + lon_idx
        return -1
    
    def cell_to_lat_lon(self, cell_id, centroid_lat=39.9075, centroid_lon=116.3972, radius_km=8.0):
        """Convert cell to lat/lon"""
        lat_per_km = 1 / 111.0
        lon_per_km = 1 / (111.0 * np.cos(np.radians(centroid_lat)))
        
        min_lat = centroid_lat - radius_km * lat_per_km
        min_lon = centroid_lon - radius_km * lon_per_km
        
        cell_size_lat = (2 * radius_km * lat_per_km) / self.grid_size
        cell_size_lon = (2 * radius_km * lon_per_km) / self.grid_size
        
        lat_idx = cell_id // self.grid_size
        lon_idx = cell_id % self.grid_size
        
        lat = min_lat + (lat_idx + 0.5) * cell_size_lat
        lon = min_lon + (lon_idx + 0.5) * cell_size_lon
        
        return lat, lon
    
    def timestamp_to_period(self, timestamp):
        """Convert timestamp to period"""
        hour = timestamp.hour
        if 5 <= hour < 7: return 0
        elif 7 <= hour < 10: return 1
        elif 10 <= hour < 12: return 2
        elif 12 <= hour < 14: return 3
        elif 14 <= hour < 17: return 4
        elif 17 <= hour < 20: return 5
        elif 20 <= hour < 23: return 6
        else: return 7
    
    def manhattan_distance(self, cell1, cell2):
        """Spatial distance"""
        row1, col1 = cell1 // self.grid_size, cell1 % self.grid_size
        row2, col2 = cell2 // self.grid_size, cell2 % self.grid_size
        return abs(row1 - row2) + abs(col1 - col2)
    
    def period_distance(self, period1, period2):
        """Time distance in periods"""
        if period2 >= period1:
            return period2 - period1
        else:
            return (8 - period1) + period2
    
    def get_neighbors(self, state, user_id):
        """Get neighboring states from transition matrix"""
        cell, period, mode = state
        
        # Try user transitions
        if user_id in self.user_transitions:
            if state in self.user_transitions[user_id]:
                return self.user_transitions[user_id][state]
        
        # Try global
        if state in self.global_transitions:
            return self.global_transitions[state]
        
        # Generate neighbors
        neighbors = {}
        row, col = cell // self.grid_size, cell % self.grid_size
        
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < self.grid_size and 0 <= new_col < self.grid_size:
                    new_cell = new_row * self.grid_size + new_col
                    neighbors[(new_cell, period, mode)] = 0.1
                    next_period = (period + 1) % 8
                    neighbors[(new_cell, next_period, mode)] = 0.05
        
        next_period = (period + 1) % 8
        neighbors[(cell, next_period, mode)] = 0.2
        
        total = sum(neighbors.values())
        if total > 0:
            neighbors = {s: p/total for s, p in neighbors.items()}
        
        return neighbors
    
    def astar_search(self, start_state, goal_cell, goal_period, user_id, max_iterations=1000):
        """A* search with time constraint"""
        start_cell, start_period, start_mode = start_state
        
        open_set = []
        heapq.heappush(open_set, (0, 0, start_state))
        
        came_from = {}
        g_score = {start_state: 0}
        
        def heuristic(state):
            cell, period, mode = state
            spatial_dist = self.manhattan_distance(cell, goal_cell)
            time_dist = self.period_distance(period, goal_period)
            return spatial_dist + time_dist * 3
        
        visited = set()
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            _, current_g, current_state = heapq.heappop(open_set)
            current_cell, current_period, current_mode = current_state
            
            if current_cell == goal_cell and current_period == goal_period:
                path = []
                state = current_state
                while state in came_from:
                    path.append(state)
                    state = came_from[state]
                path.append(start_state)
                path.reverse()
                return path
            
            if current_state in visited:
                continue
            
            visited.add(current_state)
            
            neighbors = self.get_neighbors(current_state, user_id)
            
            for next_state, transition_prob in neighbors.items():
                if next_state in visited:
                    continue
                
                cost = -np.log(max(transition_prob, 1e-10))
                tentative_g = current_g + cost
                
                if next_state not in g_score or tentative_g < g_score[next_state]:
                    came_from[next_state] = current_state
                    g_score[next_state] = tentative_g
                    f_score = tentative_g + heuristic(next_state)
                    heapq.heappush(open_set, (f_score, tentative_g, next_state))
        
        return self._fallback_path(start_state, goal_cell, goal_period)
    
    def _fallback_path(self, start_state, goal_cell, goal_period):
        """Fallback if A* fails"""
        start_cell, start_period, start_mode = start_state
        
        spatial_dist = self.manhattan_distance(start_cell, goal_cell)
        time_dist = self.period_distance(start_period, goal_period)
        
        num_steps = max(spatial_dist, time_dist, 5) + 1
        path = []
        
        for i in range(num_steps):
            t = i / (num_steps - 1) if num_steps > 1 else 1
            
            start_row, start_col = start_cell // self.grid_size, start_cell % self.grid_size
            goal_row, goal_col = goal_cell // self.grid_size, goal_cell % self.grid_size
            
            row = int(start_row + t * (goal_row - start_row))
            col = int(start_col + t * (goal_col - start_col))
            cell = row * self.grid_size + col
            
            periods_forward = self.period_distance(start_period, goal_period)
            period = (start_period + int(t * periods_forward)) % 8
            
            path.append((cell, period, start_mode))
        
        return path
    
    def calculate_confidence_score(self, path, start_cell, end_cell, user_id):
        """Calculate confidence"""
        if user_id not in self.user_cells:
            return {
                'score': 0.3,
                'level': 'low',
                'warning': '⚠️ User not in database',
                'message': 'This user has no historical data. Prediction is based on global patterns.',
                'reasons': ['User has no historical data']
            }
        
        known_cells = self.user_cells[user_id]
        cells_in_path = set([s[0] for s in path])
        
        start_known = start_cell in known_cells
        end_known = end_cell in known_cells
        coverage = len(cells_in_path.intersection(known_cells)) / len(cells_in_path) if cells_in_path else 0
        
        confidence = 0.4 * coverage + 0.3 * start_known + 0.3 * end_known
        
        if confidence > 0.7:
            level = 'high'
            warning = None
            message = None
        elif confidence > 0.4:
            level = 'medium'
            warning = 'Moderate Confidence'
            message = 'Some parts of this route are unfamiliar to this user.'
        else:
            level = 'low'
            warning = '⚠️ Low Confidence'
            message = 'This route is largely unfamiliar. Prediction may be inaccurate.'
        
        return {
            'score': float(confidence),
            'level': level,
            'warning': warning,
            'message': message,
            'reasons': [
                f"Start point {'known' if start_known else 'unknown'}",
                f"End point {'known' if end_known else 'unknown'}",
                f"Route coverage: {coverage*100:.0f}%"
            ]
        }
    
    def generate_trajectory(self, start_lat, start_lon, end_lat, end_lon,
                          start_time, end_time, user_id=None):
        """Generate single trajectory"""
        
        start_cell = self.lat_lon_to_cell(start_lat, start_lon)
        end_cell = self.lat_lon_to_cell(end_lat, end_lon)
        
        if start_cell == -1 or end_cell == -1:
            raise ValueError("Location outside grid boundaries")
        
        start_period = self.timestamp_to_period(start_time)
        end_period = self.timestamp_to_period(end_time)
        
        start_state = (start_cell, start_period, 0)  # Default to WALKING
        
        # Generate path
        path = self.astar_search(start_state, end_cell, end_period, user_id)
        
        if len(path) == 0:
            raise ValueError("Could not generate valid path")
        
        # Convert to trajectory points
        trajectory_data = []
        time_delta = (end_time - start_time) / max(len(path) - 1, 1)
        
        for i, (cell, period, mode) in enumerate(path):
            lat, lon = self.cell_to_lat_lon(cell)
            timestamp = start_time + time_delta * i
            
            # Calculate speed
            speed = 0
            if i > 0:
                prev_cell = path[i-1][0]
                distance_km = self.manhattan_distance(prev_cell, cell) * self.cell_size_km
                time_hrs = time_delta.total_seconds() / 3600
                if time_hrs > 0:
                    speed = distance_km / time_hrs
            
            trajectory_data.append({
                'lat': float(lat),
                'lon': float(lon),
                'speed': float(speed),
                'timestamp': timestamp.isoformat()
            })
        
        # Calculate confidence
        confidence = self.calculate_confidence_score(path, start_cell, end_cell, user_id)
        
        # Calculate metadata
        total_distance = sum(
            self.manhattan_distance(path[i-1][0], path[i][0]) * self.cell_size_km
            for i in range(1, len(path))
        )
        
        return {
            'trajectory': trajectory_data,
            'confidence': confidence,
            'metadata': {
                'distance_km': f"{total_distance:.2f}",
                'num_points': len(trajectory_data)
            }
        }