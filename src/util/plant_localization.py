#! /usr/bin/env python

import sys
import math

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.data.field_item import Plant
from src.processing.item_processing import lateral_and_projection_distance_2d, projection_to_position_2d
from src.processing.item_processing import position_difference
from src.util.clustering import corner_rectangle_size

class SegmentPart:
    
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.possible_plants = None
        self.expected_projections = None
    
    @property
    def length(self):
        dx = self.start.position[0] - self.end.position[0]
        dy = self.start.position[1] - self.end.position[1]
        return math.sqrt(dx*dx + dy*dy) 
        
class RecursiveSplitPlantFilter:
    
    def __init__(self, code_spacing, plant_spacing, lateral_ps=1, projection_ps=1,
                 closeness_ps=1, stick_multiplier=2, leaf_multiplier=1.5):
        '''Spacing distances (in centimeters) are expected values'''
        self.expected_code_spacing = code_spacing
        self.expected_plant_spacing = plant_spacing
        
        self.closest_code_spacing = code_spacing / 2.0
        self.closest_plant_spacing = plant_spacing / 2.0
        
        self.num_successfully_found_plants = 0
        self.num_created_because_no_plants = 0
        self.num_created_because_no_valid_plants = 0
        
        # Scales to weight the importance of different penalties
        self.lateral_penalty_scale = lateral_ps
        self.projection_penalty_scale = projection_ps
        self.closeness_penalty_scale = closeness_ps
        self.stick_multiplier = max(1, stick_multiplier)
        self.leaf_multiplier = max(1, leaf_multiplier)
        
    def locate_actual_plants_in_segment(self, possible_plants, whole_segment):
    
        whole_part = SegmentPart(whole_segment.start_code, whole_segment.end_code)
        whole_part.possible_plants = possible_plants
    
        sub_parts = self.split_into_subparts(whole_part)
        
        actual_plants = []
        for part in sub_parts:
            # Add start of segment part.  Don't add the end since it should be the start of the next part,
            # and the last part the end item is a code so we don't want to add that either.
            if part.start.type.lower() == 'plant':
                actual_plants.append(part.start)
                
        assert('code' in sub_parts[-1].end.type.lower())
             
        return actual_plants
    
    def split_into_subparts(self, segment_part):
    
        split_segment_parts = self.process_segment_part(segment_part)
        
        all_segment_parts = []
        if len(split_segment_parts) == 0:
            # Can't split segment part up into smaller parts.
            all_segment_parts.append(segment_part)
        else:
            for split_part in split_segment_parts:
                all_segment_parts += self.split_into_subparts(split_part)
        
        return all_segment_parts
    
    def process_segment_part(self, segment_part):
        
        segment_part.expected_projections = self.calculate_expected_positions(segment_part)
        
        if len(segment_part.expected_projections) == 0:
            # Segment part is too short to contain more plants so don't split it up any more.
            return []
        
        # Remove any plants that don't fall within the valid range of the segment part.
        segment_part.possible_plants = self.filter_plants_by_segment_part(segment_part)

        if len(segment_part.possible_plants) == 0:
            # No plants to select from so just create a plant where one is most likely to be.
            selected_plant = self.create_closest_plant(segment_part)
            self.num_created_because_no_plants += 1
        else:
            # Figure out which possible plant is most likely to be an actual plant.
            selected_plant = self.find_most_likely_plant(segment_part)
            if selected_plant is None:
                # None of the possible plants worked out so fall back on closest expected plant.
                selected_plant = self.create_closest_plant(segment_part)
                self.num_created_because_no_valid_plants += 1

        first_subpart = SegmentPart(start=segment_part.start, end=selected_plant)
        second_subpart = SegmentPart(start=selected_plant, end=segment_part.end)
        
        before_plants, after_plants = self.split_possible_plants_by_threshold(segment_part.possible_plants, selected_plant.projection)
        first_subpart.possible_plants = before_plants
        second_subpart.possible_plants = after_plants
        
        return [first_subpart, second_subpart]
    
    def create_closest_plant(self, segment_part):
        closest_expected_projection = segment_part.expected_projections[0]
        closest_expected_position = projection_to_position_2d(closest_expected_projection, segment_part.start.position, segment_part.end.position)
        # Add on z value
        closest_expected_position = closest_expected_position + (segment_part.start.position[2],)
        new_plant = Plant(name='plant', position=closest_expected_position, zone=segment_part.start.zone)
        new_plant.projection = closest_expected_projection
        return new_plant
    
    def find_most_likely_plant(self, segment_part):
        
        for plant in segment_part.possible_plants:
            
            lateral_penalty = self.calculate_lateral_penalty(plant['lateral'])
        
            projection_penalty = self.calculate_projection_penalty(segment_part.expected_projections, plant['projection'])
        
            closeness_penalty = self.calculate_closeness_penalty(plant['projection'])
            
            confidence_boost = self.calculate_plant_part_confidence(plant)
            
            plant['penalty'] = ((lateral_penalty * self.lateral_penalty_scale +
                                projection_penalty * self.lateral_penalty_scale +
                                closeness_penalty * self.closeness_penalty_scale) /
                                confidence_boost)
            
        valid_plants = [p for p in segment_part.possible_plants if not math.isnan(p['penalty'])]
            
        if len(valid_plants) == 0:
            return None # none of the possible plants worked out
        
        best_plant = sorted(valid_plants, key=lambda p: p['penalty'])[0]
        
        # convert to an actual plant object
        selected_plant = Plant('plant', position=best_plant['position'], zone=segment_part.start.zone)
        
        # this global rect will be converted to a rotated image rect later
        selected_plant.bounding_rect = best_plant['rect']
        selected_plant.projection = best_plant['projection']
        
        self.num_successfully_found_plants += 1
        
        return selected_plant
            
    def split_possible_plants_by_threshold(self, possible_plants, projection_thresh):
            
        before_plants = [p for p in possible_plants if p['projection'] < projection_thresh]
        after_plants = [p for p in possible_plants if p['projection'] >= projection_thresh]
        
        return before_plants, after_plants
            
    def filter_plants_by_segment_part(self, segment_part):
        
        possible_plants = segment_part.possible_plants
        
        for plant in possible_plants:
            lateral_distance, projection_distance = lateral_and_projection_distance_2d(plant['position'], segment_part.start.position, segment_part.end.position)
            plant['lateral'] = lateral_distance
            plant['projection'] = projection_distance
        
        # Order from start to end code
        possible_plants = sorted(possible_plants, key=lambda p: p['projection'])
        
        # Throw out any that are too close to or behind start/end code
        if 'code' in segment_part.start.type.lower():
            closest_at_start = self.closest_code_spacing
        else:
            closest_at_start = self.closest_plant_spacing
        if 'code' in segment_part.end.type.lower():
            closest_at_end = segment_part.length - self.closest_code_spacing
        else:
            closest_at_end = segment_part.length - self.closest_plant_spacing
    
        filtered_plants = [p for p in segment_part.possible_plants if p['projection'] >= closest_at_start and p['projection'] <= closest_at_end]
    
        return filtered_plants
    
    def calculate_expected_positions(self, segment_part):
    
        # Calculate expected positions.
        expected_distances = []
        if 'code' in segment_part.start.type.lower():
            start_distance = self.expected_code_spacing
        else:
            start_distance = self.expected_plant_spacing
            
        if 'code' in segment_part.end.type.lower():
            end_distance = segment_part.length - self.closest_code_spacing
        else:
            end_distance = segment_part.length - self.closest_plant_spacing
            
        if start_distance > end_distance:
            return [] # no expected plant left in this segment part
            
        expected_distances.append(start_distance)
        current_distance = start_distance
        while True:
            current_distance += self.expected_plant_spacing
            if current_distance > end_distance:
                break
            expected_distances.append(current_distance)            
    
        return expected_distances

    def calculate_lateral_penalty(self, lateral_error):
        
        lateral_error = abs(lateral_error)
        
        # lateral errors (in meters) for two linear pieces
        x1 = 0.076 
        x2 = 0.15
        # penalty values for two linear pieces
        y1 = 0.1 
        y2 = 1.0
        if lateral_error < x1:
            y = (y1 / x1) * lateral_error
        elif lateral_error <= x2:
            y = ((y2-y1) / (x2-x1)) * (lateral_error - x1) + y1
        else:
            y = float('NaN')
            
        return y
            
    def calculate_projection_penalty(self, expected_projections, projection):
        
        # Find error (in meters) to closest expected projection
        smallest_error = min([abs(projection - expected) for expected in expected_projections])
        
        # projection errors (in meters) for two linear pieces
        x1 = self.expected_plant_spacing / 4.0
        x2 = self.expected_plant_spacing / 2.0
        # penalty values for two linear pieces
        y1 = 0.1
        y2 = 1.0
        if smallest_error < x1:
            y = (y1 / x1) * smallest_error
        elif smallest_error <= x2:
            y = ((y2-y1) / (x2-x1)) * (smallest_error - x1) + y1
        else:
            y = 1.0
            
        return y
    
    def calculate_closeness_penalty(self, projection):
        
        if projection < (2.5 * self.expected_plant_spacing):
            y = 0.0
        elif projection < (3.5 * self.expected_plant_spacing):
            y = 1.0
        else:
            y = float('NaN')
            
        return y
    
    def calculate_plant_part_confidence(self, plant):
        
        # Assign plants confidence based on blue sticks vs plants
        if 'items' in plant:
            plant_component_types = [item['item_type'] for item in plant['items']]
        else:
            plant_component_types = [plant['item_type']]
        contains_blue_stick = 'stick_part' in plant_component_types
        contains_leaf = 'leaf' in plant_component_types
        blue_stick_multiplier = self.stick_multiplier if contains_blue_stick else 1
        leaf_multiplier = self.leaf_multiplier if contains_leaf else 1
        plant_part_confidence = 1 * blue_stick_multiplier * leaf_multiplier
            
        return plant_part_confidence
    
