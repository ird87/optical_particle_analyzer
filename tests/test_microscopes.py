import json
import pytest
from backend.microscopes import MicroscopeRegistry


def test_save_reload_and_rebind(tmp_path):
    registry = MicroscopeRegistry(tmp_path)
    identifier = registry.save({'name': ' USB 1 ', 'type': 'MANUAL', 'camera_index': 0})
    reloaded = MicroscopeRegistry(tmp_path)
    assert reloaded.get('USB 1')['id'] == identifier
    reloaded.bind('USB 1', 2)
    assert registry.get('USB 1')['camera_index'] == 2
    registry.bind('М001', 1)
    assert reloaded.get('М001')['camera_index'] == 1
    assert reloaded.get('По умолчанию')['camera_index'] is None
    registry.delete(identifier)
    assert all(m['name'] != 'USB 1' for m in reloaded.list())


def test_reads_existing_custom_format(tmp_path):
    entry = {'id': 3, 'name': 'Old', 'type': 'AUTOMATIC', 'type_localized': 'Автоматический', 'camera_index': 1}
    (tmp_path / 'microscopes.json').write_text(json.dumps([entry]))
    assert MicroscopeRegistry(tmp_path).get('Old')['camera_index'] == 1


@pytest.mark.parametrize('name', ['', ' ', 'М001', 'по УМОЛЧАНИЮ'])
def test_rejects_empty_or_reserved_names(tmp_path, name):
    with pytest.raises(ValueError):
        MicroscopeRegistry(tmp_path).save({'name': name, 'type': 'MANUAL', 'camera_index': 0})


def test_rejects_duplicate_name_case_insensitive(tmp_path):
    registry = MicroscopeRegistry(tmp_path)
    registry.save({'name': 'USB', 'type': 'MANUAL', 'camera_index': 0})
    with pytest.raises(ValueError):
        registry.save({'name': 'usb', 'type': 'MANUAL', 'camera_index': 1})


@pytest.mark.parametrize('index', [-1, .5, True, '0', None])
def test_rejects_invalid_camera_index(tmp_path, index):
    with pytest.raises(ValueError):
        MicroscopeRegistry(tmp_path).save({'name': 'USB', 'type': 'MANUAL', 'camera_index': index})


def test_corrupt_file_not_overwritten(tmp_path):
    path = tmp_path / 'microscopes.json'
    path.write_text('{broken')
    with pytest.raises(ValueError):
        MicroscopeRegistry(tmp_path).save({'name': 'USB', 'type': 'MANUAL', 'camera_index': 0})
    assert path.read_text() == '{broken'


def test_default_and_unknown_type_cannot_connect(tmp_path):
    registry = MicroscopeRegistry(tmp_path)
    with pytest.raises(ValueError):
        registry.bind('По умолчанию', 0)
    with pytest.raises(ValueError):
        registry.save({'name': 'USB', 'type': 'UNKNOWN', 'camera_index': 0})
