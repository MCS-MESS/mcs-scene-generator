import copy

import pytest

from generator import base_objects, instances, mechanisms

BALL_DEFINITION = base_objects.create_soccer_ball()
# 0.42, 0.34, 0.13
DUCK_DEFINITION = base_objects.create_specific_definition_from_base(
    type='duck_on_wheels',
    color=['yellow'],
    materials=['UnityAssetStore/Wooden_Toys_Bundle/ToyBlocks/meshes/Materials/yellow_1x1'],  # noqa: E501
    salient_materials=None,
    scale=2
)
# Adjust the duck definition's Y rotation so it's facing left by default.
DUCK_DEFINITION.rotation.y = 180


def test_create_dropping_device():
    device = mechanisms.create_dropping_device(
        1,
        2,
        3,
        vars(BALL_DEFINITION.dimensions),
        100
    )

    assert device['id'].startswith('dropping_device_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 3
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'dropper', 'device', 'grey dropper', 'grey device'
    ]
    assert device['states'] == ([['held']] * 100)

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2.85, 'z': 2}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert device['shows'][0]['scale'] == {'x': 0.28, 'y': 0.3, 'z': 0.28}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == pytest.approx(
        {'x': 1.14, 'y': 0, 'z': 2.14}
    )
    assert vars(device_bounds.box_xz[1]) == pytest.approx(
        {'x': 1.14, 'y': 0, 'z': 1.86}
    )
    assert vars(device_bounds.box_xz[2]) == pytest.approx(
        {'x': 0.86, 'y': 0, 'z': 1.86}
    )
    assert vars(device_bounds.box_xz[3]) == pytest.approx(
        {'x': 0.86, 'y': 0, 'z': 2.14}
    )
    assert device_bounds.max_y == 3
    assert device_bounds.min_y == 0


def test_create_dropping_device_weird_shape():
    device = mechanisms.create_dropping_device(
        1,
        2,
        3,
        vars(DUCK_DEFINITION.dimensions),
        100
    )

    assert device['id'].startswith('dropping_device_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 17
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'dropper', 'device', 'grey dropper', 'grey device'
    ]
    assert device['states'] == ([['held']] * 100)

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2.765, 'z': 2}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert device['shows'][0]['scale'] == {'x': 0.53, 'y': 0.47, 'z': 0.53}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == pytest.approx(
        {'x': 1.265, 'y': 0, 'z': 2.265}
    )
    assert vars(device_bounds.box_xz[1]) == pytest.approx(
        {'x': 1.265, 'y': 0, 'z': 1.735}
    )
    assert vars(device_bounds.box_xz[2]) == pytest.approx(
        {'x': 0.735, 'y': 0, 'z': 1.735}
    )
    assert vars(device_bounds.box_xz[3]) == pytest.approx(
        {'x': 0.735, 'y': 0, 'z': 2.265}
    )
    assert device_bounds.max_y == 3
    assert device_bounds.min_y == 0


def test_create_dropping_device_with_step():
    device = mechanisms.create_dropping_device(
        1,
        2,
        3,
        vars(BALL_DEFINITION.dimensions),
        100,
        25,
        'custom_id'
    )

    assert device['id'].startswith('dropping_device_custom_id_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 3
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'dropper', 'device', 'grey dropper', 'grey device'
    ]
    assert device['states'] == (([['held']] * 24) + ([['released']] * 76))

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2.85, 'z': 2}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert device['shows'][0]['scale'] == {'x': 0.28, 'y': 0.3, 'z': 0.28}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == pytest.approx(
        {'x': 1.14, 'y': 0, 'z': 2.14}
    )
    assert vars(device_bounds.box_xz[1]) == pytest.approx(
        {'x': 1.14, 'y': 0, 'z': 1.86}
    )
    assert vars(device_bounds.box_xz[2]) == pytest.approx(
        {'x': 0.86, 'y': 0, 'z': 1.86}
    )
    assert vars(device_bounds.box_xz[3]) == pytest.approx(
        {'x': 0.86, 'y': 0, 'z': 2.14}
    )
    assert device_bounds.max_y == 3
    assert device_bounds.min_y == 0