class ClosestSinglePlantFilter:
    
    def __init__(self, max_single_distance):
        
        self.max_single_distance = max_single_distance
        
        self.num_successfully_found_plants = 0
        self.num_created_because_no_plants = 0
    
    def find_actual_plant(self, possible_plants, segment):
        
        for possible_plant in possible_plants:
            distance_to_code = position_difference(possible_plant['position'], segment.start_code.position)
            
            closeness_penalty = self.calculate_closeness_penalty(distance_to_code)
            num_items_penalty = self.calculate_num_items_penalty(possible_plant)
            
            possible_plant['penalty'] = closeness_penalty + 0.2*num_items_penalty
            
        valid_plants = [p for p in possible_plants if not math.isnan(p['penalty'])]
            
        if len(valid_plants) == 0:
            best_plant = None # none of the possible plants worked out
        else:
            best_plant = sorted(valid_plants, key=lambda p: p['penalty'])[0]
            
        if best_plant is None:
            position = segment.start_code.position
            bounding_rect = None
        else:
            position = best_plant['position']
            bounding_rect = best_plant['rect']
            self.num_successfully_found_plants += 1
            
        plant = Plant('plant', position=position, zone=segment.start_code.zone, bounding_rect=bounding_rect)
        
        return plant
    
    def calculate_closeness_penalty(self, distance):
        
        if distance < self.max_single_distance:
            y = (1.0 / self.max_single_distance) * distance
        else:
            y = float('NaN')
            
        return y
    
    def calculate_num_items_penalty(self, possible_plant):
        
        try:
            num_items = len(possible_plant['items'])
        except ValueError:
            num_items = 1
        
        if num_items < 2:
            penalty = 1
        if num_items < 3:
            penalty = 0.5
        else:
            penalty = 0
        
        return penalty
        
