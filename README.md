# wrun
Run Remote Windows Executables

## Installation

Install from pypi

    pip install wrun

### To use "Windows Service" on Windows

Install the last PyWin32 package
https://sourceforge.net/projects/pywin32/files/pywin32/

## Usage

You can create a Windows Service and use it via wrun.Proxy

#### Service Configuration

Create a configuration file with python syntax.
Example settings.py:

    EXECUTABLE_PATH = "C:\remote_activation"
    LOG_PATH = "C:\remote_activation\wrun.log"
    PORT = 3333
    
Mandatory settings:
 * EXECUTABLE_PATH: absolute path of the executables directory
 * LOG_PATH/LOG_FILECONFIG/LOG_DICTCONFIG: log path and configuration
 * PORT: daemon listening port
 
Optional settings:
 * HOST: host name or IP address (default: localhost)
 * COLLECT_STDERR: response results contains stderr too (default: False)
 * SECURE: a dict with "cafile" and "keyfile", enables secure socket server

#### Advanced Logging

You must specify one and only one of the following settings:
 * LOG_PATH: absolute path of the daemon log file
 * LOG_FILECONFIG: absolute path of the logging ini configuration
    [https://docs.python.org/2.7/library/logging.config.html#logging.config.fileConfig]
 * LOG_DICTCONFIG: dictionary with logging configuration
    [https://docs.python.org/2.7/library/logging.config.html#logging.config.dictConfig]

#### Service Management

Create the Windows Service:

    wrun_service.py <service-name> <absolute-path-to-settings-file>

(wrun_service.py is a utility script installed alongside with wrun)

Start/Stop/Delete the service:

    sc start|stop|delete <service-name>

#### Client

Sample code:

    import wrun
    
    client = wrun.Proxy("localhost", 3333)
    result = client.run("sample.exe", ["first-param", "second-param"])
    print(result)
    # {"stdout": "OUTPUT", "returncode": 0}
    
 General form:
 
    import wrun
    
    client = wrun.Proxy(<server>, <port>)
    # client = wrun.Proxy(<server>, <port>, <cafile>)  # for SSL
    result = client.run(<executable_name>, <params>, <input_stdin>="")

 Some constraints:
 
 * server, port: connection parameters for daemon
 * executable_name: name of exe or script available in the EXECUTABLE_PATH of the daemon
 * params: list (can be empty) of command line arguments to pass to executable
 * input_stdin: if specified is passed as stdin to the process
 * result: dictionary with collected stdout and returncode
 
The client does not need PyWin32

## Disclaimer

USE IT AT YOUR OWN RISK!

This piece of software enables the execution of code on a remote host without any authentication.
This behaviour is "by definition" a "security hole".
So you should use "wrun" only on a very reliable environment! (ex. completely disconnected LAN ... and a "completely connected brain" (cit c8e)! )


## Tests
 
To run the test cases:

    git clone https://github.com/depaolim/wrun
    cd wrun
    python test.py
 
Some tests will be skipped if PyWin32 is not installed


### Test Certificates:

To rebuild the demo certificates:

```
cd demo_ssl
export WRUN_DEMO_PWD=x1234
openssl genrsa -des3 -passout pass:$WRUN_DEMO_PWD -out server.orig.key 2048
openssl rsa -passin pass:$WRUN_DEMO_PWD -in server.orig.key -out server.key
openssl req -new -key server.key -out server.csr -subj "/C=IT/emailAddress=depaolim@gmail.com"
openssl x509 -req -days 358000 -in server.csr -signkey server.key -out server.crt
```

## TODO

* Travis-CI
* hmac