def test_create_placer():
    placer = mechanisms.create_placer(
        {'x': 1, 'y': 3, 'z': -1},
        {'x': 0.5, 'y': 0.5, 'z': 0.5},
        {'x': 2, 'y': 2, 'z': 2},
        0,
        10,
        0,
        4
    )

    assert placer['id'].startswith('placer_')
    assert placer['kinematic'] is True
    assert placer['structure'] is True
    assert placer['type'] == 'cylinder'
    assert placer['mass'] == 10
    assert placer['materials'] == ['Custom/Materials/Magenta']
    assert placer['debug']['color'] == ['magenta', 'cyan']
    assert placer['debug']['info'] == [
        'magenta', 'cyan', 'placer', 'magenta placer', 'cyan placer'
    ]
    assert placer['debug']['shape'] == ['placer']

    assert len(placer['shows']) == 1
    assert placer['shows'][0]['stepBegin'] == 0
    assert placer['shows'][0]['position'] == {'x': 1, 'y': 6, 'z': -1}
    assert placer['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert placer['shows'][0]['scale'] == {'x': 0.2, 'y': 2, 'z': 0.2}
    placer_bounds = placer['shows'][0]['boundingBox']
    assert vars(placer_bounds.box_xz[0]) == {'x': 1.1, 'y': 0, 'z': -0.9}
    assert vars(placer_bounds.box_xz[1]) == {'x': 1.1, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[2]) == {'x': 0.9, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[3]) == {'x': 0.9, 'y': 0, 'z': -0.9}
    assert placer_bounds.max_y == 7
    assert placer_bounds.min_y == 0

    assert len(placer['moves']) == 2
    assert placer['moves'][0]['stepBegin'] == 10
    assert placer['moves'][0]['stepEnd'] == 21
    assert placer['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}
    assert placer['moves'][1]['stepBegin'] == 32
    assert placer['moves'][1]['stepEnd'] == 43
    assert placer['moves'][1]['vector'] == {'x': 0, 'y': 0.25, 'z': 0}

    assert placer['states'] == ([['active']] * 26) + [['inactive']]


def test_create_placer_with_position_y_offset():
    placer = mechanisms.create_placer(
        {'x': 1, 'y': 3.5, 'z': -1},
        {'x': 0.5, 'y': 0.5, 'z': 0.5},
        {'x': 2, 'y': 2, 'z': 2},
        0.5,
        10,
        0,
        4
    )

    assert placer['id'].startswith('placer_')
    assert placer['kinematic'] is True
    assert placer['structure'] is True
    assert placer['type'] == 'cylinder'
    assert placer['mass'] == 10
    assert placer['materials'] == ['Custom/Materials/Magenta']
    assert placer['debug']['color'] == ['magenta', 'cyan']
    assert placer['debug']['info'] == [
        'magenta', 'cyan', 'placer', 'magenta placer', 'cyan placer'
    ]
    assert placer['debug']['shape'] == ['placer']

    assert len(placer['shows']) == 1
    assert placer['shows'][0]['stepBegin'] == 0
    assert placer['shows'][0]['position'] == {'x': 1, 'y': 6, 'z': -1}
    assert placer['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert placer['shows'][0]['scale'] == {'x': 0.2, 'y': 2, 'z': 0.2}
    placer_bounds = placer['shows'][0]['boundingBox']
    assert vars(placer_bounds.box_xz[0]) == {'x': 1.1, 'y': 0, 'z': -0.9}
    assert vars(placer_bounds.box_xz[1]) == {'x': 1.1, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[2]) == {'x': 0.9, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[3]) == {'x': 0.9, 'y': 0, 'z': -0.9}
    assert placer_bounds.max_y == 7
    assert placer_bounds.min_y == 0

    assert len(placer['moves']) == 2
    assert placer['moves'][0]['stepBegin'] == 10
    assert placer['moves'][0]['stepEnd'] == 21
    assert placer['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}
    assert placer['moves'][1]['stepBegin'] == 32
    assert placer['moves'][1]['stepEnd'] == 43
    assert placer['moves'][1]['vector'] == {'x': 0, 'y': 0.25, 'z': 0}

    assert placer['states'] == ([['active']] * 26) + [['inactive']]


def test_create_placer_with_pole_offset():
    placer = mechanisms.create_placer(
        {'x': 1, 'y': 3, 'z': -1},
        {'x': 0.5, 'y': 0.5, 'z': 0.5},
        {'x': 2, 'y': 2, 'z': 2},
        0,
        10,
        0,
        4,
        placed_object_pole_offset_y=0.1
    )

    assert placer['id'].startswith('placer_')
    assert placer['kinematic'] is True
    assert placer['structure'] is True
    assert placer['type'] == 'cylinder'
    assert placer['mass'] == 10
    assert placer['materials'] == ['Custom/Materials/Magenta']
    assert placer['debug']['color'] == ['magenta', 'cyan']
    assert placer['debug']['info'] == [
        'magenta', 'cyan', 'placer', 'magenta placer', 'cyan placer'
    ]
    assert placer['debug']['shape'] == ['placer']

    assert len(placer['shows']) == 1
    assert placer['shows'][0]['stepBegin'] == 0
    assert placer['shows'][0]['position'] == {'x': 1, 'y': 5.95, 'z': -1}
    assert placer['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert placer['shows'][0]['scale'] == {'x': 0.2, 'y': 2, 'z': 0.2}
    placer_bounds = placer['shows'][0]['boundingBox']
    assert vars(placer_bounds.box_xz[0]) == {'x': 1.1, 'y': 0, 'z': -0.9}
    assert vars(placer_bounds.box_xz[1]) == {'x': 1.1, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[2]) == {'x': 0.9, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[3]) == {'x': 0.9, 'y': 0, 'z': -0.9}
    assert placer_bounds.max_y == 6.95
    assert placer_bounds.min_y == 0

    assert len(placer['moves']) == 2
    assert placer['moves'][0]['stepBegin'] == 10
    assert placer['moves'][0]['stepEnd'] == 21
    assert placer['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}
    assert placer['moves'][1]['stepBegin'] == 32
    assert placer['moves'][1]['stepEnd'] == 43
    assert placer['moves'][1]['vector'] == {'x': 0, 'y': 0.25, 'z': 0}

    assert placer['states'] == ([['active']] * 26) + [['inactive']]


def test_create_placer_with_last_step():
    placer = mechanisms.create_placer(
        {'x': 1, 'y': 3, 'z': -1},
        {'x': 0.5, 'y': 0.5, 'z': 0.5},
        {'x': 2, 'y': 2, 'z': 2},
        0,
        10,
        0,
        4,
        last_step=100
    )

    assert placer['id'].startswith('placer_')
    assert placer['kinematic'] is True
    assert placer['structure'] is True
    assert placer['type'] == 'cylinder'
    assert placer['mass'] == 10
    assert placer['materials'] == ['Custom/Materials/Magenta']
    assert placer['debug']['color'] == ['magenta', 'cyan']
    assert placer['debug']['info'] == [
        'magenta', 'cyan', 'placer', 'magenta placer', 'cyan placer'
    ]
    assert placer['debug']['shape'] == ['placer']

    assert len(placer['shows']) == 1
    assert placer['shows'][0]['stepBegin'] == 0
    assert placer['shows'][0]['position'] == {'x': 1, 'y': 6, 'z': -1}
    assert placer['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert placer['shows'][0]['scale'] == {'x': 0.2, 'y': 2, 'z': 0.2}
    placer_bounds = placer['shows'][0]['boundingBox']
    assert vars(placer_bounds.box_xz[0]) == {'x': 1.1, 'y': 0, 'z': -0.9}
    assert vars(placer_bounds.box_xz[1]) == {'x': 1.1, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[2]) == {'x': 0.9, 'y': 0, 'z': -1.1}
    assert vars(placer_bounds.box_xz[3]) == {'x': 0.9, 'y': 0, 'z': -0.9}
    assert placer_bounds.max_y == 7
    assert placer_bounds.min_y == 0

    assert len(placer['moves']) == 2
    assert placer['moves'][0]['stepBegin'] == 10
    assert placer['moves'][0]['stepEnd'] == 21
    assert placer['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}
    assert placer['moves'][1]['stepBegin'] == 32
    assert placer['moves'][1]['stepEnd'] == 43
    assert placer['moves'][1]['vector'] == {'x': 0, 'y': 0.25, 'z': 0}

    assert placer['states'] == ([['active']] * 26) + ([['inactive']] * 73)


def test_create_throwing_device():
    device = mechanisms.create_throwing_device(
        1,
        2,
        3,
        0,
        0,
        vars(BALL_DEFINITION.dimensions),
        100
    )

    assert device['id'].startswith('throwing_device_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 4
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'thrower', 'device', 'grey thrower', 'grey device'
    ]
    assert device['states'] == ([['held']] * 100)

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 90}
    assert device['shows'][0]['scale'] == {'x': 0.28, 'y': 0.4, 'z': 0.28}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == {'x': 1.2, 'y': 0, 'z': 3.14}
    assert vars(device_bounds.box_xz[1]) == {'x': 1.2, 'y': 0, 'z': 2.86}
    assert vars(device_bounds.box_xz[2]) == {'x': 0.8, 'y': 0, 'z': 2.86}
    assert vars(device_bounds.box_xz[3]) == {'x': 0.8, 'y': 0, 'z': 3.14}
    assert device_bounds.max_y == pytest.approx(2.14)
    assert device_bounds.min_y == pytest.approx(1.86)


def test_create_throwing_device_weird_shape():
    device = mechanisms.create_throwing_device(
        1,
        2,
        3,
        0,
        0,
        vars(DUCK_DEFINITION.dimensions),
        100
    )

    assert device['id'].startswith('throwing_device_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 22
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'thrower', 'device', 'grey thrower', 'grey device'
    ]
    assert device['states'] == ([['held']] * 100)

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 90}
    assert device['shows'][0]['scale'] == {'x': 0.53, 'y': 0.62, 'z': 0.53}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == pytest.approx(
        {'x': 1.31, 'y': 0, 'z': 3.265}
    )
    assert vars(device_bounds.box_xz[1]) == pytest.approx(
        {'x': 1.31, 'y': 0, 'z': 2.735}
    )
    assert vars(device_bounds.box_xz[2]) == pytest.approx(
        {'x': 0.69, 'y': 0, 'z': 2.735}
    )
    assert vars(device_bounds.box_xz[3]) == pytest.approx(
        {'x': 0.69, 'y': 0, 'z': 3.265}
    )
    assert device_bounds.max_y == pytest.approx(2.265)
    assert device_bounds.min_y == pytest.approx(1.735)


def test_create_throwing_device_with_step():
    device = mechanisms.create_throwing_device(
        1,
        2,
        3,
        0,
        0,
        vars(BALL_DEFINITION.dimensions),
        100,
        25,
        'custom_id'
    )

    assert device['id'].startswith('throwing_device_custom_id_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 4
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'thrower', 'device', 'grey thrower', 'grey device'
    ]
    assert device['states'] == (([['held']] * 24) + ([['released']] * 76))

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 90}
    assert device['shows'][0]['scale'] == {'x': 0.28, 'y': 0.4, 'z': 0.28}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == {'x': 1.2, 'y': 0, 'z': 3.14}
    assert vars(device_bounds.box_xz[1]) == {'x': 1.2, 'y': 0, 'z': 2.86}
    assert vars(device_bounds.box_xz[2]) == {'x': 0.8, 'y': 0, 'z': 2.86}
    assert vars(device_bounds.box_xz[3]) == {'x': 0.8, 'y': 0, 'z': 3.14}
    assert device_bounds.max_y == pytest.approx(2.14)
    assert device_bounds.min_y == pytest.approx(1.86)


def test_create_throwing_device_with_y_rotation():
    device = mechanisms.create_throwing_device(
        1,
        2,
        3,
        30,
        0,
        vars(BALL_DEFINITION.dimensions),
        100
    )

    assert device['id'].startswith('throwing_device_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 4
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'thrower', 'device', 'grey thrower', 'grey device'
    ]
    assert device['states'] == ([['held']] * 100)

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 30, 'z': 90}
    assert device['shows'][0]['scale'] == {'x': 0.28, 'y': 0.4, 'z': 0.28}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == pytest.approx(
        {'x': 1.243205, 'y': 0, 'z': 3.021244}
    )
    assert vars(device_bounds.box_xz[1]) == pytest.approx(
        {'x': 1.103205, 'y': 0, 'z': 2.778756}
    )
    assert vars(device_bounds.box_xz[2]) == pytest.approx(
        {'x': 0.756795, 'y': 0, 'z': 2.978756}
    )
    assert vars(device_bounds.box_xz[3]) == pytest.approx(
        {'x': 0.896795, 'y': 0, 'z': 3.221244}
    )
    assert device_bounds.max_y == pytest.approx(2.14)
    assert device_bounds.min_y == pytest.approx(1.86)


def test_create_throwing_device_with_z_rotation():
    device = mechanisms.create_throwing_device(
        1,
        2,
        3,
        0,
        30,
        vars(BALL_DEFINITION.dimensions),
        100
    )

    assert device['id'].startswith('throwing_device_')
    assert device['kinematic'] is True
    assert device['structure'] is True
    assert device['type'] == 'tube_wide'
    assert device['mass'] == 4
    assert device['materials'] == ['Custom/Materials/Grey']
    assert device['debug']['color'] == ['grey']
    assert device['debug']['info'] == [
        'grey', 'thrower', 'device', 'grey thrower', 'grey device'
    ]
    assert device['states'] == ([['held']] * 100)

    assert len(device['shows']) == 1
    assert device['shows'][0]['stepBegin'] == 0
    assert device['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert device['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 120}
    assert device['shows'][0]['scale'] == {'x': 0.28, 'y': 0.4, 'z': 0.28}
    device_bounds = device['shows'][0]['boundingBox']
    assert vars(device_bounds.box_xz[0]) == {'x': 1.2, 'y': 0, 'z': 3.14}
    assert vars(device_bounds.box_xz[1]) == {'x': 1.2, 'y': 0, 'z': 2.86}
    assert vars(device_bounds.box_xz[2]) == {'x': 0.8, 'y': 0, 'z': 2.86}
    assert vars(device_bounds.box_xz[3]) == {'x': 0.8, 'y': 0, 'z': 3.14}
    assert device_bounds.max_y == pytest.approx(2.14)
    assert device_bounds.min_y == pytest.approx(1.86)


def test_drop_object():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(BALL_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.drop_object(
        target,
        mock_device,
        25
    )
    assert target['type'] == BALL_DEFINITION.type
    assert target['togglePhysics'] == [{'stepBegin': 25}]
    assert target['kinematic'] is True

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 1.11, 'y': 0, 'z': 3.11}
    assert vars(target_bounds.box_xz[1]) == {'x': 1.11, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[2]) == {'x': 0.89, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[3]) == {'x': 0.89, 'y': 0, 'z': 3.11}
    assert target_bounds.max_y == 2.11
    assert target_bounds.min_y == 1.89


def test_drop_object_weird_shape():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(DUCK_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.drop_object(
        target,
        mock_device,
        25,
        rotation_y=DUCK_DEFINITION.rotation.y
    )
    assert target['type'] == DUCK_DEFINITION.type
    assert target['togglePhysics'] == [{'stepBegin': 25}]
    assert target['kinematic'] is True

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 180, 'z': 0}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 0.79, 'y': 0, 'z': 2.935}
    assert vars(target_bounds.box_xz[1]) == {'x': 0.79, 'y': 0, 'z': 3.065}
    assert vars(target_bounds.box_xz[2]) == {'x': 1.21, 'y': 0, 'z': 3.065}
    assert vars(target_bounds.box_xz[3]) == {'x': 1.21, 'y': 0, 'z': 2.935}
    assert target_bounds.max_y == 2.33
    assert target_bounds.min_y == 1.99


def test_place_object():
    mock_instance = {
        'shows': [{
            'position': {'x': 1, 'y': 3, 'z': -1},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5}
        }],
        'debug': {
            'dimensions': {'x': 2, 'y': 2, 'z': 2},
            'positionY': 0
        }
    }
    mechanisms.place_object(mock_instance, 10)
    assert mock_instance['kinematic']
    assert mock_instance['togglePhysics'] == [{'stepBegin': 27}]

    assert len(mock_instance['shows']) == 1
    assert mock_instance['shows'][0]['position'] == {'x': 1, 'y': 3, 'z': -1}
    assert mock_instance['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert mock_instance['shows'][0]['scale'] == {'x': 0.5, 'y': 0.5, 'z': 0.5}

    assert len(mock_instance['moves']) == 1
    assert mock_instance['moves'][0]['stepBegin'] == 10
    assert mock_instance['moves'][0]['stepEnd'] == 21
    assert mock_instance['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}


def test_place_object_with_position_y_offset():
    mock_instance = {
        'shows': [{
            'position': {'x': 1, 'y': 3.5, 'z': -1},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5}
        }],
        'debug': {
            'dimensions': {'x': 2, 'y': 2, 'z': 2},
            'positionY': 0.5
        }
    }
    mechanisms.place_object(mock_instance, 10)
    assert mock_instance['kinematic']
    assert mock_instance['togglePhysics'] == [{'stepBegin': 27}]

    assert len(mock_instance['shows']) == 1
    assert (
        mock_instance['shows'][0]['position'] == {'x': 1, 'y': 3.5, 'z': -1}
    )
    assert mock_instance['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert mock_instance['shows'][0]['scale'] == {'x': 0.5, 'y': 0.5, 'z': 0.5}

    assert len(mock_instance['moves']) == 1
    assert mock_instance['moves'][0]['stepBegin'] == 10
    assert mock_instance['moves'][0]['stepEnd'] == 21
    assert mock_instance['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}


def test_place_object_with_end_height():
    mock_instance = {
        'shows': [{
            'position': {'x': 1, 'y': 3, 'z': -1},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5}
        }],
        'debug': {
            'dimensions': {'x': 2, 'y': 2, 'z': 2},
            'positionY': 0
        }
    }
    mechanisms.place_object(mock_instance, 10, end_height=1)
    assert mock_instance['kinematic']
    assert mock_instance['togglePhysics'] == [{'stepBegin': 23}]

    assert len(mock_instance['shows']) == 1
    assert mock_instance['shows'][0]['position'] == {'x': 1, 'y': 3, 'z': -1}
    assert mock_instance['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert mock_instance['shows'][0]['scale'] == {'x': 0.5, 'y': 0.5, 'z': 0.5}

    assert len(mock_instance['moves']) == 1
    assert mock_instance['moves'][0]['stepBegin'] == 10
    assert mock_instance['moves'][0]['stepEnd'] == 17
    assert mock_instance['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}


def test_place_object_with_end_height_position_y_offset():
    mock_instance = {
        'shows': [{
            'position': {'x': 1, 'y': 3.5, 'z': -1},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5}
        }],
        'debug': {
            'dimensions': {'x': 2, 'y': 2, 'z': 2},
            'positionY': 0.5
        }
    }
    mechanisms.place_object(mock_instance, 10, end_height=1)
    assert mock_instance['kinematic']
    assert mock_instance['togglePhysics'] == [{'stepBegin': 23}]

    assert len(mock_instance['shows']) == 1
    assert (
        mock_instance['shows'][0]['position'] == {'x': 1, 'y': 3.5, 'z': -1}
    )
    assert mock_instance['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert mock_instance['shows'][0]['scale'] == {'x': 0.5, 'y': 0.5, 'z': 0.5}

    assert len(mock_instance['moves']) == 1
    assert mock_instance['moves'][0]['stepBegin'] == 10
    assert mock_instance['moves'][0]['stepEnd'] == 17
    assert mock_instance['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}


def test_place_object_with_start_height():
    mock_instance = {
        'shows': [{
            'position': {'x': 1, 'y': 0, 'z': -1},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5}
        }],
        'debug': {
            'dimensions': {'x': 2, 'y': 2, 'z': 2},
            'positionY': 0
        }
    }
    mechanisms.place_object(mock_instance, 10, start_height=5)
    assert mock_instance['kinematic']
    assert mock_instance['togglePhysics'] == [{'stepBegin': 26}]

    assert len(mock_instance['shows']) == 1
    assert mock_instance['shows'][0]['position'] == (
        {'x': 1, 'y': 2.995, 'z': -1}
    )
    assert mock_instance['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert mock_instance['shows'][0]['scale'] == {'x': 0.5, 'y': 0.5, 'z': 0.5}

    assert len(mock_instance['moves']) == 1
    assert mock_instance['moves'][0]['stepBegin'] == 10
    assert mock_instance['moves'][0]['stepEnd'] == 20
    assert mock_instance['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}


def test_place_object_with_start_height_position_y_offset():
    mock_instance = {
        'shows': [{
            'position': {'x': 1, 'y': 0, 'z': -1},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5}
        }],
        'debug': {
            'dimensions': {'x': 2, 'y': 2, 'z': 2},
            'positionY': 0.5
        }
    }
    mechanisms.place_object(mock_instance, 10, start_height=5)
    assert mock_instance['kinematic']
    assert mock_instance['togglePhysics'] == [{'stepBegin': 26}]

    assert len(mock_instance['shows']) == 1
    assert mock_instance['shows'][0]['position'] == (
        {'x': 1, 'y': 3.495, 'z': -1}
    )
    assert mock_instance['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    assert mock_instance['shows'][0]['scale'] == {'x': 0.5, 'y': 0.5, 'z': 0.5}

    assert len(mock_instance['moves']) == 1
    assert mock_instance['moves'][0]['stepBegin'] == 10
    assert mock_instance['moves'][0]['stepEnd'] == 20
    assert mock_instance['moves'][0]['vector'] == {'x': 0, 'y': -0.25, 'z': 0}


def test_throw_object():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3},
            'rotation': {'x': 0, 'y': 0, 'z': 90},
            'scale': {'x': 0.28, 'y': 0.4, 'z': 0.28}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(BALL_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.throw_object(
        target,
        mock_device,
        345,
        25
    )
    assert target['type'] == BALL_DEFINITION.type
    assert target['forces'] == [{
        'relative': True,
        'stepBegin': 25,
        'stepEnd': 25,
        'vector': {'x': 345, 'y': 0, 'z': 0}
    }]

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 1.11, 'y': 0, 'z': 3.11}
    assert vars(target_bounds.box_xz[1]) == {'x': 1.11, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[2]) == {'x': 0.89, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[3]) == {'x': 0.89, 'y': 0, 'z': 3.11}
    assert target_bounds.max_y == 2.11
    assert target_bounds.min_y == 1.89


def test_throw_object_downward():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3},
            'rotation': {'x': 0, 'y': 0, 'z': 90},
            'scale': {'x': 0.28, 'y': 0.4, 'z': 0.28}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(BALL_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.throw_object(
        target,
        mock_device,
        345,
        25,
        rotation_z=-5
    )
    assert target['type'] == BALL_DEFINITION.type
    assert target['forces'] == [{
        'relative': True,
        'stepBegin': 25,
        'stepEnd': 25,
        'vector': {'x': 345, 'y': 0, 'z': 0}
    }]

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': -5}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 1.11, 'y': 0, 'z': 3.11}
    assert vars(target_bounds.box_xz[1]) == {'x': 1.11, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[2]) == {'x': 0.89, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[3]) == {'x': 0.89, 'y': 0, 'z': 3.11}
    assert target_bounds.max_y == 2.11
    assert target_bounds.min_y == 1.89


def test_throw_object_downward_from_device_with_upward_z_rotation():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3},
            'rotation': {'x': 0, 'y': 0, 'z': 60},
            'scale': {'x': 0.28, 'y': 0.4, 'z': 0.28}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(BALL_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.throw_object(
        target,
        mock_device,
        345,
        25,
        rotation_z=-5
    )
    assert target['type'] == BALL_DEFINITION.type
    assert target['forces'] == [{
        'relative': True,
        'stepBegin': 25,
        'stepEnd': 25,
        'vector': {'x': 345, 'y': 0, 'z': 0}
    }]

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': -5}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 1.11, 'y': 0, 'z': 3.11}
    assert vars(target_bounds.box_xz[1]) == {'x': 1.11, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[2]) == {'x': 0.89, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[3]) == {'x': 0.89, 'y': 0, 'z': 3.11}
    assert target_bounds.max_y == 2.11
    assert target_bounds.min_y == 1.89


def test_throw_object_weird_shape():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3},
            'rotation': {'x': 0, 'y': 0, 'z': 90},
            'scale': {'x': 0.53, 'y': 0.62, 'z': 0.53}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(DUCK_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.throw_object(
        target,
        mock_device,
        345,
        25,
        rotation_y=DUCK_DEFINITION.rotation.y
    )
    assert target['type'] == DUCK_DEFINITION.type
    assert target['forces'] == [{
        'relative': True,
        'stepBegin': 25,
        'stepEnd': 25,
        'vector': {'x': 345, 'y': 0, 'z': 0}
    }]

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 180, 'z': 0}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 0.79, 'y': 0, 'z': 2.935}
    assert vars(target_bounds.box_xz[1]) == {'x': 0.79, 'y': 0, 'z': 3.065}
    assert vars(target_bounds.box_xz[2]) == {'x': 1.21, 'y': 0, 'z': 3.065}
    assert vars(target_bounds.box_xz[3]) == {'x': 1.21, 'y': 0, 'z': 2.935}
    assert target_bounds.max_y == 2.33
    assert target_bounds.min_y == 1.99


def test_throw_object_with_y_rotation():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3},
            'rotation': {'x': 0, 'y': 90, 'z': 90},
            'scale': {'x': 0.28, 'y': 0.4, 'z': 0.28}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(BALL_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.throw_object(
        target,
        mock_device,
        345,
        25
    )
    assert target['type'] == BALL_DEFINITION.type
    assert target['forces'] == [{
        'relative': True,
        'stepBegin': 25,
        'stepEnd': 25,
        'vector': {'x': 345, 'y': 0, 'z': 0}
    }]

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 90, 'z': 0}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 1.11, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[1]) == {'x': 0.89, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[2]) == {'x': 0.89, 'y': 0, 'z': 3.11}
    assert vars(target_bounds.box_xz[3]) == {'x': 1.11, 'y': 0, 'z': 3.11}
    assert target_bounds.max_y == 2.11
    assert target_bounds.min_y == 1.89


def test_throw_object_from_device_with_upward_z_rotation():
    mock_device = {
        'shows': [{
            'position': {'x': 1, 'y': 2, 'z': 3},
            'rotation': {'x': 0, 'y': 0, 'z': 60},
            'scale': {'x': 0.28, 'y': 0.4, 'z': 0.28}
        }]
    }
    target = instances.instantiate_object(
        copy.deepcopy(BALL_DEFINITION),
        {'position': {'x': 0, 'y': 0, 'z': 0}}
    )
    target = mechanisms.throw_object(
        target,
        mock_device,
        345,
        25
    )
    assert target['type'] == BALL_DEFINITION.type
    assert target['forces'] == [{
        'relative': True,
        'stepBegin': 25,
        'stepEnd': 25,
        'vector': {'x': 345, 'y': 0, 'z': 0}
    }]

    assert len(target['shows']) == 1
    assert target['shows'][0]['position'] == {'x': 1, 'y': 2, 'z': 3}
    assert target['shows'][0]['rotation'] == {'x': 0, 'y': 0, 'z': 0}
    target_bounds = target['shows'][0]['boundingBox']
    assert vars(target_bounds.box_xz[0]) == {'x': 1.11, 'y': 0, 'z': 3.11}
    assert vars(target_bounds.box_xz[1]) == {'x': 1.11, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[2]) == {'x': 0.89, 'y': 0, 'z': 2.89}
    assert vars(target_bounds.box_xz[3]) == {'x': 0.89, 'y': 0, 'z': 3.11}
    assert target_bounds.max_y == 2.11
    assert target_bounds.min_y == 1.89