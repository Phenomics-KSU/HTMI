#! /usr/bin/env python

import sys
import math
import copy

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.data.field_item import Plant, CreatedPlant
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
    
    def __init__(self, start_code_spacing, end_code_spacing, plant_spacing, lateral_ps=1, projection_ps=1,
                 closeness_ps=1, stick_multiplier=2, leaf_multiplier=1.5, tag_multiplier=4):
        '''Spacing distances (in centimeters) are expected values'''
        self.expected_start_code_spacing = start_code_spacing
        self.expected_end_code_spacing = end_code_spacing
        self.expected_plant_spacing = plant_spacing
        
        # Allow row codes to be much closer to plants since they're hand placed.
        closer_code_spacing = min(self.expected_start_code_spacing, self.expected_end_code_spacing)
        self.closest_group_code_spacing = closer_code_spacing / 2.0
        self.closest_row_code_spacing = closer_code_spacing / 8.0
        self.closest_plant_spacing = plant_spacing / 1.5
        
        self.num_successfully_found_plants = 0
        self.num_created_plants = 0

        # Scales to weight the importance of different penalties
        self.lateral_penalty_scale = lateral_ps
        self.projection_penalty_scale = projection_ps
        self.closeness_penalty_scale = closeness_ps
        self.stick_multiplier = max(1, stick_multiplier)
        self.leaf_multiplier = max(1, leaf_multiplier)
        self.tag_multiplier = max(1, tag_multiplier)
        
    def locate_actual_plants_in_segment(self, possible_plants, whole_segment):
    
        whole_part = SegmentPart(whole_segment.start_code, whole_segment.end_code)
        whole_part.possible_plants = possible_plants
    
        sub_parts = self.split_into_subparts(whole_part)
        
        actual_plants = []
        for part in sub_parts:
            # Add start of segment part.  Don't add the end since it should be the start of the next part,
            # and the last part the end item is a code so we don't want to add that either.
            if 'plant' in part.start.type.lower():
                actual_plants.append(part.start)
                
        assert('code' in sub_parts[-1].end.type.lower())
        
        for plant in actual_plants:
            if plant.type == 'CreatedPlant':
                self.num_created_plants += 1
            else:
                self.num_successfully_found_plants += 1
             
        return actual_plants
    
    def split_into_subparts(self, segment_part):
    
        reverse_segment_part = SegmentPart(segment_part.end, segment_part.start)
        reverse_segment_part.possible_plants = copy.copy(segment_part.possible_plants)
    
        # Need to process reverse first so when splitting segments the possible plants will have correct 'forward' projections.
        reverse_plant = self.process_segment_part(reverse_segment_part)
        forward_plant = self.process_segment_part(segment_part)
        
        split_segment_parts = self.split_segment_into_parts(segment_part, forward_plant, reverse_plant)
  
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
            # Segment part is too short to contain more plants.
            return None
        
        # Remove any plants that don't fall within the valid range of the segment part.
        segment_part.possible_plants = self.filter_plants_by_segment_part(segment_part)

        if len(segment_part.possible_plants) == 0:
            # No plants to select from so just create a plant where one is most likely to be.
            selected_plant = self.create_closest_plant(segment_part)
        else:
            # Figure out which possible plant is most likely to be an actual plant.
            selected_plant = self.find_most_likely_plant(segment_part)
            if selected_plant is None:
                # None of the possible plants worked out so fall back on closest expected plant.
                selected_plant = self.create_closest_plant(segment_part)
                
        return selected_plant
    
    def split_segment_into_parts(self, segment_part, forward_plant, reverse_plant):
        
        if not forward_plant or not reverse_plant:
            return [] # Can't split up any more. 
        
        # First change reverse plant projection to be in the forward direction to make it consistent.
        _, reverse_plant.projection = lateral_and_projection_distance_2d(reverse_plant.position, segment_part.start.position,
                                                                            segment_part.end.position)
        
        projection_difference = reverse_plant.projection - forward_plant.projection
        
        selected_plants = []
        if abs(projection_difference) < 0.0001:
            # Segments split on same plant so it doesn't matter which one we choose.
            selected_plants = [forward_plant]
        elif projection_difference > self.closest_plant_spacing:
            # Normal case where forward/reverse don't overlap. We should now have 3 segments.
            selected_plants = [forward_plant, reverse_plant]
        else:
            # Forward/reverse overlap.  Need to decide which one to use.
            if forward_plant.type == 'CreatedPlant' and reverse_plant.type == 'CreatedPlant':
                avg_position = np.mean([forward_plant.position, reverse_plant.position], axis=0)
                avg_plant = CreatedPlant(name='plant', position=avg_position, zone=forward_plant.zone)
                avg_plant.projection = np.mean([forward_plant.projection, reverse_plant.projection], axis=0)
                selected_plants = [avg_plant]
            elif forward_plant.type == 'Plant' and reverse_plant.type == 'Plant':
                if forward_plant.penalty < reverse_plant.penalty:
                    selected_plants = [forward_plant]
                else:
                    selected_plants = [reverse_plant]
            elif forward_plant.type == 'Plant':
                selected_plants = [forward_plant]
            elif reverse_plant.type == 'Plant':
                selected_plants = [reverse_plant]
            else:
                assert(False)
        
        if len(selected_plants) == 0:
            return []
        elif len(selected_plants) == 1:
            selected_plant = selected_plants[0]
            first_subpart = SegmentPart(start=segment_part.start, end=selected_plant)
            second_subpart = SegmentPart(start=selected_plant, end=segment_part.end)
            before_plants, after_plants = self.split_possible_plants_by_projections(segment_part.possible_plants, [selected_plant.projection])
            first_subpart.possible_plants = before_plants
            second_subpart.possible_plants = after_plants
            return [first_subpart, second_subpart]
        elif len(selected_plants) == 2:
            first_subpart = SegmentPart(start=segment_part.start, end=selected_plants[0])
            second_subpart = SegmentPart(start=selected_plants[0], end=selected_plants[1])
            third_subpart = SegmentPart(start=selected_plants[1], end=segment_part.end)
            first_subpart.possible_plants, second_subpart.possible_plants, third_subpart.possible_plants = \
                self.split_possible_plants_by_projections(segment_part.possible_plants, [selected_plants[0].projection, selected_plants[1].projection])
            return [first_subpart, second_subpart, third_subpart]
        else:
            assert(False)
    
    def create_closest_plant(self, segment_part):
        closest_expected_projection = segment_part.expected_projections[0]
        closest_expected_position = projection_to_position_2d(closest_expected_projection, segment_part.start.position, segment_part.end.position)
        # Add on z value
        closest_expected_position = closest_expected_position + (segment_part.start.position[2],)
        new_plant = CreatedPlant(name='plant', position=closest_expected_position, zone=segment_part.start.zone)
        new_plant.projection = closest_expected_projection
        return new_plant
    
    def find_most_likely_plant(self, segment_part):
        
        for plant in segment_part.possible_plants:
            
            lateral_penalty = self.calculate_lateral_penalty(plant['lateral'])
        
            projection_penalty = self.calculate_projection_penalty(segment_part.expected_projections, plant['projection'])
            
            if segment_part.start.type == 'RowCode':
                # Don't weight as heavily since row codes are hand placed.
                projection_penalty /= 3
        
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
        selected_plant.penalty = best_plant['penalty']

        return selected_plant
            
    def split_possible_plants_by_projections(self, possible_plants, projections):

        if len(projections) == 0:
            return possible_plants

        split_plants = [[] for i in range(len(projections)+1)]
        
        for plant in possible_plants:
            plant_grouped = False
            for i, projection in enumerate(projections):
                if plant['projection'] < projection:
                    split_plants[i].append(plant)
                    plant_grouped = True
                    break
            if not plant_grouped:
                # Plant came after all projections.
                split_plants[-1].append(plant)

        return split_plants

    def split_possible_plants_between_projections(self, possible_plants, smaller_projection, larger_projection):
        '''Return plants in possible_plants that fall between smaller and larger projections'''
            
        return [p for p in possible_plants if p['projection'] > smaller_projection and p['projection'] < larger_projection]
            
    def filter_plants_by_segment_part(self, segment_part):
        
        possible_plants = segment_part.possible_plants
        
        for plant in possible_plants:
            lateral_distance, projection_distance = lateral_and_projection_distance_2d(plant['position'], segment_part.start.position, segment_part.end.position)
            plant['lateral'] = lateral_distance
            plant['projection'] = projection_distance
        
        # Order from start to end code
        possible_plants = sorted(possible_plants, key=lambda p: p['projection'])
        
        # Throw out any that are too close to or behind start/end code
        if segment_part.start.type == 'GroupCode':
            closest_at_start = self.closest_group_code_spacing
        elif segment_part.start.type == 'RowCode':
            closest_at_start = self.closest_row_code_spacing 
        else:
            closest_at_start = self.closest_plant_spacing
            
        if segment_part.start.type == 'GroupCode':
            closest_at_end = segment_part.length - self.closest_group_code_spacing
        elif segment_part.start.type == 'RowCode':
            closest_at_end = segment_part.length - self.closest_row_code_spacing 
        else:
            closest_at_end = segment_part.length - self.closest_plant_spacing
    
        filtered_plants = [p for p in possible_plants if p['projection'] >= closest_at_start and p['projection'] <= closest_at_end]
    
        return filtered_plants
    
    def calculate_expected_positions(self, segment_part):
    
        # Calculate expected positions.
        expected_distances = []
        if 'code' in segment_part.start.type.lower():
            start_distance = self.expected_start_code_spacing
        else:
            start_distance = self.expected_plant_spacing
            
        if 'code' in segment_part.end.type.lower():
            end_distance = segment_part.length - self.closest_group_code_spacing
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
        x1 = 0.07 
        x2 = 0.12
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
        
        # Assign plants confidence based on blue sticks vs tags vs leaves
        if 'items' in plant:
            plant_component_types = [item['item_type'] for item in plant['items']]
        else:
            plant_component_types = [plant['item_type']]
        contains_blue_stick = 'stick_part' in plant_component_types
        contains_leaf = 'leaf' in plant_component_types
        contains_tag = 'tag' in plant_component_types
        blue_stick_multiplier = self.stick_multiplier if contains_blue_stick else 1
        leaf_multiplier = self.leaf_multiplier if contains_leaf else 1
        tag_multiplier = self.tag_multiplier if contains_tag else 1
        plant_part_confidence = blue_stick_multiplier * leaf_multiplier * tag_multiplier
            
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
            
        plant = Plant(name=segment.start_code.name, position=position, zone=segment.start_code.zone, bounding_rect=bounding_rect)
        
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
        
class PlantSpacingFilter(object):
    
    def __init__(self, spacing_thresh):
        
        self.spacing_thresh = spacing_thresh
        self.num_plants_moved = 0
    
    def filter(self, plants):
        
        for k, plant in enumerate(plants):
            
            if k == 0 or k == len(plants) - 1:
                continue
            
            last_plant = plants[k-1]
            next_plant = plants[k+1]
            
            last_dist = position_difference(last_plant.position, plant.position)
            next_dist = position_difference(next_plant.position, plant.position)
            
            min_dist = min(last_dist, next_dist)
            max_dist = max(last_dist, next_dist)
            
            if min_dist == 0:
                continue # protect against division by zero
            
            ratio = max_dist / min_dist
            
            if ratio <= self.spacing_thresh:
                continue # good spacing so don't need to do anything
            
            # Bad spacing so move plant to be in center
            avg_position = np.mean([last_plant.position, next_plant.position], axis=0)
            
            plants[k] = CreatedPlant(name='plant', position=avg_position, zone=last_plant.zone)
            
            self.num_plants_moved += 1
                