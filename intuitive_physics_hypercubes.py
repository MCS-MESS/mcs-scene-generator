import copy
import math
import random
from abc import ABC, abstractmethod
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import exceptions
import geometry
import gravity_support_objects
import materials
import objects
import occluders
import hypercubes
from shapely import affinity
import speeds
import tags
import util


PLAUSIBLE = 'plausible'
IMPLAUSIBLE = 'implausible'

# The number of steps any object will take to fall and settle.
OBJECT_FALL_TIME = 34

LAST_STEP_MOVE_ACROSS = 90
LAST_STEP_FALL_DOWN = 60

EARLIEST_ACTION_STEP = occluders.OCCLUDER_MOVEMENT_TIME * 2 + 1
LATEST_ACTION_STEP_MOVE_ACROSS = LAST_STEP_MOVE_ACROSS - \
    occluders.OCCLUDER_MOVEMENT_TIME
LATEST_ACTION_STEP_FALL_DOWN = LAST_STEP_FALL_DOWN - \
    occluders.OCCLUDER_MOVEMENT_TIME - OBJECT_FALL_TIME

BACKGROUND_MAX_X = 6.5
BACKGROUND_MIN_Z = 3.25
BACKGROUND_MAX_Z = 4.95

PERFORMER_START = {
    'position': {
        'x': 0,
        'y': 0,
        'z': -4.5
    },
    'rotation': {
        'y': 0
    }
}

MIN_TARGET_Z = 1.6
MAX_TARGET_Z = 4.4
STEP_Z = 0.05
SEPARATION_Z = 1.1

MIN_OFFSCREEN_X = 4.16
STEP_OFFSCREEN_X = 0.03

MIN_OFFSCREEN_Y = 4.94
STEP_OFFSCREEN_Y = 0.02

# Assume the target object will be at most 1.0 wide, and then add some space
# for the no-support position, so each object is always in view of the camera.
GRAVITY_SUPPORT_MAX_ONSCREEN_X = 1.5

GRAVITY_SUPPORT_MOVE = 0.25
GRAVITY_SUPPORT_WAIT = 5
GRAVITY_SUPPORT_WIND = 250
GRAVITY_SUPPORT_MOVEMENT = {
    "stepBegin": 0,
    "stepEnd": 0,
    "vector": {
        "x": 0,
        "y": -GRAVITY_SUPPORT_MOVE,
        "z": 0
    }
}
POLE_ACTIVE = ['active']
POLE_INACTIVE = ['inactive']


def choose_move_across_object_position(
    left_side: bool,
    position_y: float,
    object_list: List[Dict[str, Any]]
) -> float:
    """Return a new X/Y/Z position for a move-across object with the given
    side and Y position that is not too close to an existing object."""
    while True:
        position_z = choose_position_z()
        # Don't be too close to any existing object.
        for instance in object_list:
            object_z = instance['shows'][0]['position']['z']
            if (
                position_z < (object_z + SEPARATION_Z) and
                position_z > (object_z - SEPARATION_Z)
            ):
                position_z = None
                break
        if position_z is not None:
            break

    position_x = retrieve_off_screen_position_x(position_z)

    return {
        'x': (-1 * position_x) if left_side else position_x,
        'y': position_y,
        'z': position_z
    }


def choose_position_z() -> float:
    """Return a pseudo-random Z position for a target/non-target object."""
    max_steps = (MAX_TARGET_Z - MIN_TARGET_Z) / STEP_Z
    return MIN_TARGET_Z + (random.randint(0, max_steps) * STEP_Z)


def object_x_to_occluder_x(object_x: float, object_z: float):
    """Return the X position for an occluder in front of an object at the given
    X/Z position."""
    object_distance_z = object_z - PERFORMER_START['position']['z']
    occluder_distance_z = (
        occluders.OCCLUDER_POSITION_Z - PERFORMER_START['position']['z']
    )
    camera_angle = math.asin(object_x / object_distance_z)
    return math.sin(camera_angle) * occluder_distance_z


def occluder_x_to_object_x(occluder_x: float, object_z: float):
    """Return the X position for an object at the given Z position in back of
    an occluder at the given X position."""
    object_distance_z = object_z - PERFORMER_START['position']['z']
    occluder_distance_z = (
        occluders.OCCLUDER_POSITION_Z - PERFORMER_START['position']['z']
    )
    camera_angle = math.asin(occluder_x / occluder_distance_z)
    return math.sin(camera_angle) * object_distance_z


def retrieve_off_screen_position_x(position_z: float) -> float:
    """Return the off-screen object X position for the given Z position."""
    return MIN_OFFSCREEN_X + (
        ((position_z - MIN_TARGET_Z) / STEP_Z) * STEP_OFFSCREEN_X
    )


def retrieve_off_screen_position_y(position_z: float) -> float:
    """Return the off-screen object Y position for the given Z position."""
    return MIN_OFFSCREEN_Y + (
        ((position_z - MIN_TARGET_Z) / STEP_Z) * STEP_OFFSCREEN_Y
    )


VARIATIONS = SimpleNamespace(
    TRAINED='trained',
    DIFFERENT_SHAPE='different_shape',
    UNTRAINED_SHAPE='untrained_shape',
    UNTRAINED_DIFFERENT_SHAPE='untrained_different_shape',
    UNTRAINED_SIZE='untrained_size',
    # Gravity Support
    SYMMETRIC='symmetric',
    ASYMMETRIC_LEFT='asymmetric_left',
    ASYMMETRIC_RIGHT='asymmetric_right'
)


class ObjectVariations():
    """Saves multiple variations of a single conceptual object. Each scene in a
    hypercube may use a variation of the object. Variations may be different in
    size, shape, position, color, etc."""

    def __init__(self, name_to_instance: Dict[str, Dict[str, Any]]) -> None:
        self._instances = name_to_instance

    def all(self) -> List[Dict[str, Any]]:
        """Return a list of instances for all variations."""
        return list(self._instances.values())

    def get(self, name) -> Dict[str, Any]:
        """Return an instance for the variation with the given name."""
        return self._instances[name]

    def get_max_size_x(self):
        """Return the max size X of instances across all variations."""
        # For a non-occluder, the size is its dimensions, NOT its scale!
        return max([
            instance['dimensions']['x'] for instance in self.all()
        ])


class TargetVariations(ObjectVariations):
    """Saves multiple variations of a single conceptual target. Each scene in a
    hypercube may use a variation of the target. Variations may be different in
    size, shape, position, color, etc."""

    def __init__(
        self,
        name_to_definition: Dict[str, Dict[str, Any]],
        location: Dict[str, Any],
        is_fall_down=False
    ) -> None:
        self._definitions = name_to_definition
        self._is_fall_down = is_fall_down

        object_id = None
        object_materials_list = None

        instances = {}
        for name, definition in name_to_definition.items():
            adjusted_location = self._adjust_location(definition, location)
            # Instantiate each variation from the common target definition.
            instances[name] = util.instantiate_object(
                definition,
                adjusted_location,
                object_materials_list
            )
            instances[name]['shows'][0]['boundingBox'] = (
                geometry.generate_object_bounds(
                    definition['dimensions'],
                    definition.get('offset'),
                    instances[name]['shows'][0]['position'],
                    instances[name]['shows'][0]['rotation']
                )
            )
            # Ensure each instance uses the same ID and materials/colors.
            if not object_id:
                object_id = instances[name]['id']
            if not object_materials_list:
                object_materials_list = [(
                    instances[name]['materials'][0],
                    instances[name]['color']
                )]
            instances[name]['id'] = object_id
            instances[name]['role'] = tags.ROLES.TARGET

        super().__init__(instances)

    def _adjust_location(
        self,
        definition: Dict[str, Any],
        location: Dict[str, Any]
    ) -> Dict[str, Any]:
        location_copy = copy.deepcopy(location)
        location_copy['position']['y'] += definition['positionY']
        if 'rotation' not in location_copy:
            location_copy['rotation'] = {
                'x': 0,
                'y': 0,
                'z': 0
            }
        # If the object's a cylinder, rotate it a little to be at an angle.
        if definition['type'] == 'cylinder' and self._is_fall_down:
            location_copy['rotation']['y'] = random.choice([45, -45])
        return location_copy


