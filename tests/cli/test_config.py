import io
from textwrap import dedent

import pytest

from vdirsyncer import cli, exceptions
from vdirsyncer.cli.config import Config, _parse_config_value

import vdirsyncer.cli.utils  # noqa


invalid = object()


@pytest.fixture
def read_config(tmpdir, monkeypatch):
    def inner(cfg):
        errors = []
        monkeypatch.setattr('vdirsyncer.cli.cli_logger.error', errors.append)
        f = io.StringIO(dedent(cfg.format(base=str(tmpdir))))
        rv = Config.from_fileobject(f)
        monkeypatch.undo()
        return errors, rv
    return inner


@pytest.fixture
def parse_config_value(capsys):
    def inner(s):
        try:
            rv = _parse_config_value(s)
        except ValueError:
            return invalid
        else:
            warnings = capsys.readouterr()[1]
            return rv, len(warnings.splitlines())
    return inner


def test_read_config(read_config):
    errors, c = read_config(u'''
        [general]
        status_path = /tmp/status/

        [pair bob]
        a = "bob_a"
        b = "bob_b"
        collections = null

        [storage bob_a]
        type = "filesystem"
        path = "/tmp/contacts/"
        fileext = ".vcf"
        yesno = false
        number = 42

        [storage bob_b]
        type = "carddav"
        ''')

    assert c.general == {'status_path': '/tmp/status/'}

    assert set(c.pairs) == {'bob'}
    bob = c.pairs['bob']
    assert bob.collections is None

    assert c.storages == {
        'bob_a': {'type': 'filesystem', 'path': '/tmp/contacts/', 'fileext':
                  '.vcf', 'yesno': False, 'number': 42,
                  'instance_name': 'bob_a'},
        'bob_b': {'type': 'carddav', 'instance_name': 'bob_b'}
    }


def test_missing_collections_param(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [general]
            status_path = /tmp/status/

            [pair bob]
            a = "bob_a"
            b = "bob_b"

            [storage bob_a]
            type = "lmao"

            [storage bob_b]
            type = "lmao"
            ''')

    assert 'collections parameter missing' in str(excinfo.value)


def test_invalid_section_type(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [general]
            status_path = /tmp/status/

            [bogus]
        ''')

    assert 'Unknown section' in str(excinfo.value)
    assert 'bogus' in str(excinfo.value)


def test_storage_instance_from_config(monkeypatch):
    def lol(**kw):
        assert kw == {'foo': 'bar', 'baz': 1}
        return 'OK'

    monkeypatch.setitem(cli.utils.storage_names._storages,
                        'lol', lol)
    config = {'type': 'lol', 'foo': 'bar', 'baz': 1}
    assert cli.utils.storage_instance_from_config(config) == 'OK'


def test_missing_general_section(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [pair my_pair]
            a = "my_a"
            b = "my_b"
            collections = null

            [storage my_a]
            type = "filesystem"
            path = "{base}/path_a/"
            fileext = ".txt"

            [storage my_b]
            type = "filesystem"
            path = "{base}/path_b/"
            fileext = ".txt"
            ''')

    assert 'Invalid general section.' in str(excinfo.value)


def test_wrong_general_section(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [general]
            wrong = true
            ''')

    assert 'Invalid general section.' in str(excinfo.value)
    assert excinfo.value.problems == [
        'general section doesn\'t take the parameters: wrong',
        'general section is missing the parameters: status_path'
    ]


def test_invalid_storage_name(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
        [general]
        status_path = {base}/status/

        [storage foo.bar]
        ''')

    assert 'invalid characters' in str(excinfo.value).lower()


def test_invalid_collections_arg(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
        [general]
        status_path = /tmp/status/

        [pair foobar]
        a = "foo"
        b = "bar"
        collections = [null]

        [storage foo]
        type = "filesystem"
        path = "/tmp/foo/"
        fileext = ".txt"

        [storage bar]
        type = "filesystem"
        path = "/tmp/bar/"
        fileext = ".txt"
        ''')

    assert 'Expected string' in str(excinfo.value)


def test_duplicate_sections(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
        [general]
        status_path = /tmp/status/

        [pair foobar]
        a = "foobar"
        b = "bar"
        collections = null

        [storage foobar]
        type = "filesystem"
        path = "/tmp/foo/"
        fileext = ".txt"

        [storage bar]
        type = "filesystem"
        path = "/tmp/bar/"
        fileext = ".txt"
        ''')

    assert 'Name "foobar" already used' in str(excinfo.value)


def test_parse_config_value(parse_config_value):
    x = parse_config_value

    assert x('123  # comment!') is invalid

    assert x('True') is invalid
    assert x('False') is invalid
    assert x('Yes') is invalid
    assert x('None') is invalid
    assert x('"True"') == ('True', 0)
    assert x('"False"') == ('False', 0)

    assert x('"123  # comment!"') == ('123  # comment!', 0)
    assert x('true') == (True, 0)
    assert x('false') == (False, 0)
    assert x('null') == (None, 0)
    assert x('3.14') == (3.14, 0)
    assert x('') == ('', 1)
    assert x('""') == ('', 0)


def test_validate_collections_param():
    x = cli.config._validate_collections_param
    x(None)
    x(["c", "a", "b"])
    pytest.raises(ValueError, x, [None])
    pytest.raises(ValueError, x, ["a", "a", "a"])
    pytest.raises(ValueError, x, [[None, "a", "b"]])
    x([["c", None, "b"]])
    x([["c", "a", None]])
    x([["c", None, None]])
