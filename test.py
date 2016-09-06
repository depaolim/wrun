from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import subprocess
import unittest

import wrun

DIR_NAME = os.path.dirname(os.path.realpath(__file__))


class AcceptanceTest(unittest.TestCase):
        def setUp(self):
            self.daemon = subprocess.Popen("python wrun/__init__.py")
            
        def tearDown(self):
            self.daemon.terminate()
            
        def test_execute_with_param_P1(self):
            client = wrun.Client("localhost")
            result = client.run("sample.bat", "P1")
            self.assertEqual(result, "{}\r\nhello P1\r\n".format(DIR_NAME))

        def test_execute_with_param_P2(self):
            client = wrun.Client("localhost")
            result = client.run("sample.bat", "P2")
            self.assertEqual(result, "{}\r\nhello P2\r\n".format(DIR_NAME))


if __name__ == '__main__':
    unittest.main()