class IntuitivePhysicsHypercube(hypercubes.Hypercube, ABC):
    def __init__(
        self,
        name: str,
        body_template: Dict[str, Any],
        goal_template: Dict[str, Any],
        role_to_type: Dict[str, str],
        is_fall_down=False,
        is_move_across=False,
        only_basic_shapes=False,
        only_complex_shapes=False,
        training=False
    ) -> None:
        self._role_to_type = role_to_type

        # Choose fall-down or move-across if needed.
        if not is_fall_down and not is_move_across:
            is_fall_down = random.choice([False, True])
            is_move_across = not is_fall_down

        self._init_each_object_definition_list(is_fall_down)

        if is_fall_down:
            self._last_step = LAST_STEP_FALL_DOWN
            self._scene_setup_function = (
                IntuitivePhysicsHypercube._generate_fall_down
            )
        elif is_move_across:
            self._last_step = LAST_STEP_MOVE_ACROSS
            self._scene_setup_function = (
                IntuitivePhysicsHypercube._generate_move_across
            )

        super().__init__(name, body_template, goal_template, training=training)

    @abstractmethod
    def _create_intuitive_physics_scenes(
        self,
        default_scene: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Create and return a collection of new intuitive physics scenes."""
        pass

    # Override
    def _create_scenes(
        self,
        body_template: Dict[str, Any],
        goal_template: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        default_scene = self._create_default_scene(body_template,
                                                   goal_template)
        scenes = self._create_intuitive_physics_scenes(default_scene)
        for scene in scenes.values():
            scene['goal']['sceneInfo'][tags.SCENE.ID] = [
                scene_id.upper() for scene_id
                in scene['goal']['sceneInfo'][tags.SCENE.ID]
            ]
        # Sort scenes by ID.
        return sorted(
            list(scenes.values()),
            key=lambda x: x['goal']['sceneInfo'][tags.SCENE.ID][0]
        )

    # Override
    def _get_training_scenes(self) -> List[Dict[str, Any]]:
        return [scene for scene in self._scenes if (
            scene['goal']['answer']['choice'] == PLAUSIBLE and
            (not scene['evaluationOnly'])
        )]

    def _choose_fall_down_object_count(self) -> int:
        """Return the number of objects for the fall-down scene."""
        # Always generate two objects for all fall-down scenes in Eval 3.
        # We may remove one or more of them later for specific scenes.
        return 2

    def _choose_fall_down_occluder_count(self) -> int:
        """Return the number of occluders for the fall-down scene."""
        # Always generate two occluders for all fall-down scenes in Eval 3.
        # We may remove one or more of them later for specific scenes.
        return 2

    def _choose_move_across_object_count(self) -> int:
        """Return the number of objects for the move-across scene."""
        # Always generate two objects for all move-across scenes in Eval 3.
        # We may remove one or more of them later for specific scenes.
        return 2

    def _choose_move_across_occluder_count(self) -> int:
        """Return the number of occluders for the move-across scene."""
        # Always generate three occluders for all move-across scenes in Eval 3.
        # We may remove one or more of them later for specific scenes.
        return 3

    def _choose_object_definition(
        self,
        location: Dict[str, Any],
        index: int
    ) -> TargetVariations:
        """Return trained and untrained variations of an object definition for
        a target or non-target object positioned at the given location."""
        definitions = {}
        role = tags.ROLES.TARGET if index == 0 else tags.ROLES.NON_TARGET
        object_type = self._role_to_type[role]
        trained_definition_list = self._filter_definition_list_on_type(
            self._trained_definition_list,
            object_type
        )
        untrained_shape_definition_list = self._filter_definition_list_on_type(
            self._untrained_shape_definition_list,
            object_type
        )
        untrained_size_definition_list = self._filter_definition_list_on_type(
            self._untrained_size_definition_list,
            object_type
        )

        trained_definition = random.choice(trained_definition_list)
        definitions[VARIATIONS.TRAINED] = trained_definition

        different_shape_list = [
            definition for definition in trained_definition_list
            if util.is_similar_except_in_shape(
                trained_definition,
                definition,
                only_x_dimension=True
            )
        ]
        if len(different_shape_list) == 0:
            raise exceptions.SceneException(
                f'Intuitive physics trained object definition does not have '
                f'any different trained shapes {trained_definition}')
        definitions[VARIATIONS.DIFFERENT_SHAPE] = random.choice(
            different_shape_list
        )

        untrained_shape_list = [
            definition for definition in untrained_shape_definition_list
            if util.is_similar_except_in_shape(
                trained_definition,
                definition,
                only_x_dimension=True
            )
        ]
        if len(untrained_shape_list) == 0:
            raise exceptions.SceneException(
                f'Intuitive physics trained object definition does not have '
                f'any different untrained shapes {trained_definition}')
        untrained_shape_definition = random.choice(untrained_shape_list)
        definitions[VARIATIONS.UNTRAINED_SHAPE] = untrained_shape_definition

        different_untrained_shape_list = [
            definition for definition in untrained_shape_list
            if util.is_similar_except_in_shape(
                untrained_shape_definition,
                definition,
                only_x_dimension=True
            )
        ]
        if len(different_untrained_shape_list) == 0:
            raise exceptions.SceneException(
                f'Intuitive physics trained object definition does not have '
                f'a second different untrained shape {trained_definition} '
                f'and {untrained_shape_definition}')
        definitions[VARIATIONS.UNTRAINED_DIFFERENT_SHAPE] = random.choice(
            different_untrained_shape_list
        )

        untrained_size_list = [
            definition for definition in untrained_size_definition_list
            if util.is_similar_except_in_size(
                trained_definition,
                definition,
                only_x_dimension=True
            )
        ]
        if len(untrained_size_list) == 0:
            raise exceptions.SceneException(
                f'Intuitive physics trained object definition does not have '
                f'any different untrained sizes {trained_definition}')
        definitions[VARIATIONS.UNTRAINED_SIZE] = random.choice(
            untrained_size_list
        )

        return TargetVariations(definitions, location, self.is_fall_down())

    def _create_default_scene(
        self,
        body_template: Dict[str, Any],
        goal_template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create and return this hypercube's default scene JSON using the
        given templates that will be shared by each scene in this hypercube."""
        scene = copy.deepcopy(body_template)
        scene['evaluationOnly'] = False
        scene['performerStart'] = PERFORMER_START
        scene['intuitivePhysics'] = True

        # Choose a new room wall material from a restricted list.
        room_wall_material_choice = random.choice(
            random.choice(materials.INTUITIVE_PHYSICS_WALL_MATERIALS)
        )
        scene['wallMaterial'] = room_wall_material_choice[0]
        scene['wallColors'] = room_wall_material_choice[1]

        scene['goal'] = copy.deepcopy(goal_template)
        scene['goal']['answer'] = {
            'choice': PLAUSIBLE
        }
        scene['goal']['sceneInfo'][tags.SCENE.FALL_DOWN] = self.is_fall_down()
        scene['goal']['sceneInfo'][tags.SCENE.MOVE_ACROSS] = (
            self.is_move_across()
        )
        scene['goal']['sceneInfo'][tags.SCENE.SETUP] = (
            tags.tag_to_label(tags.SCENE.FALL_DOWN) if self.is_fall_down()
            else tags.tag_to_label(tags.SCENE.MOVE_ACROSS)
        )
        scene['goal']['last_step'] = self._last_step
        scene['goal']['action_list'] = [['Pass']] * scene['goal']['last_step']
        scene['goal']['description'] = ''
        scene['goal']['metadata'] = {
            'choose': [PLAUSIBLE, IMPLAUSIBLE]
        }

        role_to_object_list = self._create_default_objects(
            scene['wallMaterial'],
            scene['wallColors']
        )
        scene = hypercubes.update_scene_objects(scene, role_to_object_list)

        return scene

    def _create_default_objects(
        self,
        room_wall_material_name: str,
        room_wall_colors: List[str]
    ) -> Dict[str, Any]:
        """Generate and return this hypercube's objects in a dict of roles with
        their corresponding object lists."""
        occluder_wall_material_list = (
            self._find_structural_object_material_list(room_wall_material_name)
        )
        moving_object_list, occluder_list = self._scene_setup_function(
            self,
            occluder_wall_material_list
        )
        target_list, distractor_list = self._separate_targets_and_non_targets(
            moving_object_list
        )
        self._target_list = target_list
        self._distractor_list = distractor_list
        self._occluder_list = occluder_list
        # Don't generate background (context) objects for any scenes in Eval 3.
        self._background_list = []
        role_to_object_list = {}
        role_to_object_list[tags.ROLES.TARGET] = self._target_list
        role_to_object_list[tags.ROLES.NON_TARGET] = (
            self._distractor_list
        )
        role_to_object_list[tags.ROLES.INTUITIVE_PHYSICS_OCCLUDER] = (
            self._occluder_list
        )
        role_to_object_list[tags.ROLES.CONTEXT] = self._background_list
        return role_to_object_list

    def _filter_definition_list_on_type(
        self,
        definition_list: List[Dict[str, Any]],
        object_type: str
    ) -> List[Dict[str, Any]]:
        """Return the given definition list filtered to only have objects of
        the given type, unless doing so would remove all the objects from the
        definition list."""
        filtered_definition_list = [
            definition for definition in definition_list
            if definition['type'] == object_type
        ] if object_type else definition_list
        return (
            filtered_definition_list if len(filtered_definition_list) > 0
            else definition_list
        )

    def _find_fall_down_paired_list(self) -> List[TargetVariations]:
        """Return objects that must be paired with occluders in fall-down
        scenes."""
        return self._variations_list

    def _find_move_across_paired_list(self) -> List[TargetVariations]:
        """Return objects that must be paired with occluders in move-across
        scenes."""
        return [self._variations_list[0]]

    def _find_structural_object_material_list(
        self,
        room_wall_material_name: str
    ) -> List[Tuple[str, List[str]]]:
        """Find and return the material list for any structural objects in the
        scene (like occluders) that isn't the same as the room's wall
        material."""
        structural_object_material_list = []
        for material_list in materials.INTUITIVE_PHYSICS_WALL_MATERIALS:
            filtered_material_list = []
            for material in material_list:
                if material[0] != room_wall_material_name:
                    filtered_material_list.append(material)
            structural_object_material_list.append(filtered_material_list)
        return structural_object_material_list

    def _generate_background_object_list(self) -> List[Dict[str, Any]]:
        """Generate and return the list of background (a.k.a. context) objects,
        behind the moving objects, positioned near the room's back wall."""

        def random_x():
            return util.random_real(-BACKGROUND_MAX_X, BACKGROUND_MAX_X,
                                    util.MIN_RANDOM_INTERVAL)

        def random_z():
            # Choose Z values so each background object is positioned between
            # moving objects and the back wall of the room.
            return util.random_real(BACKGROUND_MIN_Z, BACKGROUND_MAX_Z,
                                    util.MIN_RANDOM_INTERVAL)

        background_count = random.choices((0, 1, 2, 3, 4, 5),
                                          (50, 10, 10, 10, 10, 10))[0]
        background_object_list = []
        background_bounds_list = []
        definition_list = util.retrieve_complete_definition_list(
            objects.get(objects.ObjectDefinitionList.NOT_PICKUPABLES)
        )

        for _ in range(background_count):
            location = None
            while not location:
                background_definition = random.choice(
                    random.choice(definition_list)
                )
                location = geometry.calc_obj_pos(geometry.ORIGIN,
                                                 background_bounds_list,
                                                 background_definition,
                                                 random_x, random_z)
                if location:
                    # Ensure entire bounds is within background
                    for point in location['boundingBox']:
                        x = point['x']
                        z = point['z']
                        if (
                            x < -BACKGROUND_MAX_X or x > BACKGROUND_MAX_X or
                            z < BACKGROUND_MIN_Z or z > BACKGROUND_MAX_Z
                        ):
                            # If not, reset and try again
                            location = None
                            del background_bounds_list[-1]
                            break
            background_object = util.instantiate_object(background_definition,
                                                        location)
            background_object_list.append(background_object)

        return background_object_list

    def _generate_fall_down(
        self,
        occluder_wall_material_list: List[List[Tuple]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate and return fall-down objects and occluders."""
        object_list = self._generate_fall_down_object_list()
        occluder_list = self._generate_fall_down_paired_occluder_list(
            occluder_wall_material_list
        )
        self._generate_occluder_list(
            self._choose_fall_down_occluder_count() -
            int(len(occluder_list) / 2),
            occluder_list,
            occluder_wall_material_list,
            True
        )
        return object_list, occluder_list

    def _generate_fall_down_object_list(self) -> List[Dict[str, Any]]:
        """Generate and return fall-down objects."""
        object_list = []
        self._variations_list = []

        # Use roughly the same show step-begin on each fall-down object.
        show_step = random.randint(
            EARLIEST_ACTION_STEP,
            LATEST_ACTION_STEP_FALL_DOWN
        )

        for i in range(self._choose_fall_down_object_count()):
            successful = False
            for _ in range(util.MAX_TRIES):
                # Ensure the random X position is within the camera's view.
                x_position = util.random_real(
                    -occluders.OCCLUDER_DEFAULT_MAX_X,
                    occluders.OCCLUDER_DEFAULT_MAX_X,
                    util.MIN_RANDOM_INTERVAL
                )

                z_position = choose_position_z()

                # Each object must have an occluder so ensure that they're each
                # positioned far enough away from one another.
                too_close = False
                for instance in object_list:
                    occluder_max_scale_x = (
                        occluders.OCCLUDER_MAX_SCALE_X +
                        occluders.OCCLUDER_SCALE_X_BUFFER
                    )
                    too_close = occluders.calculate_separation_distance(
                        object_x_to_occluder_x(x_position, z_position),
                        occluder_max_scale_x,
                        object_x_to_occluder_x(
                            instance['shows'][0]['position']['x'],
                            instance['shows'][0]['position']['z']
                        ),
                        occluder_max_scale_x
                    ) < 0
                    if too_close:
                        break
                if not too_close:
                    successful = True
                    break
            if not successful:
                raise exceptions.SceneException(
                    f'Cannot position object to fall down object_list='
                    f'{object_list}')

            object_location = {
                'position': {
                    'x': x_position,
                    'y': retrieve_off_screen_position_y(z_position),
                    'z': z_position
                }
            }

            # Add minor variation to this object's show step.
            object_show_step = random.randint(
                max(EARLIEST_ACTION_STEP, show_step - 1),
                min(LATEST_ACTION_STEP_FALL_DOWN, show_step + 1)
            )

            variations = self._choose_object_definition(object_location, i)
            for instance in variations.all():
                instance['shows'][0]['stepBegin'] = object_show_step

            object_list.append(variations.get(VARIATIONS.TRAINED))
            self._variations_list.append(variations)

        return object_list

    def _generate_fall_down_paired_occluder(
        self,
        paired_variations: TargetVariations,
        occluder_list: List[Dict[str, Any]],
        occluder_wall_material_list: List[List[Tuple]]
    ) -> List[Dict[str, Any]]:
        """Generate and return one fall-down paired occluder that must be
        positioned underneath the paired object."""
        paired_object = paired_variations.get(VARIATIONS.TRAINED)
        paired_x = paired_object['shows'][0]['position']['x']
        paired_size = paired_variations.get_max_size_x()
        # Object may be a cylinder at an angle, so use diagonal distance.
        paired_size = math.sqrt(2) * paired_size
        min_scale = min(
            # Add a buffer to the occluder's minimum scale to handle minor
            # changes in size or position-by-step with switched objects.
            paired_size + occluders.OCCLUDER_SCALE_X_BUFFER,
            occluders.OCCLUDER_MAX_SCALE_X
        )
        max_scale = occluders.OCCLUDER_MAX_SCALE_X

        # Adjust the X position using the sight angle from the camera
        # to the object so an occluder will properly hide the object.
        paired_z = paired_object['shows'][0]['position']['z']
        x_position = object_x_to_occluder_x(paired_x, paired_z)

        for occluder in occluder_list:
            if occluder['shape'] == ['pole']:
                continue
            occluder_x = occluder['shows'][0]['position']['x']
            occluder_size = occluder['shows'][0]['scale']['x']
            # Ensure that each occluder is positioned far enough away from one
            # another (this should be done previously, but check again).
            distance = occluders.calculate_separation_distance(
                occluder_x,
                occluder_size,
                x_position,
                paired_size
            )
            if distance < 0:
                print(f'OBJECT={paired_object}\nOCCLUDER_LIST={occluder_list}')
                raise exceptions.SceneException(
                    f'Two fall-down objects were positioned too close '
                    f'distance={distance} object_position={x_position} '
                    f'object_size={paired_size} '
                    f'occluder_position={occluder_x} '
                    f'occluder_size={occluder_size}')
            if distance < (max_scale - min_scale):
                max_scale = min_scale + distance

        # Choose a random size.
        if max_scale <= min_scale:
            x_scale = min_scale
        else:
            x_scale = util.random_real(min_scale, max_scale,
                                       util.MIN_RANDOM_INTERVAL)

        # Choose a left or right sideways pole based on its X position.
        sideways_left = (x_position < 0)
        # If a previous occluder exists, we may need to change our choice.
        if len(occluder_list) > 0:
            # Assume a max of two occluders in fall-down scenes.
            previous_wall = occluder_list[0]
            previous_pole = occluder_list[1]
            previous_x = previous_wall['shows'][0]['position']['x']
            # If both occluders are positioned on the same side of the scene...
            if (
                (sideways_left and previous_x < 0) or
                (not sideways_left and previous_x >= 0)
            ):
                # If the new occluder is closer to the center of the scene than
                # the previous occluder, just change the side its pole is on.
                if (
                    (sideways_left and x_position > previous_x) or
                    (not sideways_left and x_position < previous_x)
                ):
                    sideways_left = (not sideways_left)
                # Else, change the side the previous occluder's pole is on.
                else:
                    previous_pole['shows'][0]['position']['x'] = (
                        occluders.generate_occluder_pole_position_x(
                            previous_wall['shows'][0]['position']['x'],
                            previous_wall['shows'][0]['scale']['x'],
                            (not sideways_left)
                        )
                    )

        return occluders.create_occluder(
            random.choice(random.choice(occluder_wall_material_list)),
            random.choice(materials.METAL_MATERIALS),
            x_position,
            x_scale,
            sideways_left=sideways_left,
            sideways_right=(not sideways_left)
        )

    def _generate_fall_down_paired_occluder_list(
        self,
        occluder_wall_material_list: List[List[Tuple]]
    ) -> List[Dict[str, Any]]:
        """Generate and return needed fall-down paired occluders."""
        paired_list = self._find_fall_down_paired_list()
        occluder_list = []
        for paired_variations in paired_list:
            occluder = self._generate_fall_down_paired_occluder(
                paired_variations,
                occluder_list,
                occluder_wall_material_list
            )
            if not occluder:
                raise exceptions.SceneException(
                    f'Cannot create fall-down paired occluder object='
                    f'{paired_variations.get("trained")} '
                    f'occluder_list={occluder_list}')
            occluder_list.extend(occluder)
        return occluder_list

    def _generate_move_across(
        self,
        occluder_wall_material_list: List[List[Tuple]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate and return move-across objects and occluders."""
        object_list = self._generate_move_across_object_list(
            self._last_step - occluders.OCCLUDER_MOVEMENT_TIME
        )
        occluder_list = self._generate_move_across_paired_occluder_list(
            object_list, occluder_wall_material_list)
        self._generate_occluder_list(
            self._choose_move_across_occluder_count() -
            int(len(occluder_list) / 2),
            occluder_list,
            occluder_wall_material_list,
            False
        )
        return object_list, occluder_list

    def _generate_move_across_object_list(
        self,
        last_action_step: int
    ) -> List[Dict[str, Any]]:
        """Generate and return move-across objects."""
        object_count = self._choose_move_across_object_count()
        object_list = []
        speed_list = []
        self._variations_list = []

        # Each move-across object enters from the same side in Eval 3.
        left_side = random.choice([True, False])

        for i in range(object_count):
            # Choose the object's speed to set its forces and start Y position.
            speed_list.append(
                copy.deepcopy(random.choice(speeds.MOVE_ACROSS_SPEEDS))
            )

            # Choose the object's position and define its location.
            object_position = choose_move_across_object_position(
                left_side,
                speed_list[i]['y'],
                object_list
            )
            object_location = {
                'position': object_position
            }

            # Create the object and its variations.
            variations = self._choose_object_definition(object_location, i)

            # Remove each X distance after the object moves off-screen from
            # its distance-by-step list.
            end_x = 2 * abs(object_position['x'])
            speed_list[i]['distanceByStep'] = [
                # Add/subtract the object's starting X position to/from its
                # X-move-distance in the distance-by-step list of its speed.
                object_position['x'] + (
                    distance if left_side else (-1 * distance)
                )
                for distance in speed_list[i]['distanceByStep'] if (
                    abs(distance) <= end_x
                )
            ]

            object_list.append(variations.get(VARIATIONS.TRAINED))
            self._variations_list.append(variations)

        # Adjust the latest action step by the slowest chosen speed.
        latest_action_step = LATEST_ACTION_STEP_MOVE_ACROSS - max(
            [len(speed['distanceByStep']) for speed in speed_list]
        )

        step_separation = (5 * (object_count - 1))
        if (latest_action_step - EARLIEST_ACTION_STEP) < step_separation:
            raise exceptions.SceneException(
                f'Cannot set object show step because move-across scene does '
                f'not have enough action step variance: {step_separation} '
                f'earliest={EARLIEST_ACTION_STEP} latest={latest_action_step}')

        show_step_list = []
        while len(show_step_list) < object_count:
            for i in range(object_count):
                show_step = random.randint(EARLIEST_ACTION_STEP,
                                           latest_action_step)
                redo = False
                for existing_show_step in show_step_list:
                    if (
                        show_step >= (existing_show_step - 5) and
                        show_step <= (existing_show_step + 5)
                    ):
                        redo = True
                        break
                if redo:
                    show_step_list = []
                    break
                show_step_list.append(show_step)

        for i in range(object_count):
            # Assign the needed properties to each of the object's variations.
            for instance in self._variations_list[i].all():
                instance['shows'][0]['stepBegin'] = show_step_list[i]
                instance['forces'] = [{
                    'stepBegin': show_step_list[i],
                    'stepEnd': show_step_list[i],
                    'vector': {
                        'x': speed_list[i]['force'] * instance['mass'],
                        'y': 0,
                        'z': 0
                    }
                }]

                # Reverse the force and facing if moving right-to-left.
                if not left_side:
                    instance['forces'][0]['vector']['x'] *= -1
                    # Assume all objects start facing left-to-right.
                    instance['shows'][0]['rotation']['y'] += 180

                instance['speed'] = speed_list[i]

        return object_list

    def _generate_move_across_paired_occluder(
        self,
        paired_variations: TargetVariations,
        occluder_list: List[Dict[str, Any]],
        occluder_wall_material_list: List[List[Tuple]]
    ) -> List[Dict[str, Any]]:
        """Generate and return one move-across paired occluder that must be
        positioned at one of the paired object's distance_by_step so that it
        will properly hide the paired object during the implausible event."""
        successful = False
        for _ in range(util.MAX_TRIES):
            paired_object = paired_variations.get(VARIATIONS.TRAINED)
            paired_size = paired_variations.get_max_size_x()
            # Object may be a cube on its corner, so use diagonal distance.
            paired_size = math.sqrt(2) * paired_size
            min_scale = min(
                # Add a buffer to the occluder's minimum scale to handle minor
                # changes in size or distance-by-step with switched objects.
                paired_size + occluders.OCCLUDER_SCALE_X_BUFFER,
                occluders.OCCLUDER_MAX_SCALE_X
            )

            # Choose a random size.
            x_scale = util.random_real(
                min_scale,
                occluders.OCCLUDER_MAX_SCALE_X,
                util.MIN_RANDOM_INTERVAL
            )

            # Choose a random position.
            # The position must correspond with one of the object's positions.
            distance_by_step_list = paired_object['speed']['distanceByStep']
            max_x_position = occluders.OCCLUDER_MAX_X - x_scale / 2
            while True:
                position_index = random.randrange(len(distance_by_step_list))
                paired_x = distance_by_step_list[position_index]
                if -max_x_position <= paired_x <= max_x_position:
                    break

            # Adjust the X position using the sight angle from the camera
            # to the object so an occluder will properly hide the object.
            paired_z = paired_object['shows'][0]['position']['z']
            x_position = object_x_to_occluder_x(paired_x, paired_z)

            # Ensure the new occluder isn't too close to an existing occluder.
            too_close = False
            for occluder in occluder_list:
                too_close = occluders.calculate_separation_distance(
                    occluder['shows'][0]['position']['x'],
                    occluder['shows'][0]['scale']['x'],
                    x_position,
                    x_scale
                ) < 0
                if too_close:
                    break
            if not too_close:
                # Save the occluderIndices needed by specific hypercubes.
                occluder_indices = paired_object['speed'].get(
                    'occluderIndices',
                    []
                )
                occluder_indices.append(position_index)
                paired_object['speed']['occluderIndices'] = occluder_indices
                successful = True
                break
        if successful:
            return occluders.create_occluder(
                random.choice(random.choice(occluder_wall_material_list)),
                random.choice(materials.METAL_MATERIALS),
                x_position,
                x_scale
            )
        return None

    def _generate_move_across_paired_occluder_list(
        self,
        object_list: List[Dict[str, Any]],
        occluder_wall_material_list: List[List[Tuple]]
    ) -> List[Dict[str, Any]]:
        """Generate and return needed move-across paired occluders."""
        paired_list = self._find_move_across_paired_list()
        occluder_list = []
        for paired_variations in paired_list:
            occluder = self._generate_move_across_paired_occluder(
                paired_variations,
                occluder_list,
                occluder_wall_material_list
            )
            if not occluder:
                raise exceptions.SceneException(
                    f'Cannot create move-across paired object='
                    f'{paired_variations.get("trained")} '
                    f'occluder_list={occluder_list}')
            occluder_list.extend(occluder)
        return occluder_list

    def _generate_occluder(
        self,
        occluder_list: List[Dict[str, Any]],
        occluder_wall_material_list: List[List[Tuple]],
        sideways: bool
    ) -> List[Dict[str, Any]]:
        """Generate and return a single occluder."""
        successful = False
        for _ in range(util.MAX_TRIES):
            # Choose a random size.
            x_scale = util.random_real(
                occluders.OCCLUDER_MIN_SCALE_X,
                occluders.OCCLUDER_MAX_SCALE_X,
                util.MIN_RANDOM_INTERVAL
            )
            x_position = occluders.generate_occluder_position(x_scale,
                                                              occluder_list)
            if x_position is not None:
                successful = True
                break
        if successful:
            # Choose a left or right sideways pole based on its X position.
            sideways_left = (x_position < 0) if self.is_fall_down() else False
            sideways_right = (
                (not sideways_left) if self.is_fall_down() else False
            )
            return occluders.create_occluder(
                random.choice(random.choice(occluder_wall_material_list)),
                random.choice(materials.METAL_MATERIALS),
                x_position,
                x_scale,
                sideways_left=sideways_left,
                sideways_right=sideways_right
            )
        return None

    def _generate_occluder_list(
        self,
        number: int,
        occluder_list: List[Dict[str, Any]],
        occluder_wall_material_list: List[List[Tuple]],
        sideways: bool
    ) -> None:
        """Generate occluders and add them to the given occluder_list."""
        for _ in range(number):
            occluder = self._generate_occluder(occluder_list,
                                               occluder_wall_material_list,
                                               sideways)
            if not occluder:
                raise exceptions.SceneException(
                    f'Cannot create occluder occluder_list={occluder_list}')
            occluder_list.extend(occluder)

    def _init_each_object_definition_list(self, is_fall_down: bool) -> None:
        """Set each object definition list needed by this hypercube, used in
        _choose_object_definition."""

        # List with each possible intuitive physics object definition (shape)
        # and material (color) combination for the specific scene setup.
        definition_list = util.retrieve_complete_definition_list(
            [objects.get_intuitive_physics(is_fall_down)]
        )[0]
        self._trained_definition_list = (
            util.retrieve_trained_definition_list([definition_list])
        )[0]
        self._untrained_shape_definition_list = (
            util.retrieve_untrained_definition_list(
                [definition_list],
                tags.SCENE.UNTRAINED_SHAPE
            )
        )[0]
        self._untrained_size_definition_list = (
            util.retrieve_untrained_definition_list(
                [definition_list],
                tags.SCENE.UNTRAINED_SIZE
            )
        )[0]

    def _separate_targets_and_non_targets(
        self,
        moving_object_list: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return the target and non-target lists from the given moving object
        list."""
        return moving_object_list, []

    def _update_object_tags(
        self,
        scene: Dict[str, Any],
        object_list: List[Dict[str, Any]],
        role: str
    ) -> Dict[str, Any]:
        """Update and return the given scene with info from targets in the
        given list because targets were added or removed."""

        important_tag_list = [
            tags.SCENE.TRAINED, tags.SCENE.TRAINED_COLOR,
            tags.SCENE.TRAINED_COMBINATION, tags.SCENE.TRAINED_SHAPE,
            tags.SCENE.TRAINED_SIZE, tags.SCENE.UNTRAINED,
            tags.SCENE.UNTRAINED_COLOR, tags.SCENE.UNTRAINED_COMBINATION,
            tags.SCENE.UNTRAINED_SHAPE, tags.SCENE.UNTRAINED_SIZE
        ]

        for tag in important_tag_list:
            scene['goal']['sceneInfo'][tag][tags.role_to_key(role)] = False

        scene['goal']['objectsInfo']['all'] = []
        scene['goal']['objectsInfo'][tags.role_to_key(role)] = []

        for instance in object_list:
            role_to_object_list = {}
            role_to_object_list[role] = object_list
            tags.append_object_tags_of_type(
                scene['goal']['sceneInfo'],
                scene['goal']['objectsInfo'],
                role_to_object_list,
                role
            )
            scene['goal']['objectsInfo'][tags.role_to_key(role)].extend(
                instance['info']
            )
            instance['info'].append(role)
            instance['role'] = role
            instance[tags.role_to_tag(role)] = True

        scene = hypercubes.update_scene_objects_tag_lists(scene)
        return scene

    def _update_hypercube_scene_info_tags(
        self,
        scenes: Dict[str, Dict[str, Any]],
        tag_list: List[str]
    ) -> Dict[str, Any]:
        """Update and return the hypercube and target tags in each scene from
        the given scene dictionary."""

        for scene_id, scene in scenes.items():
            # Update the target-specific and non-target-specific scene tags
            # since a target or non-target may have been changed or added.
            for role in [tags.ROLES.TARGET, tags.ROLES.NON_TARGET]:
                self._update_object_tags(scene, [
                    instance for instance in scene['objects']
                    if instance['role'] == role
                ], role)

            # Finalize the complete scene slice list.
            for tag in tag_list:
                scene['goal']['sceneInfo'][tags.SCENE.SLICES].append(
                    tags.tag_to_label(tag) + ' ' +
                    str(scene['goal']['sceneInfo'][tag])
                )

            scene['goal']['sceneInfo'][tags.SCENE.ID] = [scene_id]

    def is_fall_down(self) -> bool:
        """Return if this is a fall-down hypercube."""
        return self._scene_setup_function == (
            IntuitivePhysicsHypercube._generate_fall_down
        )

    def is_move_across(self) -> bool:
        """Return if this is a move-across hypercube."""
        return self._scene_setup_function == (
            IntuitivePhysicsHypercube._generate_move_across
        )


class GravitySupportHypercube(IntuitivePhysicsHypercube):
    GOAL_TEMPLATE = {
        'category': tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS),
        'domainsInfo': {
            'objects': [
                tags.DOMAINS.OBJECTS_3,
                tags.DOMAINS.OBJECTS_10
            ],
            'places': [],
            'agents': []
        },
        'sceneInfo': {}
    }

    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.PRIMARY] = (
        tags.tag_to_label(tags.SCENE.PASSIVE)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.SECONDARY] = (
        tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.TERTIARY] = (
        tags.tag_to_label(tags.SCENE.GRAVITY_SUPPORT)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.QUATERNARY] = (
        tags.tag_to_label(tags.SCENE.ACTION_NONE)
    )

    def __init__(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str],
        training=False,
        is_fall_down=False,
        is_move_across=False
    ):
        super().__init__(
            tags.ABBREV.GRAVITY_SUPPORT.upper(),
            body_template,
            GravitySupportHypercube.GOAL_TEMPLATE,
            role_to_type,
            # All gravity support scenes are fall-down in Eval 4.
            is_fall_down=True,
            is_move_across=False,
            training=training
        )

    # Override
    def _create_default_objects(
        self,
        room_wall_material_name: str,
        room_wall_colors: List[str]
    ) -> Dict[str, Any]:
        """Generate and return this hypercube's objects in a dict of roles with
        their corresponding object lists."""

        self._target = self._create_gravity_support_target()
        structural_object_material_list = (
            self._find_structural_object_material_list(room_wall_material_name)
        )
        self._visible_support = self._create_visible_support_object(
            self._target,
            structural_object_material_list
        )
        factor = 1.0 / GRAVITY_SUPPORT_MOVE

        # Add the "attached-to-pole" movement to all target variations.
        for instance in self._target.all():
            # Adjust target Y position with visible support object Y size.
            instance['shows'][0]['position']['y'] = (
                round(instance['shows'][0]['position']['y'] * factor) / factor
            ) + self._visible_support['dimensions']['y'] + 0.005 + (
                instance['dimensions']['y'] / 2.0
            )
            self._update_object_movement(
                instance,
                instance['shows'][0]['position']['y'],
                instance['dimensions']['y'],
                self._visible_support['dimensions']['y']
            )
            # Enable gravity physics once "attached-to-pole" movement is done.
            instance['togglePhysics'] = [{
                'stepBegin': (
                    instance['moves'][-1]['stepEnd'] + 1 + GRAVITY_SUPPORT_WAIT
                )
            }]

        self._pole = self._create_pole(self._target, self._visible_support)

        # Save the default objects. These objects will be replaced as needed in
        # _create_intuitive_physics_scenes.
        role_to_object_list = {}
        role_to_object_list[tags.ROLES.TARGET] = [
            self._target.get(VARIATIONS.SYMMETRIC)
        ]
        role_to_object_list[tags.ROLES.STRUCTURAL] = [
            self._pole.get(VARIATIONS.SYMMETRIC), self._visible_support
        ]
        return role_to_object_list

    # Override
    def _init_each_object_definition_list(self, is_fall_down: bool) -> None:
        """Set each object definition list needed by this hypercube, used in
        _choose_object_definition."""
        # Not used since we override _create_default_objects.
        pass

    def _create_gravity_support_target(self) -> TargetVariations:
        # Retrieve each base target object definition lists.
        base_symmetric_list = util.retrieve_complete_definition_list(
            [gravity_support_objects.get_symmetric_target_definition_list()]
        )[0]
        base_asymmetric_list = util.retrieve_complete_definition_list(
            [gravity_support_objects.get_asymmetric_target_definition_list()]
        )[0]

        # Restrict object to a specific type, if type was given as input.
        symmetric_object_type = self._role_to_type.get('symmetric')
        asymmetric_object_type = self._role_to_type.get('asymmetric')
        base_symmetric_list = self._filter_definition_list_on_type(
            base_symmetric_list,
            symmetric_object_type
        )
        base_asymmetric_list = self._filter_definition_list_on_type(
            base_asymmetric_list,
            asymmetric_object_type
        )

        # Choose symmetric target object definition.
        definitions = {}
        definitions[VARIATIONS.SYMMETRIC] = random.choice(base_symmetric_list)

        # Restrict asymmetric target object definition to same size/material.
        modified_asymmetric_list = [
            definition for definition in base_asymmetric_list
            if util.is_similar_except_in_shape(
                definitions[VARIATIONS.SYMMETRIC],
                definition,
                only_x_dimension=True
            )
        ]
        if len(modified_asymmetric_list) == 0:
            raise exceptions.SceneException(
                f'Intuitive physics gravity support asymmetric target object  '
                f'list does not have any options with same size and material: '
                f'{definitions[VARIATIONS.SYMMETRIC]}')

        # Choose asymmetric target object definition.
        definitions[VARIATIONS.ASYMMETRIC_LEFT] = random.choice(
            modified_asymmetric_list
        )

        # Copy the asymmetric target object to add a reversed definition.
        # (We'll rotate the reversed instance later.)
        definitions[VARIATIONS.ASYMMETRIC_RIGHT] = copy.deepcopy(
            definitions[VARIATIONS.ASYMMETRIC_LEFT]
        )

        # Choose target object location.
        target_z_position = choose_position_z()
        target_location = {
            'position': {
                'x': random.randrange(
                    -GRAVITY_SUPPORT_MAX_ONSCREEN_X * 100,
                    GRAVITY_SUPPORT_MAX_ONSCREEN_X * 100,
                    5
                ) / 100.0,
                'y': retrieve_off_screen_position_y(target_z_position),
                'z': target_z_position
            }
        }

        target_variations = TargetVariations(
            definitions,
            target_location,
            self.is_fall_down()
        )

        # Rotate the asymmetric target instance so it's reversed.
        reversed_instance = target_variations.get(VARIATIONS.ASYMMETRIC_RIGHT)
        reversed_instance['shows'][0]['rotation']['y'] += 180

        # Choose target object step to appear.
        show_step = random.randint(1, 10)

        for instance in target_variations.all():
            instance['shows'][0]['stepBegin'] = show_step
            # Will update the movement once the visible support is made.
            instance['moves'] = [
                copy.deepcopy(GRAVITY_SUPPORT_MOVEMENT)
            ]
            # Ignore gravity physics before pole disconnects.
            instance['kinematic'] = True

        return target_variations

    def _create_pole(
        self,
        target_variations: TargetVariations,
        visible_support: Dict[str, Any]
    ) -> ObjectVariations:
        target_symmetric = target_variations.get(VARIATIONS.SYMMETRIC)
        target_asymmetric_left = target_variations.get(
            VARIATIONS.ASYMMETRIC_LEFT
        )
        target_asymmetric_right = target_variations.get(
            VARIATIONS.ASYMMETRIC_RIGHT
        )

        # Create a pole template to use with all target variations.
        pole_template = gravity_support_objects.create_pole_template(
            # Assume all target variations will have the same show step.
            target_symmetric['shows'][0]['stepBegin']
        )
        # The pole will descend and then ascend in scripted movement.
        pole_template['moves'] = [
            copy.deepcopy(GRAVITY_SUPPORT_MOVEMENT),
            copy.deepcopy(GRAVITY_SUPPORT_MOVEMENT)
        ]
        pole_template['moves'][1]['vector']['y'] *= -1

        # Create a pole variation for all target variations.
        pole_instances = {}
        for name, target, multiplier in [
            (VARIATIONS.SYMMETRIC, target_symmetric, 0),
            (VARIATIONS.ASYMMETRIC_LEFT, target_asymmetric_left, 1),
            (VARIATIONS.ASYMMETRIC_RIGHT, target_asymmetric_right, -1)
        ]:
            pole_copy = copy.deepcopy(pole_template)
            # Use the target's position for the pole's position.
            target_position = target['shows'][0]['position']
            pole_copy['shows'][0]['position']['x'] = target_position['x']
            pole_copy['shows'][0]['position']['z'] = target_position['z']
            # Add the scripted pole movement config.
            pole_instances[name] = self._update_object_movement(
                pole_copy,
                target['shows'][0]['position']['y'],
                target['dimensions']['y'],
                visible_support['dimensions']['y']
            )
            target_definition = target_variations._definitions[name]
            # Adjust the pole Y position using the target Y position and size.
            target_y_top = target['shows'][0]['position']['y'] + (
                target['dimensions']['y'] / 2.0
            ) - (
                target['dimensions']['y'] *
                target_definition.get('poleOffsetY', 0)
            )
            pole_instances[name]['shows'][0]['position']['y'] = (
                target_y_top + pole_instances[name]['shows'][0]['scale']['y']
            )
            pole_inactive_step = target['togglePhysics'][0]['stepBegin']
            # The pole must change colors once it begins to rise.
            pole_instances[name]['changeMaterials'][0]['stepBegin'] = (
                pole_inactive_step
            )
            # The pole must record its state.
            pole_instances[name]['states'] = (
                [POLE_ACTIVE] * (pole_inactive_step + 1) +
                [POLE_INACTIVE] * (self._last_step - pole_inactive_step)
            )
            # Update the pole's position with the asymmetric offset, if any.
            # The pole is normally positioned over the middle of the target,
            # but may be adjusted with asymmetric shapes like triangles or Ls.
            target_rotation = target_definition.get('rotation', {'y': 0})['y']
            target_offset_x = target_definition.get('poleOffsetX', 0) * (
                target['shows'][0]['scale']['z']
                if (target_rotation == -90 or target_rotation == 90)
                else target['shows'][0]['scale']['x']
            )
            pole_instances[name]['shows'][0]['position']['x'] += (
                multiplier * target_offset_x
            )

        return ObjectVariations(pole_instances)

    def _create_visible_support_object(
        self,
        target_variations: TargetVariations,
        structural_object_material_list: List[Tuple[str, List[str]]]
    ) -> Dict[str, Any]:
        # Finalize the object definition to set the object's final dimensions.
        definition = util.finalize_object_definition(
            gravity_support_objects.get_visible_support_object_definition()
        )
        # Choose a random material (and color) from the given list.
        material_and_color = random.choice(random.choice(
            structural_object_material_list
        ))
        definition['materials'] = [material_and_color[0]]
        definition['color'] = material_and_color[1]
        target_symmetric = target_variations.get(VARIATIONS.SYMMETRIC)
        # Create and return the visible support positioned under the target.
        location = {
            'position': {
                # Assume all target variations will have the same X position.
                'x': target_symmetric['shows'][0]['position']['x'],
                'y': definition['positionY'],
                # Assume all target variations will have the same Z position.
                'z': target_symmetric['shows'][0]['position']['z']
            }
        }
        return util.instantiate_object(definition, location)

    def _update_object_movement(
        self,
        instance: Dict[str, Any],
        falling_object_y_position: float,
        falling_object_y_scale: float,
        support_object_y_scale: float
    ) -> Dict[str, Any]:
        # Find the Y distance between the falling and support objects.
        move_y_total = falling_object_y_position - support_object_y_scale - (
            falling_object_y_scale / 2.0
        )
        # Find the Y distance in steps. Assume this will always divide evenly.
        move_step_total = int(move_y_total / GRAVITY_SUPPORT_MOVE)
        # Assume the show step was set in the instance previously.
        show_step = instance['shows'][0]['stepBegin']
        # Move the falling object from its starting position down to be just
        # above the support object.
        instance['moves'][0]['stepBegin'] = show_step
        instance['moves'][0]['stepEnd'] = show_step + move_step_total - 1
        # If the falling object is the pole, make it rise again afterward.
        if len(instance['moves']) > 1:
            instance['moves'][1]['stepBegin'] = (
                instance['moves'][0]['stepEnd'] + 1 +
                (2 * GRAVITY_SUPPORT_WAIT)
            )
            instance['moves'][1]['stepEnd'] = (
                instance['moves'][1]['stepBegin'] + move_step_total - 1
            )
        return instance

    def _get_scene_ids(self) -> List[int]:
        return [
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p'
        ]

    def _get_scene_ids_implausible(self) -> List[int]:
        return ['c', 'd', 'g', 'h', 'k', 'l', 'o', 'p']

    def _get_scene_ids_implausible_float(self) -> List[int]:
        return ['o', 'p']

    def _get_scene_ids_implausible_force(self) -> List[int]:
        return []

    def _get_scene_ids_implausible_support(self) -> List[int]:
        return ['c', 'd', 'g', 'h', 'k', 'l']

    def _get_scene_ids_move_target(self) -> List[int]:
        return ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l']

    def _get_scene_ids_target_support_none(self) -> List[int]:
        return ['a', 'b', 'c', 'd']

    def _get_scene_ids_target_support_minimal(self) -> List[int]:
        return ['e', 'f', 'g', 'h']

    def _get_scene_ids_target_support_25(self) -> List[int]:
        return ['i', 'j', 'k', 'l']

    # Override
    def _create_intuitive_physics_scenes(
        self,
        default_scene: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        target_id = self._target.get(VARIATIONS.SYMMETRIC)['id']
        pole_id = self._pole.get(VARIATIONS.SYMMETRIC)['id']

        # Choose to move the target right (positive) or left (negative).
        is_positive = random.choice([True, False])

        # Choose the multipler of the target's movement in no-support scenes.
        # Must be a max of # 1.5 so the target is always in view of the camera.
        no_support_multiplier = 0.5 + (random.randint(1, 10) / 20.0)

        # Choose the height of the invisible support in the implausible
        # full-support scenes (evenly divisible by GRAVITY_SUPPORT_MOVE).
        implausible_support_y = random.randint(1, (1 / GRAVITY_SUPPORT_MOVE))

        # Initialize scenes.
        scenes = {}
        for i in self._get_scene_ids():
            scenes[i + '1'] = copy.deepcopy(default_scene)
            scenes[i + '1']['goal']['sceneInfo'][tags.SCENE.DIRECTION] = (
                'right' if is_positive else 'left'
            )

        # Initialize gravity support tags in scenes.
        for scene in scenes.values():
            scene['goal']['sceneInfo'][tags.SCENE.SLICES] = []
            scene['goal']['sceneInfo'][
                tags.TYPES.GRAVITY_SUPPORT_PLAUSIBLE
            ] = tags.CELLS.GRAVITY_SUPPORT_PLAUSIBLE.YES
            scene['goal']['sceneInfo'][
                tags.TYPES.GRAVITY_SUPPORT_TARGET_POSITION
            ] = tags.CELLS.GRAVITY_SUPPORT_TARGET_POSITION.FULL
            scene['goal']['sceneInfo'][
                tags.TYPES.GRAVITY_SUPPORT_TARGET_TYPE
            ] = tags.CELLS.GRAVITY_SUPPORT_TARGET_TYPE.SYMMETRIC

        # Switch target with its asymmetric variation.
        self._update_asymmetric_target_slice_scene(scenes, is_positive)

        # Move target X position.
        for i in self._get_scene_ids_move_target():
            scene = scenes[i + '1']
            x_position_multiplier = 0
            # Move target to its no-support X position.
            if i in self._get_scene_ids_target_support_none():
                scene['goal']['sceneInfo'][
                    tags.TYPES.GRAVITY_SUPPORT_TARGET_POSITION
                ] = tags.CELLS.GRAVITY_SUPPORT_TARGET_POSITION.NONE
                x_position_multiplier = no_support_multiplier
            # Move target to its minimal-support X position.
            if i in self._get_scene_ids_target_support_minimal():
                scene['goal']['sceneInfo'][
                    tags.TYPES.GRAVITY_SUPPORT_TARGET_POSITION
                ] = tags.CELLS.GRAVITY_SUPPORT_TARGET_POSITION.MINIMAL
                x_position_multiplier = 0.45
            # Move target to its 25%-supported X position.
            if i in self._get_scene_ids_target_support_25():
                scene['goal']['sceneInfo'][
                    tags.TYPES.GRAVITY_SUPPORT_TARGET_POSITION
                ] = tags.CELLS.GRAVITY_SUPPORT_TARGET_POSITION.HALF
                x_position_multiplier = 0.25
            for instance in scene['objects']:
                if instance['id'] == target_id:
                    modifier = ((
                        (self._visible_support['dimensions']['x'] / 2.0) +
                        (x_position_multiplier * instance['dimensions']['x'])
                    ) * (1 if is_positive else -1))
                    instance['shows'][0]['position']['x'] += modifier
                    break
            for instance in scene['objects']:
                if instance['id'] == pole_id:
                    instance['shows'][0]['position']['x'] += modifier
                    break

        # Implausible scenes.
        for i in self._get_scene_ids_implausible():
            scene = scenes[i + '1']
            scene['evaluationOnly'] = True
            scene['goal']['answer']['choice'] = IMPLAUSIBLE
            scene['goal']['sceneInfo'][
                tags.TYPES.GRAVITY_SUPPORT_PLAUSIBLE
            ] = tags.CELLS.GRAVITY_SUPPORT_PLAUSIBLE.NO
            # Add an invisible support on the floor next to the visible one.
            if i in self._get_scene_ids_implausible_support():
                target = None
                for instance in scene['objects']:
                    if instance['id'] == target_id:
                        self._place_invisible_support_on_floor(
                            scene,
                            instance,
                            is_positive
                        )
                        break
            # Add an invisible wind to blow over the target object.
            if i in self._get_scene_ids_implausible_force():
                for instance in scene['objects']:
                    if instance['id'] == target_id:
                        self._shove_target_off_its_support(
                            instance,
                            is_positive
                        )
                        break
            # Add an invisible support on top of the visible support.
            if i in self._get_scene_ids_implausible_float():
                target = None
                pole = None
                for instance in scene['objects']:
                    if instance['id'] == target_id:
                        target = instance
                    if instance['id'] == pole_id:
                        pole = instance
                self._stack_invisible_support_on_support(
                    scene,
                    target,
                    pole,
                    implausible_support_y
                )

        # Finalize scenes.
        self._update_hypercube_scene_info_tags(scenes, [
            tags.TYPES.GRAVITY_SUPPORT_PLAUSIBLE,
            tags.TYPES.GRAVITY_SUPPORT_TARGET_POSITION,
            tags.TYPES.GRAVITY_SUPPORT_TARGET_TYPE
        ])

        return scenes

    def _update_asymmetric_target_slice_scene(
        self,
        scenes: Dict[str, Dict[str, Any]],
        is_positive: bool
    ) -> None:
        """Update the scene with the given asymmetric target slice ID."""
        target_asymmetric_left = self._target.get(VARIATIONS.ASYMMETRIC_LEFT)
        target_asymmetric_right = self._target.get(VARIATIONS.ASYMMETRIC_RIGHT)
        pole_asymmetric_left = self._pole.get(VARIATIONS.ASYMMETRIC_LEFT)
        pole_asymmetric_right = self._pole.get(VARIATIONS.ASYMMETRIC_RIGHT)
        for i in ['b', 'd', 'f', 'h', 'j', 'l', 'n', 'p']:
            scene = scenes[i + '1']
            scene['goal']['sceneInfo'][
                tags.TYPES.GRAVITY_SUPPORT_TARGET_TYPE
            ] = tags.CELLS.GRAVITY_SUPPORT_TARGET_TYPE.ASYMMETRIC
            # Assume any asymmetric object is right-to-left (like an L).
            # Create copies of the corresponding target and pole.
            target_asymmetric = copy.deepcopy(
                target_asymmetric_right if is_positive
                else target_asymmetric_left
            )
            pole_asymmetric = copy.deepcopy(
                pole_asymmetric_right if is_positive else pole_asymmetric_left
            )
            # In 25%-support scenes, position target at its center of mass.
            if i in ['j', 'l']:
                self._position_on_center_of_mass(
                    self._target._definitions[VARIATIONS.ASYMMETRIC_LEFT],
                    target_asymmetric,
                    pole_asymmetric,
                    self._target.get(VARIATIONS.SYMMETRIC),
                    is_positive
                )
            for index in range(len(scene['objects'])):
                if scene['objects'][index]['id'] == target_asymmetric['id']:
                    scene['objects'][index] = target_asymmetric
                if scene['objects'][index]['id'] == pole_asymmetric['id']:
                    scene['objects'][index] = pole_asymmetric

    def _find_center_of_mass_x(
        self,
        target_asymmetric_definition: Dict[str, Any],
        flip: bool
    ) -> float:
        # Assume each asymmetric defintion has a poly property.
        asymmetric_poly = geometry.rect_to_poly(
            target_asymmetric_definition['poly']
        )

        # If needed, flip the asymmetric target.
        if flip:
            asymmetric_poly = affinity.scale(
                asymmetric_poly,
                xfact=-1,
                origin=(0, 0)
            )

        # Use shapely to find the asymmetric target's center of mass.
        return asymmetric_poly.centroid.coords[0][0]

    def _position_on_center_of_mass(
        self,
        target_asymmetric_definition: Dict[str, Any],
        target_asymmetric: Dict[str, Any],
        pole_asymmetric: Dict[str, Any],
        target_symmetric: Dict[str, Any],
        flip: bool
    ) -> None:
        asymmetric_center = self._find_center_of_mass_x(
            target_asymmetric_definition,
            flip
        )

        # Adjust the position of each asymmetric object for its center of mass.
        pole_asymmetric['shows'][0]['position']['x'] -= asymmetric_center
        target_asymmetric['shows'][0]['position']['x'] -= asymmetric_center
        target_asymmetric['shows'][0]['boundingBox'] = [{
            'x': corner['x'] - asymmetric_center, 'y': corner['y'],
            'z': corner['z']
        } for corner in target_asymmetric['shows'][0]['boundingBox']]

    def _place_invisible_support_on_floor(
        self,
        scene: Dict[str, Any],
        target: Dict[str, Any],
        is_positive: bool
    ) -> None:
        invisible_support = copy.deepcopy(self._visible_support)
        invisible_support['id'] = 'invisible_support'
        invisible_support['shows'][0]['position']['x'] += (
            (1 if is_positive else -1) *
            (self._visible_support['dimensions']['x'] + 0.05)
        )
        invisible_support['shrouds'] = [{
            'stepBegin': 0,
            'stepEnd': self._last_step + 1
        }]

        # If the target is in its no-support position, we may just need to move
        # the invisible support directly under the target.
        target_position = target['shows'][0]['position']['x']
        support_position = invisible_support['shows'][0]['position']['x']
        if (
            (is_positive and target_position > support_position) or
            (not is_positive and target_position < support_position)
        ):
            invisible_support['shows'][0]['position']['x'] = target_position

        scene['objects'].append(invisible_support)

    def _shove_target_off_its_support(
        self,
        instance: Dict[str, Any],
        is_positive: bool
    ) -> None:
        wind_step = instance['togglePhysics'][0]['stepBegin'] + 1 + (
            2 * GRAVITY_SUPPORT_WAIT
        )
        instance['forces'] = [{
            'stepBegin': wind_step,
            'stepEnd': wind_step,
            'vector': {
                'x': (
                    (1 if is_positive else -1) * instance['mass'] *
                    GRAVITY_SUPPORT_WIND
                ),
                'y': 0,
                'z': 0
            }
        }]

    def _stack_invisible_support_on_support(
        self,
        scene: Dict[str, Any],
        target: Dict[str, Any],
        pole: Dict[str, Any],
        implausible_support_y: float
    ) -> None:
        invisible_support = copy.deepcopy(self._visible_support)
        invisible_support['id'] = 'invisible_support'
        height = implausible_support_y * GRAVITY_SUPPORT_MOVE
        invisible_support['dimensions']['y'] = height
        invisible_support['shows'][0]['scale']['y'] = height
        invisible_support['shows'][0]['position']['y'] = (
            self._visible_support['dimensions']['y'] +
            (invisible_support['shows'][0]['scale']['y'] / 2.0)
        )
        invisible_support['shrouds'] = [{
            'stepBegin': 0,
            'stepEnd': self._last_step + 1
        }]
        scene['objects'].append(invisible_support)
        target['moves'][0]['stepEnd'] -= implausible_support_y
        target['togglePhysics'][0]['stepBegin'] -= implausible_support_y
        pole['changeMaterials'][0]['stepBegin'] -= implausible_support_y
        pole['moves'][0]['stepEnd'] -= implausible_support_y
        pole['moves'][1]['stepBegin'] -= implausible_support_y
        pole['moves'][1]['stepEnd'] -= (2 * implausible_support_y)


class ObjectPermanenceHypercube(IntuitivePhysicsHypercube):
    GOAL_TEMPLATE = {
        'category': tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS),
        'domainsInfo': {
            'objects': [
                tags.DOMAINS.OBJECTS_4
            ],
            'places': [],
            'agents': []
        },
        'sceneInfo': {}
    }

    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.PRIMARY] = (
        tags.tag_to_label(tags.SCENE.PASSIVE)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.SECONDARY] = (
        tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.TERTIARY] = (
        tags.tag_to_label(tags.SCENE.OBJECT_PERMANENCE)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.QUATERNARY] = (
        tags.tag_to_label(tags.SCENE.ACTION_NONE)
    )

    def __init__(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str],
        training=False,
        is_fall_down=False,
        is_move_across=False
    ):
        super().__init__(
            tags.ABBREV.OBJECT_PERMANENCE.upper(),
            body_template,
            ObjectPermanenceHypercube.GOAL_TEMPLATE,
            role_to_type,
            # All object permanence scenes are fall-down in Eval 3.
            is_fall_down=True,
            is_move_across=False,
            training=training
        )

    def _appear_behind_occluder(
        self,
        scene: Dict[str, Any],
        target_id: str
    ) -> None:
        target = [
            instance for instance in scene['objects']
            if instance['id'] == target_id
        ][0]

        if self.is_move_across():
            # Implausible event happens after target moves behind occluder.
            occluder_index = target['speed']['occluderIndices'][0]
            implausible_event_step = occluder_index + \
                target['forces'][0]['stepBegin']
            # Set target's X position behind occluder.
            target_appear_x = target['speed']['distanceByStep'][occluder_index]
            target['shows'][0]['position']['x'] = target_appear_x

        elif self.is_fall_down():
            # Implausible event happens after target falls behind occluder.
            implausible_event_step = (
                OBJECT_FALL_TIME + target['shows'][0]['stepBegin']
            )
            # Set target's Y position stationary on the ground.
            y_position = retrieve_off_screen_position_y(
                target['shows'][0]['position']['z']
            )
            target['shows'][0]['position']['y'] -= y_position

        else:
            raise exceptions.SceneException('Unknown scene setup function!')

        # Set target to appear at implausible event step.
        target['shows'][0]['stepBegin'] = implausible_event_step

    def _disappear_behind_occluder(
        self,
        scene: Dict[str, Any],
        target_id: str
    ) -> None:
        target = [
            instance for instance in scene['objects']
            if instance['id'] == target_id
        ][0]

        if self.is_move_across():
            # Implausible event happens after target moves behind occluder.
            occluder_index = target['speed']['occluderIndices'][0]
            implausible_event_step = occluder_index + \
                target['forces'][0]['stepBegin']

        elif self.is_fall_down():
            # Implausible event happens after target falls behind occluder.
            implausible_event_step = (
                OBJECT_FALL_TIME + target['shows'][0]['stepBegin']
            )

        else:
            raise exceptions.SceneException('Unknown scene setup function!')

        # Set target to disappear at implausible event step.
        target['hides'] = [{
            'stepBegin': implausible_event_step
        }]

    # Override
    def _create_intuitive_physics_scenes(
        self,
        default_scene: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        target_id_1 = self._target_list[0]['id']
        target_id_2 = self._target_list[1]['id']

        # Variations on object one.
        variations_1 = self._variations_list[0]
        shape_variation_1 = variations_1.get(VARIATIONS.UNTRAINED_SHAPE)
        size_variation_1 = variations_1.get(VARIATIONS.UNTRAINED_SIZE)

        # Variations on object two.
        variations_2 = self._variations_list[1]
        shape_variation_2 = variations_2.get(VARIATIONS.UNTRAINED_SHAPE)
        size_variation_2 = variations_2.get(VARIATIONS.UNTRAINED_SIZE)

        # Initialize scenes.
        scenes = {}
        for i in ['a', 'b', 'c', 'j', 'k', 'l', 's', 't', 'u']:
            scenes[i + '1'] = copy.deepcopy(default_scene)
        for i in [
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            'aa'
        ]:
            for j in [i + '2', i + '3', i + '4']:
                scenes[j] = copy.deepcopy(default_scene)

        # Initialize object permanence tags in scenes.
        for scene in scenes.values():
            scene['goal']['sceneInfo'][tags.SCENE.SLICES] = []
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_OBJECT_ONE
            ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_ONE.NO_CHANGE
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_OBJECT_TWO
            ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_TWO.NO_CHANGE
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_NOVELTY_ONE
            ] = tags.CELLS.OBJECT_PERMANENCE_NOVELTY_ONE.NONE
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_NOVELTY_TWO
            ] = tags.CELLS.OBJECT_PERMANENCE_NOVELTY_TWO.NONE

        # Remove object two completely.
        for i in ['a', 'b', 'c', 'j', 'k', 'l', 's', 't', 'u']:
            scene = scenes[i + '1']
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_OBJECT_TWO
            ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_TWO.NONE
            for index in range(len(scene['objects'])):
                if scene['objects'][index]['id'] == target_id_2:
                    del scene['objects'][index]
                    break

        # Switch object one with its untrained size variation.
        for i in ['b', 'e', 'h', 'k', 'n', 'q', 't', 'w', 'z']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['sceneInfo'][
                    tags.TYPES.OBJECT_PERMANENCE_NOVELTY_ONE
                ] = tags.CELLS.OBJECT_PERMANENCE_NOVELTY_ONE.SIZE
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id_1:
                        scene['objects'][index] = (
                            copy.deepcopy(size_variation_1)
                        )
                        break

        # Switch object one with its untrained shape variation.
        for i in ['c', 'f', 'i', 'l', 'o', 'r', 'u', 'x', 'aa']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['sceneInfo'][
                    tags.TYPES.OBJECT_PERMANENCE_NOVELTY_ONE
                ] = tags.CELLS.OBJECT_PERMANENCE_NOVELTY_ONE.SHAPE
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id_1:
                        scene['objects'][index] = (
                            copy.deepcopy(shape_variation_1)
                        )
                        break

        # Switch object two with its untrained size variation.
        for i in ['d', 'e', 'f', 'm', 'n', 'o', 'v', 'w', 'x']:
            for j in [i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['sceneInfo'][
                    tags.TYPES.OBJECT_PERMANENCE_NOVELTY_TWO
                ] = tags.CELLS.OBJECT_PERMANENCE_NOVELTY_TWO.SIZE
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id_2:
                        scene['objects'][index] = (
                            copy.deepcopy(size_variation_2)
                        )
                        break

        # Switch object two with its untrained shape variation.
        for i in ['g', 'h', 'i', 'p', 'q', 'r', 'y', 'z', 'aa']:
            for j in [i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['sceneInfo'][
                    tags.TYPES.OBJECT_PERMANENCE_NOVELTY_TWO
                ] = tags.CELLS.OBJECT_PERMANENCE_NOVELTY_TWO.SHAPE
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id_2:
                        scene['objects'][index] = (
                            copy.deepcopy(shape_variation_2)
                        )
                        break

        # Make object one disappear.
        for i in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['answer']['choice'] = IMPLAUSIBLE
                scene['goal']['sceneInfo'][
                    tags.TYPES.OBJECT_PERMANENCE_OBJECT_ONE
                ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_ONE.DISAPPEAR
                self._disappear_behind_occluder(scene, target_id_1)

        # Make object one appear.
        for i in ['j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['answer']['choice'] = IMPLAUSIBLE
                scene['goal']['sceneInfo'][
                    tags.TYPES.OBJECT_PERMANENCE_OBJECT_ONE
                ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_ONE.APPEAR
                self._appear_behind_occluder(scene, target_id_1)

        for i in [
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            'aa'
        ]:
            # Make object two disappear.
            scene = scenes[i + '4']
            scene['evaluationOnly'] = True
            scene['goal']['answer']['choice'] = IMPLAUSIBLE
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_OBJECT_TWO
            ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_TWO.DISAPPEAR
            self._disappear_behind_occluder(scene, target_id_2)

            # Make object two appear.
            scene = scenes[i + '3']
            scene['evaluationOnly'] = True
            scene['goal']['answer']['choice'] = IMPLAUSIBLE
            scene['goal']['sceneInfo'][
                tags.TYPES.OBJECT_PERMANENCE_OBJECT_TWO
            ] = tags.CELLS.OBJECT_PERMANENCE_OBJECT_TWO.APPEAR
            self._appear_behind_occluder(scene, target_id_2)

        # Finalize scenes.
        self._update_hypercube_scene_info_tags(scenes, [
            tags.TYPES.OBJECT_PERMANENCE_OBJECT_ONE,
            tags.TYPES.OBJECT_PERMANENCE_OBJECT_TWO,
            tags.TYPES.OBJECT_PERMANENCE_NOVELTY_ONE,
            tags.TYPES.OBJECT_PERMANENCE_NOVELTY_TWO
        ])

        return scenes


class SpatioTemporalContinuityHypercube(IntuitivePhysicsHypercube):
    GOAL_TEMPLATE = {
        'category': tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS),
        'domainsInfo': {
            'objects': [
                tags.DOMAINS.OBJECTS_4
            ],
            'places': [],
            'agents': []
        },
        'sceneInfo': {}
    }

    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.PRIMARY] = (
        tags.tag_to_label(tags.SCENE.PASSIVE)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.SECONDARY] = (
        tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.TERTIARY] = (
        tags.tag_to_label(tags.SCENE.SPATIO_TEMPORAL_CONTINUITY)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.QUATERNARY] = (
        tags.tag_to_label(tags.SCENE.ACTION_NONE)
    )

    def __init__(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str],
        training=False,
        is_fall_down=False,
        is_move_across=False
    ):
        super().__init__(
            tags.ABBREV.SPATIO_TEMPORAL_CONTINUITY.upper(),
            body_template,
            SpatioTemporalContinuityHypercube.GOAL_TEMPLATE,
            role_to_type,
            # All spatio-temporal continuity scenes are move-across in Eval 3.
            is_fall_down=False,
            is_move_across=True,
            training=training
        )

    def _shroud_object(self, scene: Dict[str, Any], target_id: str) -> None:
        target = [
            instance for instance in scene['objects']
            if instance['id'] == target_id
        ][0]

        if self.is_move_across():
            # Implausible event happens after target moves behind occluder.
            # Shroud target until it moves behind second occluder.
            occluder_index_1 = target['speed']['occluderIndices'][0]
            occluder_index_2 = target['speed']['occluderIndices'][1]
            if occluder_index_1 < occluder_index_2:
                occluder_start_index = occluder_index_1
                occluder_end_index = occluder_index_2
            else:
                occluder_start_index = occluder_index_2
                occluder_end_index = occluder_index_1

            target['shrouds'] = [{
                'stepBegin': (
                    occluder_start_index + target['forces'][0]['stepBegin'] + 1
                ),
                'stepEnd': (
                    target['shows'][0]['stepBegin'] + occluder_end_index + 1
                )
            }]

        elif self.is_fall_down():
            # TODO If we ever need STC fall-down scenes in a future eval.
            raise exceptions.SceneException('STC fall-down hypercubes are not '
                                            'yet supported!')

        else:
            raise exceptions.SceneException('Unknown scene setup function!')

    # Override
    def _create_intuitive_physics_scenes(
        self,
        default_scene: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        target_id = self._target_list[0]['id']
        non_target_id = self._distractor_list[0]['id']

        # Variations on target.
        target_untrained_variation = self._variations_list[0].get(
            VARIATIONS.UNTRAINED_SHAPE
        )

        # Variations on non-target.
        non_target_untrained_variation = self._variations_list[1].get(
            VARIATIONS.UNTRAINED_SHAPE
        )

        for instance in self._variations_list[1].all():
            instance['role'] = tags.ROLES.NON_TARGET

        # Initialize scenes.
        scenes = {}
        for i in [
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p', 'q', 'r'
        ]:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scenes[j] = copy.deepcopy(default_scene)

        # Initialize spatio temporal continuity tags in scenes.
        for scene in scenes.values():
            scene['goal']['sceneInfo'][tags.SCENE.SLICES] = []
            scene['goal']['sceneInfo'][
                tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OBJECTS
            ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_OBJECTS.TWO
            scene['goal']['sceneInfo'][
                tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS
            ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS.THREE
            scene['goal']['sceneInfo'][
                tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_PLAUSIBLE
            ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_PLAUSIBLE.YES
            scene['goal']['sceneInfo'][
                tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_TARGET_TRAINED
            ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_TARGET_TRAINED.YES
            scene['goal']['sceneInfo'][
                tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_NON_TARGET_TRAINED
            ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_NON_TARGET_TRAINED.YES

        # Remove the non-target.
        for i in ['a', 'd', 'g', 'j', 'm', 'p', 'b', 'e', 'h', 'k', 'n', 'q']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OBJECTS
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_OBJECTS.ONE
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == non_target_id:
                        del scene['objects'][index]
                        break

        # Remove the target.
        for i in ['a', 'd', 'g', 'j', 'm', 'p']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OBJECTS
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_OBJECTS.ZERO
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id:
                        del scene['objects'][index]
                        break

        # Remove the one unpaired occluder.
        for i in ['g', 'h', 'i', 'j', 'k', 'l']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS.TWO
                remove_id_list = [
                    self._occluder_list[-2]['id'],
                    self._occluder_list[-1]['id']
                ]
                scene['objects'] = [
                    instance for instance in scene['objects']
                    if instance['id'] not in remove_id_list
                ]

        # Remove every occluder.
        for i in ['m', 'n', 'o', 'p', 'q', 'r']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS.ZERO
                remove_id_list = [
                    occluder['id'] for occluder in self._occluder_list
                ]
                scene['objects'] = [
                    instance for instance in scene['objects']
                    if instance['id'] not in remove_id_list
                ]

        for i in [
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
            'n', 'o', 'p', 'q', 'r'
        ]:
            # Switch the target with its untrained variation.
            for j in [i + '2', i + '4']:
                scene = scenes[j]
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_TARGET_TRAINED
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_TARGET_TRAINED.NO
                scene['evaluationOnly'] = True
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id:
                        scene['objects'][index] = (
                            copy.deepcopy(target_untrained_variation)
                        )
                        break

            # Switch the non-target with its untrained variation.
            for j in [i + '3', i + '4']:
                scene = scenes[j]
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_NON_TARGET_TRAINED
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_NON_TARGET_TRAINED.NO
                scene['evaluationOnly'] = True
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == non_target_id:
                        scene['objects'][index] = (
                            copy.deepcopy(non_target_untrained_variation)
                        )
                        break

        # Make target temporarily invisible (shrouded) as it moves between two
        # paired occluders (ignoring scenes in which the target was removed).
        for i in ['e', 'f', 'k', 'l', 'q', 'r']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['answer']['choice'] = IMPLAUSIBLE
                scene['goal']['sceneInfo'][
                    tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_PLAUSIBLE
                ] = tags.CELLS.SPATIO_TEMPORAL_CONTINUITY_PLAUSIBLE.NO
                self._shroud_object(scene, target_id)

        for i in ['d', 'j', 'p']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                scene = scenes[j]
                scene['evaluationOnly'] = True

        # Finalize scenes.
        self._update_hypercube_scene_info_tags(scenes, [
            tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OBJECTS,
            tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_OCCLUDERS,
            tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_PLAUSIBLE,
            tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_TARGET_TRAINED,
            tags.TYPES.SPATIO_TEMPORAL_CONTINUITY_NON_TARGET_TRAINED
        ])

        # Consolidate specific redundant scenes (STC only).
        for i in ['a', 'd', 'g', 'j', 'm', 'p']:
            for j in [i + '2', i + '3', i + '4']:
                scenes[i + '1']['goal']['sceneInfo'][tags.SCENE.ID].append(j)
                del scenes[j]
        for i in ['b', 'e', 'h', 'k', 'n', 'q']:
            scenes[i + '1']['goal']['sceneInfo'][tags.SCENE.ID].append(i + '3')
            del scenes[i + '3']
            scenes[i + '2']['goal']['sceneInfo'][tags.SCENE.ID].append(i + '4')
            del scenes[i + '4']

        return scenes

    # Override
    def _find_move_across_paired_list(self) -> List[TargetVariations]:
        # Generate two occluders paired with the target object.
        return [self._variations_list[0], self._variations_list[0]]

    # Override
    def _separate_targets_and_non_targets(
        self,
        moving_object_list: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return the target and non-target lists from the given moving object
        list."""
        # STC scenes will always have one target and one non-target in Eval 3.
        return moving_object_list[:1], moving_object_list[1:]


class ShapeConstancyHypercube(IntuitivePhysicsHypercube):
    GOAL_TEMPLATE = {
        'category': tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS),
        'domainsInfo': {
            'objects': [
                # Intentionally nothing
            ],
            'places': [],
            'agents': []
        },
        'sceneInfo': {}
    }

    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.PRIMARY] = (
        tags.tag_to_label(tags.SCENE.PASSIVE)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.SECONDARY] = (
        tags.tag_to_label(tags.SCENE.INTUITIVE_PHYSICS)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.TERTIARY] = (
        tags.tag_to_label(tags.SCENE.SHAPE_CONSTANCY)
    )
    GOAL_TEMPLATE['sceneInfo'][tags.SCENE.QUATERNARY] = (
        tags.tag_to_label(tags.SCENE.ACTION_NONE)
    )

    def __init__(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str],
        training=False,
        is_fall_down=False,
        is_move_across=False
    ):
        super().__init__(
            tags.ABBREV.SHAPE_CONSTANCY.upper(),
            body_template,
            ShapeConstancyHypercube.GOAL_TEMPLATE,
            role_to_type,
            # All shape constancy scenes are fall-down in Eval 3.
            is_fall_down=True,
            is_move_across=False,
            training=training
        )

    def _turn_a_into_b(
        self,
        scene: Dict[str, Any],
        target_id: str,
        template_b: Dict[str, Any]
    ) -> None:
        target_a = [
            instance for instance in scene['objects']
            if instance['id'] == target_id
        ][0]
        target_b = copy.deepcopy(template_b)

        if self.is_move_across():
            # Implausible event happens after target moves behind occluder.
            occluder_index = target_a['speed']['occluderIndices'][0]
            implausible_event_step = occluder_index + \
                target_a['forces'][0]['stepBegin']
            implausible_event_x = target_a['speed']['distanceByStep'][
                occluder_index
            ]
            # Give object B the movement of object A.
            target_b['forces'] = copy.deepcopy(target_a['forces'])
            target_b['speed'] = target_a['speed']

        elif self.is_fall_down():
            # Implausible event happens after target falls behind occluder.
            implausible_event_step = (
                OBJECT_FALL_TIME + target_a['shows'][0]['stepBegin']
            )
            implausible_event_x = target_a['shows'][0]['position']['x']
            # Set target's Y position stationary on the ground.
            y_position = retrieve_off_screen_position_y(
                target_b['shows'][0]['position']['z']
            )
            target_b['shows'][0]['position']['y'] -= y_position

        else:
            raise exceptions.SceneException('Unknown scene setup function!')

        # Hide object A at the implausible event step and show object B in
        # object A's old position behind the occluder.
        target_a['hides'] = [{
            'stepBegin': implausible_event_step
        }]
        target_b['shows'][0]['stepBegin'] = implausible_event_step
        target_b['shows'][0]['position']['x'] = implausible_event_x

        # Add object B to the scene.
        scene['objects'].append(target_b)

    # Override
    def _create_intuitive_physics_scenes(
        self,
        default_scene: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        target_id_1 = self._target_list[0]['id']
        target_id_2 = self._target_list[1]['id']

        # Variations on object one.
        variations_1 = self._variations_list[0]
        trained_variation_1_b = variations_1.get(VARIATIONS.DIFFERENT_SHAPE)
        untrained_variation_1_a = variations_1.get(VARIATIONS.UNTRAINED_SHAPE)
        untrained_variation_1_b = variations_1.get(
            VARIATIONS.UNTRAINED_DIFFERENT_SHAPE
        )

        # Variations on object two.
        variations_2 = self._variations_list[1]
        trained_variation_2_b = variations_2.get(VARIATIONS.DIFFERENT_SHAPE)
        untrained_variation_2_a = variations_2.get(VARIATIONS.UNTRAINED_SHAPE)
        untrained_variation_2_b = variations_2.get(
            VARIATIONS.UNTRAINED_DIFFERENT_SHAPE
        )

        # Initialize scenes.
        scenes = {}
        for i in ['a', 'b', 'e', 'f', 'i', 'j']:
            scenes[i + '1'] = copy.deepcopy(default_scene)
        for i in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l']:
            for j in [i + '2', i + '3', i + '4']:
                scenes[j] = copy.deepcopy(default_scene)

        # Initialize shape constancy tags in scenes.
        for scene in scenes.values():
            scene['goal']['sceneInfo'][tags.SCENE.SLICES] = []
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_OBJECT_ONE
            ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_ONE.NO_CHANGE
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_OBJECT_TWO
            ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_TWO.NO_CHANGE
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_TRAINED_ONE
            ] = tags.CELLS.SHAPE_CONSTANCY_TRAINED_ONE.YES
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_TRAINED_TWO
            ] = tags.CELLS.SHAPE_CONSTANCY_TRAINED_TWO.YES

        # Remove object two completely.
        for i in ['a', 'b', 'e', 'f', 'i', 'j']:
            scene = scenes[i + '1']
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_OBJECT_TWO
            ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_TWO.NONE
            for index in range(len(scene['objects'])):
                if scene['objects'][index]['id'] == target_id_2:
                    del scene['objects'][index]
                    break

        # Switch object one with its untrained variation.
        for i in ['b', 'd', 'f', 'h', 'j', 'l']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['sceneInfo'][
                    tags.TYPES.SHAPE_CONSTANCY_TRAINED_ONE
                ] = tags.CELLS.SHAPE_CONSTANCY_TRAINED_ONE.NO
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id_1:
                        scene['objects'][index] = (
                            copy.deepcopy(untrained_variation_1_a)
                        )
                        break

        # Switch object two with its untrained variation.
        for i in ['c', 'd', 'g', 'h', 'k', 'l']:
            for j in [i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['sceneInfo'][
                    tags.TYPES.SHAPE_CONSTANCY_TRAINED_TWO
                ] = tags.CELLS.SHAPE_CONSTANCY_TRAINED_TWO.NO
                for index in range(len(scene['objects'])):
                    if scene['objects'][index]['id'] == target_id_2:
                        scene['objects'][index] = (
                            copy.deepcopy(untrained_variation_2_a)
                        )
                        break

        # Object one transforms into a different trained shape.
        for i in ['e', 'f', 'g', 'h']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['answer']['choice'] = IMPLAUSIBLE
                scene['goal']['sceneInfo'][
                    tags.TYPES.SHAPE_CONSTANCY_OBJECT_ONE
                ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_ONE.TRAINED_SHAPE
                self._turn_a_into_b(scene, target_id_1, trained_variation_1_b)

        # Object one transforms into a different untrained shape.
        for i in ['i', 'j', 'k', 'l']:
            for j in [i + '1', i + '2', i + '3', i + '4']:
                if j not in scenes:
                    continue
                scene = scenes[j]
                scene['evaluationOnly'] = True
                scene['goal']['answer']['choice'] = IMPLAUSIBLE
                scene['goal']['sceneInfo'][
                    tags.TYPES.SHAPE_CONSTANCY_OBJECT_ONE
                ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_ONE.UNTRAINED_SHAPE
                self._turn_a_into_b(
                    scene,
                    target_id_1,
                    untrained_variation_1_b
                )

        for i in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l']:
            # Object two transforms into a different trained shape.
            scene = scenes[i + '3']
            scene['evaluationOnly'] = True
            scene['goal']['answer']['choice'] = IMPLAUSIBLE
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_OBJECT_TWO
            ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_TWO.TRAINED_SHAPE
            self._turn_a_into_b(scene, target_id_2, trained_variation_2_b)

            # Object two transforms into a different untrained shape.
            scene = scenes[i + '4']
            scene['evaluationOnly'] = True
            scene['goal']['answer']['choice'] = IMPLAUSIBLE
            scene['goal']['sceneInfo'][
                tags.TYPES.SHAPE_CONSTANCY_OBJECT_TWO
            ] = tags.CELLS.SHAPE_CONSTANCY_OBJECT_TWO.UNTRAINED_SHAPE
            self._turn_a_into_b(
                scene,
                target_id_2,
                untrained_variation_2_b
            )

        # Finalize scenes.
        self._update_hypercube_scene_info_tags(scenes, [
            tags.TYPES.SHAPE_CONSTANCY_OBJECT_ONE,
            tags.TYPES.SHAPE_CONSTANCY_OBJECT_TWO,
            tags.TYPES.SHAPE_CONSTANCY_TRAINED_ONE,
            tags.TYPES.SHAPE_CONSTANCY_TRAINED_TWO
        ])

        return scenes


class GravitySupportTrainingHypercubeFactory(hypercubes.HypercubeFactory):
    def __init__(self) -> None:
        super().__init__('GravitySupportTraining', training=True)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return GravitySupportHypercube(
            body_template,
            role_to_type,
            self.training
        )


class ObjectPermanenceTrainingHypercubeFactory(hypercubes.HypercubeFactory):
    def __init__(self) -> None:
        super().__init__('ObjectPermanenceTraining', training=True)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return ObjectPermanenceHypercube(
            body_template,
            role_to_type,
            self.training
        )


class ShapeConstancyTrainingHypercubeFactory(hypercubes.HypercubeFactory):
    def __init__(self) -> None:
        super().__init__('ShapeConstancyTraining', training=True)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return ShapeConstancyHypercube(
            body_template,
            role_to_type,
            self.training
        )


class SpatioTemporalContinuityTrainingHypercubeFactory(
    hypercubes.HypercubeFactory
):
    def __init__(self) -> None:
        super().__init__('SpatioTemporalContinuityTraining', training=True)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return SpatioTemporalContinuityHypercube(
            body_template,
            role_to_type,
            self.training
        )


class GravitySupportEvaluationHypercubeFactory(hypercubes.HypercubeFactory):
    def __init__(self) -> None:
        super().__init__('GravitySupportEvaluation', training=False)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return GravitySupportHypercube(
            body_template,
            role_to_type,
            self.training
        )


class ObjectPermanenceEvaluationHypercubeFactory(hypercubes.HypercubeFactory):
    def __init__(self) -> None:
        super().__init__('ObjectPermanenceEvaluation', training=False)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return ObjectPermanenceHypercube(
            body_template,
            role_to_type,
            self.training
        )


class ShapeConstancyEvaluationHypercubeFactory(hypercubes.HypercubeFactory):
    def __init__(self) -> None:
        super().__init__('ShapeConstancyEvaluation', training=False)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return ShapeConstancyHypercube(
            body_template,
            role_to_type,
            self.training
        )


class SpatioTemporalContinuityEvaluationHypercubeFactory(
    hypercubes.HypercubeFactory
):
    def __init__(self) -> None:
        super().__init__('SpatioTemporalContinuityEvaluation', training=False)

    def _build(
        self,
        body_template: Dict[str, Any],
        role_to_type: Dict[str, str]
    ) -> hypercubes.Hypercube:
        return SpatioTemporalContinuityHypercube(
            body_template,
            role_to_type,
            self.training
        )


INTUITIVE_PHYSICS_TRAINING_HYPERCUBE_LIST = [
    GravitySupportTrainingHypercubeFactory(),
    ObjectPermanenceTrainingHypercubeFactory(),
    ShapeConstancyTrainingHypercubeFactory(),
    SpatioTemporalContinuityTrainingHypercubeFactory()
]


INTUITIVE_PHYSICS_EVALUATION_HYPERCUBE_LIST = [
    GravitySupportEvaluationHypercubeFactory(),
    ObjectPermanenceEvaluationHypercubeFactory(),
    ShapeConstancyEvaluationHypercubeFactory(),
    SpatioTemporalContinuityEvaluationHypercubeFactory()
]
