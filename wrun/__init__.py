from functools import reduce
import json
import logging
import logging.config
import operator
import os
import runpy
import subprocess

from .transport import TCPClient, TCPServer
from .transport import SecureTCPClient, SecureTCPServer

ENCODING = "utf-8"

log = logging.getLogger(__name__)


class BaseConfig(object):
    def __init__(self, filepath, **kwargs):
        attrs = runpy.run_path(filepath)
        self.__dict__.update(kwargs)
        for setting, setting_value in attrs.items():
            if setting.isupper():
                setattr(self, setting, setting_value)

    @staticmethod
    def store(filepath, **kwargs):
        with open(filepath, "w") as f:
            for k, v in kwargs.items():
                f.write('{} = {}\n'.format(k, repr(v)))


class Config(BaseConfig):
    def __init__(self, filepath):
        super(Config, self).__init__(filepath, HOST="localhost", COLLECT_STDERR=False)
        log_config(self)
        log.info("settings_file '%s'", filepath)
        log.info("settings \"%s\"", self.__dict__)


LOGGING_PARAMS = {
    "LOG_PATH": lambda param: logging.basicConfig(filename=param, level=logging.DEBUG, filemode='a'),
    "LOG_FILECONFIG": logging.config.fileConfig,
    "LOG_DICTCONFIG": logging.config.dictConfig,
}


def log_config(config, logging_params=LOGGING_PARAMS):
    assert reduce(operator.xor, [hasattr(config, k) for k in logging_params], False)
    for k, f in logging_params.items():
        if hasattr(config, k):
            f(getattr(config, k))
            return


class StringTranslator:
    encoding = ENCODING

    def decode(self, binary_buffer):
        return binary_buffer.decode(self.encoding)

    def encode(self, string_buffer):
        return string_buffer.encode(self.encoding)


class Manservant:
    """ Interprets and run actions """

    def __init__(self, translator, action):
        self.translator = translator
        self.action = action

    def __call__(self, encoded_request):
        decoded_request = self.translator.decode(encoded_request)
        decoded_response = self.action(decoded_request)
        return self.translator.encode(decoded_response)


class Client:
    """ Encode and request actions """

    def __init__(self, translator, channel):
        self.translator = translator
        self.channel = channel

    def request(self, request):
        binary_request = self.translator.encode(request)
        binary_response = self.channel.request(binary_request)
        return self.translator.decode(binary_response)


def daemon(server_address, action, **kwargs):
    translate = StringTranslator()
    manservant = Manservant(translate, action)
    if kwargs:
        server_class = SecureTCPServer
    else:
        server_class = TCPServer
    with server_class(server_address, manservant, **kwargs) as channel:
        channel.serve()


def client(server_address, request, **kwargs):
    translate = StringTranslator()
    if kwargs:
        client_class = SecureTCPClient
    else:
        client_class = TCPClient
    with client_class(server_address, **kwargs) as channel:
        client = Client(translate, channel)
        return client.request(request)


def executor(exe_path, command, collect_stderr=False):
    exe_name, args, input_stdin = json.loads(command)
    log.debug("executor %s %s", exe_name, " ".join(args))
    cmd = [os.path.join(exe_path, exe_name)]
    cmd.extend(args)
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "args": cmd, "cwd": exe_path}
    if input_stdin:
        kwargs["stdin"] = subprocess.PIPE
    process = subprocess.Popen(**kwargs)
    kwargs = {}
    if input_stdin:
        kwargs["input"] = input_stdin.encode(ENCODING)
    output, error = process.communicate(**kwargs)
    retcode = process.poll()
    results = {"stdout": output.decode(ENCODING), "returncode": retcode}
    if collect_stderr:
        results["stderr"] = error.decode(ENCODING)
    return json.dumps(results)


class Proxy:
    def __init__(self, host, port, **kwargs):
        self.client = lambda request: client((host, port), request, **kwargs)

    def run(self, executable_name, args, input_stdin=""):
        result = self.client(json.dumps([executable_name, args, input_stdin]))
        return json.loads(result)
