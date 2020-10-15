#                                                         -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
"""Tests for tox_lsr hooks."""

import os
import shutil
import tempfile

try:
    from unittest import mock as unittest_mock
    from unittest.mock import MagicMock, Mock, patch
except ImportError:
    import mock as unittest_mock
    from mock import MagicMock, Mock, patch

from copy import deepcopy

import pkg_resources

# I have no idea why pylint complains about this.  This works:
# command = python -c 'import py; print(dir(py.iniconfig))'
# bug in pylint?  anyway, just ignore it
# in addition - pylint does not allow me to disable it
# on the same line, so I have to disable it before the line
# pylint: disable=no-member,no-name-in-module,import-error
import py.iniconfig
import unittest2

from tox_lsr.hooks import (
    CONFIG_FILES_SUBDIR,
    LSR_CONFIG_SECTION,
    LSR_ENABLE,
    LSR_ENABLE_ENV,
    SCRIPT_NAME,
    TOX_DEFAULT_INI,
    _LSRPath,
    is_lsr_enabled,
    merge_config,
    merge_envconf,
    merge_ini,
    merge_prop_values,
    prop_is_set,
    set_prop_values_ini,
    tox_addoption,
    tox_configure,
)

from .utils import MockConfig

# code uses some protected members such as _cfg, _parser, _reader
# pylint: disable=protected-access


class HooksTestCase(unittest2.TestCase):
    def setUp(self):
        self.toxworkdir = tempfile.mkdtemp()
        patch(
            "pkg_resources.resource_filename",
            return_value=self.toxworkdir + "/" + SCRIPT_NAME,
        ).start()
        self.default_tox_ini_b = pkg_resources.resource_string(
            "tox_lsr", CONFIG_FILES_SUBDIR + "/" + TOX_DEFAULT_INI
        )
        self.default_tox_ini_raw = self.default_tox_ini_b.decode()
        # e.g. __file__ is tests/unit/something.py -
        # fixture_path is tests/fixtures
        self.tests_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        self.fixture_path = os.path.join(
            self.tests_path, "fixtures", self.id().split(".")[-1]
        )

    def tearDown(self):
        shutil.rmtree(self.toxworkdir)
        patch.stopall()

    def test_tox_addoption(self):
        """Test tox_addoption."""

        parser = Mock(add_argument=Mock())
        tox_addoption(parser)
        self.assertEqual(1, parser.add_argument.call_count)

    def test_tox_configure(self):
        """Test tox_configure."""

        config = MockConfig(toxworkdir=self.toxworkdir)
        with patch(
            "tox_lsr.hooks.is_lsr_enabled", return_value=False
        ) as mock_ile:
            tox_configure(config)
            self.assertEqual(1, mock_ile.call_count)

        setattr(config.option, LSR_ENABLE, True)
        default_config = MockConfig(toxworkdir=self.toxworkdir)

        with patch(
            "pkg_resources.resource_string",
            return_value=self.default_tox_ini_b,
        ) as mock_rs:
            with patch("tox_lsr.hooks.merge_config") as mock_mc:
                with patch(
                    "tox_lsr.hooks.merge_ini",
                    return_value=self.default_tox_ini_raw,
                ) as mock_mi:
                    with patch(
                        "tox_lsr.hooks.Config",
                        side_effect=[TypeError(), default_config],
                    ) as mock_cfg:
                        with patch(
                            "tox_lsr.hooks.ParseIni",
                            side_effect=[TypeError(), None],
                        ) as mock_pi:
                            tox_configure(config)
                            self.assertEqual(1, mock_rs.call_count)
                            self.assertEqual(2, mock_pi.call_count)
                            self.assertEqual(1, mock_mc.call_count)
                            self.assertEqual(1, mock_mi.call_count)
                            self.assertEqual(2, mock_cfg.call_count)

    def test_tox_merge_ini(self):
        """Test that given config is merged with default config ini."""

        config = MockConfig(toxworkdir=self.toxworkdir)
        tox_ini_file = os.path.join(self.fixture_path, "tox.ini")
        config._cfg = py.iniconfig.IniConfig(tox_ini_file)
        result = merge_ini(config, self.default_tox_ini_raw)
        # check the result
        expected_file = os.path.join(self.fixture_path, "result.ini")
        expected_ini = py.iniconfig.IniConfig(expected_file)
        result_ini = py.iniconfig.IniConfig("", result)

        self.assertDictEqual(expected_ini.sections, result_ini.sections)

    def test_tox_prop_is_set(self):
        """Test prop_is_set."""

        tec = Mock(envname="prop")
        tec._reader = Mock()
        tec._reader._cfg = Mock()
        cfgdict = {
            "empty_str_prop": "",
            "str_prop": "str_prop",
            "int_prop": 0,
            "bool_prop": False,
            "float_prop": 0.0,
            "list_prop": [1, 2, 3],
            "empty_list_prop": [],
            "dict_prop": {"a": "a"},
            "empty_dict_prop": {},
            "obj_prop": object(),
            "none_prop": None,
        }
        tec._reader._cfg.sections = deepcopy({"testenv": cfgdict})
        for prop in cfgdict:
            self.assertTrue(prop_is_set(tec, prop))
        tec._reader._cfg.sections["testenv:prop"] = deepcopy(cfgdict)
        for prop in cfgdict:
            self.assertTrue(prop_is_set(tec, prop))
        del tec._reader._cfg.sections["testenv"]
        del tec._reader._cfg.sections["testenv:prop"]
        tec.configure_mock(**deepcopy(cfgdict))
        for prop in cfgdict:
            self.assertFalse(prop_is_set(tec, prop))

    def test_tox_merge_prop_values(self):
        """Test merge_prop_values."""

        # assert that code ignores properties it does not handle
        tec = MagicMock()
        def_tec = MagicMock()
        merge_prop_values("nosuchprop", tec, def_tec)
        self.assertFalse(tec.mock_calls)
        self.assertFalse(def_tec.mock_calls)
        # test empty tec
        tec = MagicMock()
        def_tec = MagicMock()
        propnames = ["setenv", "deps", "passenv", "whitelist_externals"]
        empty_attrs = {
            "setenv": {},
            "deps": [],
            "passenv": set(),
            "whitelist_externals": [],
        }
        tec.configure_mock(**deepcopy(empty_attrs))
        full_attrs = {
            "setenv": {"a": "a", "b": "b"},
            "deps": ["a", "b"],
            "passenv": set(["a", "b"]),
            "whitelist_externals": ["a", "b"],
        }
        def_tec.configure_mock(**deepcopy(full_attrs))
        for prop in propnames:
            merge_prop_values(prop, tec, def_tec)
        for prop in propnames:
            val = getattr(tec, prop)
            exp_val = full_attrs[prop]
            if isinstance(val, list):
                self.assertEqual(set(exp_val), set(val))
            else:
                self.assertEqual(exp_val, val)
        # test empty def_tec
        tec = MagicMock()
        def_tec = MagicMock()
        tec.configure_mock(**deepcopy(full_attrs))
        def_tec.configure_mock(**deepcopy(empty_attrs))
        for prop in propnames:
            merge_prop_values(prop, tec, def_tec)
        for prop in propnames:
            val = getattr(tec, prop)
            exp_val = full_attrs[prop]
            if isinstance(val, list):
                self.assertEqual(set(exp_val), set(val))
            else:
                self.assertEqual(exp_val, val)
        # test merging
        more_attrs = {
            "setenv": {"a": "a", "c": "c"},
            "deps": ["a", "c"],
            "passenv": set(["a", "c"]),
            "whitelist_externals": ["a", "c"],
        }
        result_attrs = {
            "setenv": {"a": "a", "b": "b", "c": "c"},
            "deps": ["a", "b", "c"],
            "passenv": set(["a", "b", "c"]),
            "whitelist_externals": ["a", "b", "c"],
        }
        tec = MagicMock()
        def_tec = MagicMock()
        tec.configure_mock(**deepcopy(full_attrs))
        def_tec.configure_mock(**deepcopy(more_attrs))
        for prop in propnames:
            merge_prop_values(prop, tec, def_tec)
        for prop in propnames:
            val = getattr(tec, prop)
            exp_val = result_attrs[prop]
            if isinstance(val, list):
                self.assertEqual(set(exp_val), set(val))
            else:
                self.assertEqual(exp_val, val)

    def test_tox_merge_envconf(self):
        """Test the merge_envconf method."""

        # test exception handling
        prop = "unsettable"

        def mock_unsettable_is_set(envconf, propname):
            if propname != prop:
                return False
            if envconf == def_tec:
                return True
            return False

        def_tec = Mock(unsettable="unsettable")
        tec = Mock()
        with patch(
            "tox_lsr.hooks.prop_is_set", side_effect=mock_unsettable_is_set
        ):
            with patch("tox_lsr.hooks.setattr", side_effect=AttributeError()):
                merge_envconf(tec, def_tec)
                self.assertNotEqual(tec.unsettable, "unsettable")

        # test setting an unset property
        prop = "propa"

        def mock_prop_is_set(envconf, propname):
            if propname != prop:
                return False
            if envconf == def_tec:
                return True
            return False

        unittest_mock.FILTER_DIR = (
            False  # for handling attributes that start with underscore
        )
        def_tec = Mock(spec=[prop], propa=prop, _ignoreme="ignoreme")
        tec = Mock(spec=[prop])
        with patch("tox_lsr.hooks.prop_is_set", side_effect=mock_prop_is_set):
            merge_envconf(tec, def_tec)
        unittest_mock.FILTER_DIR = True  # reset to default
        self.assertEqual(prop, tec.propa)
        # test that it tries to merge if both props are set

        # pylint: disable=unused-argument
        def mock_prop_is_set2(envconf, propname):
            if propname != prop:
                return False
            return True

        def_tec = Mock(spec=[prop], propa=prop)
        tec = Mock(spec=[prop], propa="someothervalue")
        with patch("tox_lsr.hooks.prop_is_set", side_effect=mock_prop_is_set2):
            with patch("tox_lsr.hooks.merge_prop_values") as mock_mpv:
                merge_envconf(tec, def_tec)
                self.assertEqual(1, mock_mpv.call_count)
        self.assertEqual("someothervalue", tec.propa)

    def test_tox_merge_config(self):
        """Test the merge_config method."""

        tox_attrs = {
            "a": "a",
            "b": "b",
        }
        tec = Mock()
        tec._cfg = Mock()
        tec._cfg.sections = deepcopy({"tox": tox_attrs})
        tec.configure_mock(**deepcopy(tox_attrs))
        tec.envlist_explicit = False
        tec.envlist = ["a", "b"]
        tec.envlist_default = ["a", "b"]
        enva = {}
        envb = {}
        tec.envconfigs = {"a": enva, "b": envb}
        def_tox_attrs = {"a": "b", "b": "c", "c": "d", "_skip": "skip"}
        unittest_mock.FILTER_DIR = (
            False  # for handling attributes that start with underscore
        )
        def_tec = Mock()
        def_tec._cfg = Mock()
        def_tec._cfg.sections = deepcopy({"tox": def_tox_attrs})
        def_tec.configure_mock(**deepcopy(def_tox_attrs))
        def_tec.envlist = ["b", "c"]
        def_tec.envlist_default = ["b", "c"]
        envc = {}
        def_tec.envconfigs = {"b": {}, "c": envc}
        with patch("tox_lsr.hooks.merge_envconf") as mock_me:
            merge_config(tec, def_tec)
            self.assertEqual(1, mock_me.call_count)
        self.assertIs(enva, tec.envconfigs["a"])
        self.assertIs(envb, tec.envconfigs["b"])
        self.assertIs(envc, tec.envconfigs["c"])
        self.assertEqual("a", tec.a)
        self.assertEqual("b", tec.b)
        self.assertEqual("d", tec.c)
        self.assertEqual(set(["a", "b", "c"]), set(tec.envlist))
        self.assertEqual(set(["a", "b", "c"]), set(tec.envlist_default))
        unittest_mock.FILTER_DIR = True  # reset

    def test_tox_set_set_prop_values_ini(self):
        """Test set_prop_values_ini."""

        conf = {"a": "a", "b": "b"}
        def_conf = {}
        set_prop_values_ini("a", def_conf, conf)
        self.assertEqual({"a": "a"}, def_conf)
        set_prop_values_ini("a", def_conf, conf)
        self.assertEqual({"a": "a"}, def_conf)
        set_prop_values_ini("b", def_conf, conf)
        self.assertEqual({"a": "a", "b": "b"}, def_conf)
        set_prop_values_ini("a", def_conf, conf)
        self.assertEqual({"a": "a", "b": "b"}, def_conf)
        conf = {
            "setenv": "a\nb",
            "deps": "a",
            "passenv": "TEST_*",
            "whitelist_externals": "mycmd\nmyothercmd",
        }
        def_conf = {
            "setenv": "c\nd",
            "deps": "b",
            "passenv": "*",
            "whitelist_externals": "bash",
        }
        set_prop_values_ini("setenv", def_conf, conf)
        self.assertEqual("c\nd\na\nb", def_conf["setenv"])
        set_prop_values_ini("deps", def_conf, conf)
        self.assertEqual("b\na", def_conf["deps"])
        set_prop_values_ini("passenv", def_conf, conf)
        self.assertEqual("*\nTEST_*", def_conf["passenv"])
        set_prop_values_ini("whitelist_externals", def_conf, conf)
        self.assertEqual(
            "bash\nmycmd\nmyothercmd", def_conf["whitelist_externals"]
        )

    def test_lsr_path(self):
        """Test the _LSRPath class."""

        real = "/no/such/path/to/realfile"
        temp = "/no/such/path/to/temp"
        stack_plain = (("myfile", 1, "myfunc", "text"),)
        stack_iniconfig = (("/path/to/iniconfig.py", 1, "__init__", "text"),)
        with patch("traceback.extract_stack", return_value=stack_plain):
            lsr = _LSRPath(real, temp)
            self.assertEqual(real, str(lsr))
        with patch("traceback.extract_stack", return_value=stack_iniconfig):
            lsr = _LSRPath(real, temp)
            self.assertEqual(temp, str(lsr))

    def test_is_lsr_enabled(self):
        """Test is_lsr_enabled."""

        config = MockConfig({})
        config._cfg.get = Mock(return_value="false")
        self.assertFalse(is_lsr_enabled(config))
        config._cfg.sections[LSR_CONFIG_SECTION] = {}
        self.assertFalse(is_lsr_enabled(config))
        self.assertFalse(is_lsr_enabled(config))
        config._cfg.get = Mock(return_value="true")
        self.assertTrue(is_lsr_enabled(config))

        config._cfg.get = Mock(return_value="true")
        os.environ[LSR_ENABLE_ENV] = "false"
        self.assertFalse(is_lsr_enabled(config))
        config._cfg.get = Mock(return_value="false")
        os.environ[LSR_ENABLE_ENV] = "true"
        self.assertTrue(is_lsr_enabled(config))

        config = MockConfig()
        config._cfg.get = Mock(return_value="false")
        os.environ[LSR_ENABLE_ENV] = "false"
        setattr(config.option, LSR_ENABLE, True)
        self.assertTrue(is_lsr_enabled(config))
        config._cfg.get = Mock(return_value="true")
        os.environ[LSR_ENABLE_ENV] = "true"
        setattr(config.option, LSR_ENABLE, False)
        self.assertFalse(is_lsr_enabled(config))
        del os.environ[LSR_ENABLE_ENV]
